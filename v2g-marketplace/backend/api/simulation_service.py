"""
Background simulation execution service.

Manages long-running simulations in separate threads.
"""

import threading
import uuid
import json
import os
import subprocess
from datetime import datetime
from typing import Dict, Optional
from dataclasses import asdict
import sys
from pathlib import Path

# Add project root to path for imports (works on both Windows and Unix)
_backend_dir = Path(__file__).parent.parent
_project_root = _backend_dir
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from simulation.runner import SimulationRunner, SimulationConfig, DemandMode
from core.database import Database


class SimulationJob:
    """Represents a running or completed simulation job."""

    def __init__(self, job_id: str, config: SimulationConfig, db: Database):
        self.job_id = job_id
        self.config = config
        self.db = db
        self.status = "pending"  # pending, running, completed, failed
        self.progress = 0.0
        self.current_day = 0
        self.total_days = config.duration_hours // 24
        self.error: Optional[str] = None
        self.results: Optional[dict] = None
        self.thread: Optional[threading.Thread] = None

    def _resolve_git_commit(self) -> Optional[str]:
        """Best-effort retrieval of current git commit hash."""
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=str(_project_root),
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            ).strip()
            return commit or None
        except Exception:
            return None

    def _write_provenance_artifact(self) -> None:
        """Write machine-readable evidence for this simulation run."""
        if self.results is None:
            return

        artifacts_dir = Path(
            os.getenv("CLAIM_ARTIFACTS_DIR", str(_project_root / "artifacts" / "claim_matrix"))
        )
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        payload = {
            "job_id": self.job_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "seed": self.config.random_seed,
            "config": asdict(self.config),
            "results": self.results,
            "provenance": {
                "git_commit": self._resolve_git_commit(),
                "container_image_digest": os.getenv("CONTAINER_IMAGE_DIGEST"),
                "config_hash": str(hash(json.dumps(asdict(self.config), sort_keys=True, default=str))),
                "timestamp_utc": datetime.utcnow().isoformat() + "Z",
            },
        }

        with open(artifacts_dir / f"simulation_{self.job_id}.json", "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)

    def run(self):
        """Execute the simulation in background."""
        self.status = "running"
        self.progress = 0.0

        try:
            # Create and run simulation
            runner = SimulationRunner(self.config)
            result = runner.run()

            # Save results to database
            sim_id = self.db.save_simulation({
                "id": self.job_id,
                "n_agents": self.config.num_evs,
                "n_days": self.total_days,
                "status": "completed",
                "avg_price": result.avg_price_inr,
                "total_volume": result.total_v2g_discharge_kwh + result.total_charging_kwh,
            })

            # Save periods
            for idx, stats in enumerate(result.hourly_stats):
                self.db.save_period({
                    "simulation_id": sim_id,
                    "period": idx,
                    "hour": stats.timestamp.hour,
                    "clearing_price": stats.energy_price_inr,
                    "volume": stats.v2g_discharge_kwh + stats.charging_kwh,
                    "n_buyers": stats.evs_charging,
                    "n_sellers": stats.evs_discharging,
                })

                # Save price history
                self.db.save_price(stats.energy_price_inr, "simulation")

                # Update progress
                self.current_day = idx // 24
                self.progress = (idx + 1) / len(result.hourly_stats) * 100

            # Format results for frontend
            self.results = {
                "totalEnergyTraded": result.total_v2g_discharge_kwh + result.total_charging_kwh,
                "averagePrice": result.avg_price_inr,
                "totalTransactions": len(result.hourly_stats),
                "gridSavings": result.total_revenue_inr,
                "carbonOffset": (result.total_v2g_discharge_kwh * 0.82) / 1000,  # Approximate CO2 savings
                "peakReduction": ((result.peak_demand_mw - result.avg_demand_mw) / result.peak_demand_mw) * 100,
                "peakPrice": result.peak_price_inr,
                "minPrice": result.min_price_inr,
                "totalRevenue": result.total_revenue_inr,
                "totalDischarge": result.total_v2g_discharge_kwh,
                "totalCharging": result.total_charging_kwh,
            }

            # Add token metrics if enabled
            if result.token_prices:
                self.results.update({
                    "tokenMetrics": {
                        "startPrice": result.token_prices[0],
                        "endPrice": result.token_prices[-1],
                        "priceChange": ((result.token_prices[-1] / result.token_prices[0]) - 1) * 100,
                        "totalBurned": result.total_tokens_burned,
                        "totalMinted": result.total_tokens_minted,
                        "endStakingRate": result.staking_rates[-1] * 100,
                    }
                })

            self.status = "completed"
            self.progress = 100.0
            self._write_provenance_artifact()

        except Exception as e:
            self.status = "failed"
            self.error = str(e)

            # Update database with failure
            self.db.update_simulation(self.job_id, {
                "status": "failed",
            })


class SimulationService:
    """Service for managing simulation jobs."""

    def __init__(self, db: Database):
        self.db = db
        self.jobs: Dict[str, SimulationJob] = {}
        self._lock = threading.Lock()

    def start_simulation(
        self,
        num_agents: int,
        duration_days: int,
        agent_mix: dict,
        region: str,
    ) -> str:
        """
        Start a new simulation job.

        Args:
            num_agents: Number of EV agents
            duration_days: Simulation duration in days
            agent_mix: Dictionary with residential, commercial, fleet percentages
            region: Region name (delhi, mumbai, bangalore, chennai)

        Returns:
            Job ID for tracking the simulation
        """
        job_id = str(uuid.uuid4())

        # Create simulation config
        config = SimulationConfig(
            start_time=datetime.now(),
            duration_hours=duration_days * 24,
            num_evs=num_agents,
            region=region.capitalize(),
            demand_mode=DemandMode.REALISTIC,
            enable_token=True,
            initial_staking_rate=0.20,
            target_staking_rate=0.40,
        )

        # Create job
        job = SimulationJob(job_id, config, self.db)

        # Start in background thread
        thread = threading.Thread(target=job.run, daemon=True)
        thread.start()
        job.thread = thread

        with self._lock:
            self.jobs[job_id] = job

        return job_id

    def get_status(self, job_id: str) -> Optional[dict]:
        """
        Get simulation status.

        Args:
            job_id: Job ID

        Returns:
            Status dictionary or None if job not found
        """
        with self._lock:
            job = self.jobs.get(job_id)

        if job is None:
            return None

        return {
            "status": job.status,
            "progress": job.progress,
            "current_day": job.current_day,
            "total_days": job.total_days,
            "error": job.error,
            "results": job.results,
        }

    def get_results_csv(self, job_id: str) -> Optional[str]:
        """
        Get simulation results as CSV.

        Args:
            job_id: Job ID

        Returns:
            CSV string or None if job not found/incomplete
        """
        with self._lock:
            job = self.jobs.get(job_id)

        if job is None or job.status != "completed":
            return None

        # Get periods from database
        periods = self.db.get_periods(job_id)

        # Generate CSV
        csv_lines = ["Period,Hour,ClearingPrice,Volume,Buyers,Sellers"]
        for period in periods:
            csv_lines.append(
                f"{period['period']},{period['hour']},{period['clearing_price']},"
                f"{period['volume']},{period['n_buyers']},{period['n_sellers']}"
            )

        return "\n".join(csv_lines)


# Singleton instance
_simulation_service: Optional[SimulationService] = None


def get_simulation_service(db: Database) -> SimulationService:
    """Get or create the simulation service singleton."""
    global _simulation_service
    if _simulation_service is None or _simulation_service.db is not db:
        _simulation_service = SimulationService(db)
    return _simulation_service
