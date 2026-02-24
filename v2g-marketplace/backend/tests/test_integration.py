"""
Integration tests for V2G Marketplace.

Tests cover:
1. Full simulation flow from start to finish
2. API -> Database -> Response flow
3. Multiple concurrent simulations
4. Component integration (Auction + Token + Agents)
"""

import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set test database path
TEST_DB_PATH = tempfile.mktemp(suffix="_integration.db")
os.environ["V2G_DB_PATH"] = TEST_DB_PATH


class TestFullSimulationFlow:
    """Test complete simulation workflow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        from backend.core.database import Database, reset_database

        os.environ["V2G_DB_PATH"] = TEST_DB_PATH

        reset_database()

        self.db = Database(TEST_DB_PATH)
        self.db.init_db()

        yield

        self.db.close()
        reset_database()
        if os.path.exists(TEST_DB_PATH):
            os.unlink(TEST_DB_PATH)

    def test_single_day_simulation(self):
        """Test a complete single-day simulation."""
        from backend.core.auction import McAfeeAuction, Bid
        from backend.core.token import SHAKTIToken
        from backend.core.agents import Prosumer

        # Create token model
        token = SHAKTIToken(initial_staking_rate=0.2)

        # Create prosumers
        agents = []
        for i in range(100):
            agent_type = ["residential", "commercial", "fleet"][i % 3]
            agent = Prosumer(
                agent_id=f"agent_{i}",
                agent_type=agent_type,
                battery_capacity=50.0 + (i % 5) * 10,
                initial_soc=0.3 + (i % 7) * 0.1
            )
            agents.append(agent)

        # Simulate 24 hours
        results = []
        for hour in range(24):
            auction = McAfeeAuction()

            # Generate bids from agents
            for agent in agents:
                bid = agent.generate_bid(hour=hour)
                if bid is not None:
                    auction.add_bid(Bid(
                        agent_id=agent.agent_id,
                        quantity=bid.quantity,
                        price=bid.price,
                        is_buy=bid.is_buy
                    ))

            # Clear market
            clearing_result = auction.clear_market()

            # Process token transaction if trades occurred
            if clearing_result.clearing_price is not None:
                volume_inr = clearing_result.total_quantity * clearing_result.clearing_price
                token_result = token.process_transaction(volume_inr=volume_inr)

                results.append({
                    "hour": hour,
                    "clearing_price": clearing_result.clearing_price,
                    "volume": clearing_result.total_quantity,
                    "matched_pairs": len(clearing_result.matched_buyers),
                    "token_price": token_result.new_price
                })

            # Update agent SOCs based on trades
            for buyer in clearing_result.matched_buyers:
                agent = next((a for a in agents if a.agent_id == buyer.agent_id), None)
                if agent:
                    agent.update_soc(energy_delta=buyer.quantity)

            for seller in clearing_result.matched_sellers:
                agent = next((a for a in agents if a.agent_id == seller.agent_id), None)
                if agent:
                    agent.update_soc(energy_delta=-seller.quantity)

        # Verify simulation produced results
        assert len(results) > 0
        assert all(r["clearing_price"] > 0 for r in results)
        assert all(r["volume"] > 0 for r in results)

    def test_week_simulation_with_persistence(self):
        """Test a week-long simulation with database persistence."""
        from backend.core.auction import McAfeeAuction, Bid
        from backend.core.token import SHAKTIToken

        # Create and save simulation
        sim_id = self.db.save_simulation({
            "n_agents": 50,
            "n_days": 7,
            "status": "running"
        })

        token = SHAKTIToken()
        total_volume = 0
        total_prices = []

        # Simulate 7 days * 24 hours
        for period in range(7 * 24):
            hour = period % 24

            auction = McAfeeAuction()

            # Add random bids
            import random
            for i in range(50):
                is_buyer = random.random() > 0.5
                price = random.uniform(5.0, 15.0)
                quantity = random.uniform(5.0, 20.0)

                auction.add_bid(Bid(
                    agent_id=f"agent_{i}",
                    quantity=quantity,
                    price=price,
                    is_buy=is_buyer
                ))

            result = auction.clear_market()

            if result.clearing_price is not None:
                total_volume += result.total_quantity
                total_prices.append(result.clearing_price)

                # Save period to database
                self.db.save_period({
                    "simulation_id": sim_id,
                    "period": period,
                    "hour": hour,
                    "clearing_price": result.clearing_price,
                    "volume": result.total_quantity,
                    "n_buyers": len(result.matched_buyers),
                    "n_sellers": len(result.matched_sellers)
                })

                # Process token
                token.process_transaction(
                    volume_inr=result.total_quantity * result.clearing_price
                )

        # Update simulation with final stats
        avg_price = sum(total_prices) / len(total_prices) if total_prices else 0
        self.db.update_simulation(sim_id, {
            "status": "completed",
            "avg_price": avg_price,
            "total_volume": total_volume
        })

        # Verify database records
        saved_sim = self.db.get_simulation(sim_id)
        assert saved_sim["status"] == "completed"
        assert saved_sim["avg_price"] > 0

        periods = self.db.get_periods(sim_id)
        assert len(periods) > 0


class TestDatabaseAPIFlow:
    """Test API -> Database -> Response flow."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test client."""
        from backend.core.database import Database, reset_database

        os.environ["V2G_DB_PATH"] = TEST_DB_PATH

        reset_database()

        self.db = Database(TEST_DB_PATH)
        self.db.init_db()

        yield

        self.db.close()
        reset_database()
        if os.path.exists(TEST_DB_PATH):
            os.unlink(TEST_DB_PATH)

    @pytest.fixture
    def client(self, setup):
        """Create test client."""
        from backend.api.main import app
        from fastapi.testclient import TestClient
        with TestClient(app) as test_client:
            yield test_client

    @pytest.fixture
    def auth_headers(self, client):
        """Get authenticated headers."""
        response = client.post("/auth/register", json={
            "email": "integration@test.com",
            "password": "testpassword"
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    def test_create_simulation_persists_to_db(self, client, auth_headers):
        """Test that creating simulation via API persists to database."""
        response = client.post("/simulations", json={
            "n_agents": 200,
            "n_days": 14
        }, headers=auth_headers)

        sim_id = response.json()["id"]

        # Verify in database
        saved = self.db.get_simulation(sim_id)
        assert saved is not None
        assert saved["n_agents"] == 200
        assert saved["n_days"] == 14

    def test_simulation_workflow(self, client, auth_headers):
        """Test complete simulation workflow via API."""
        # Create simulation
        create_response = client.post("/simulations", json={
            "n_agents": 100,
            "n_days": 1
        }, headers=auth_headers)
        sim_id = create_response.json()["id"]

        # Update to running
        client.patch(f"/simulations/{sim_id}", json={
            "status": "running"
        }, headers=auth_headers)

        # Add periods
        for hour in range(24):
            client.post("/periods", json={
                "simulation_id": sim_id,
                "period": hour,
                "hour": hour,
                "clearing_price": 5.0 + hour * 0.2,
                "volume": 1000 + hour * 50
            }, headers=auth_headers)

        # Update to completed
        update_response = client.patch(f"/simulations/{sim_id}", json={
            "status": "completed",
            "avg_price": 7.5,
            "total_volume": 30000
        }, headers=auth_headers)

        assert update_response.json()["status"] == "completed"

        # Get periods
        periods_response = client.get(
            f"/simulations/{sim_id}/periods",
            headers=auth_headers
        )
        assert len(periods_response.json()) == 24

    def test_price_history_flow(self, client):
        """Test price history API -> DB flow."""
        # Add prices
        prices = [5.5, 6.0, 6.5, 7.0, 7.5]
        for price in prices:
            client.post("/prices", json={
                "price": price,
                "source": "simulation"
            })

        # Retrieve prices
        response = client.get("/prices?limit=10")
        data = response.json()

        assert len(data) == 5
        # Most recent first
        assert data[0]["price"] == 7.5


class TestConcurrentSimulations:
    """Test multiple concurrent simulations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        from backend.core.database import Database, reset_database

        os.environ["V2G_DB_PATH"] = TEST_DB_PATH

        reset_database()

        self.db = Database(TEST_DB_PATH)
        self.db.init_db()

        yield

        self.db.close()
        reset_database()
        if os.path.exists(TEST_DB_PATH):
            os.unlink(TEST_DB_PATH)

    def run_simulation(self, sim_id: str, n_periods: int):
        """Run a single simulation."""
        from backend.core.auction import McAfeeAuction, Bid
        import random

        results = []
        for period in range(n_periods):
            auction = McAfeeAuction()

            # Add random bids
            for i in range(20):
                auction.add_bid(Bid(
                    agent_id=f"agent_{i}",
                    quantity=random.uniform(5, 20),
                    price=random.uniform(5, 15),
                    is_buy=random.random() > 0.5
                ))

            result = auction.clear_market()
            if result.clearing_price:
                results.append({
                    "period": period,
                    "price": result.clearing_price,
                    "volume": result.total_quantity
                })

                self.db.save_period({
                    "simulation_id": sim_id,
                    "period": period,
                    "hour": period % 24,
                    "clearing_price": result.clearing_price,
                    "volume": result.total_quantity
                })

        return sim_id, results

    def test_concurrent_simulations_no_interference(self):
        """Test that concurrent simulations don't interfere."""
        # Create multiple simulations
        sim_ids = []
        for i in range(5):
            sim_id = self.db.save_simulation({
                "n_agents": 20,
                "n_days": 1
            })
            sim_ids.append(sim_id)

        # Run simulations concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for sim_id in sim_ids:
                future = executor.submit(self.run_simulation, sim_id, 24)
                futures.append(future)

            results = {}
            for future in as_completed(futures):
                sim_id, sim_results = future.result()
                results[sim_id] = sim_results

        # Verify each simulation has its own results
        for sim_id in sim_ids:
            periods = self.db.get_periods(sim_id)
            # Each simulation should have records
            assert len(periods) > 0

            # Verify periods belong to correct simulation
            for period in periods:
                assert period["simulation_id"] == sim_id

    def test_thread_safe_database_access(self):
        """Test that database access is thread-safe."""
        results = []
        errors = []

        def create_and_read():
            try:
                sim_id = self.db.save_simulation({
                    "n_agents": 10,
                    "n_days": 1
                })
                time.sleep(0.01)  # Small delay
                retrieved = self.db.get_simulation(sim_id)
                results.append(retrieved)
            except Exception as e:
                errors.append(str(e))

        threads = []
        for _ in range(20):
            t = threading.Thread(target=create_and_read)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 20


class TestComponentIntegration:
    """Test integration between auction, token, and agents."""

    def test_auction_token_integration(self):
        """Test that auction results correctly feed into token model."""
        from backend.core.auction import McAfeeAuction, Bid
        from backend.core.token import SHAKTIToken

        token = SHAKTIToken()
        initial_price = token.current_price

        auction = McAfeeAuction()

        # Add high-value bids
        for i in range(10):
            auction.add_bid(Bid(f"buyer_{i}", 100.0, 15.0, is_buy=True))
            auction.add_bid(Bid(f"seller_{i}", 100.0, 5.0, is_buy=False))

        result = auction.clear_market()

        # Process token transaction
        if result.clearing_price:
            volume_inr = result.total_quantity * result.clearing_price
            token_result = token.process_transaction(volume_inr=volume_inr)

            # Token should have processed the transaction
            assert token_result.volume_processed == volume_inr
            assert token_result.fee_collected > 0

    def test_agent_auction_integration(self):
        """Test that agent bids work correctly in auction."""
        from backend.core.auction import McAfeeAuction, Bid
        from backend.core.agents import Prosumer

        # Create agents with different profiles
        agents = [
            Prosumer("agent_1", "residential", battery_capacity=40, initial_soc=0.8),  # Seller
            Prosumer("agent_2", "commercial", battery_capacity=100, initial_soc=0.2),  # Buyer
            Prosumer("agent_3", "fleet", battery_capacity=200, initial_soc=0.5),  # Either
        ]

        auction = McAfeeAuction()

        # Generate bids for peak hour (sellers more active)
        for agent in agents:
            bid = agent.generate_bid(hour=18)  # Peak hour
            if bid:
                auction.add_bid(Bid(
                    agent_id=agent.agent_id,
                    quantity=bid.quantity,
                    price=bid.price,
                    is_buy=bid.is_buy
                ))

        result = auction.clear_market()

        # Should have some activity
        bids = auction.get_bids()
        assert len(bids) > 0

    def test_full_pipeline_integration(self):
        """Test complete pipeline: agents -> auction -> token -> database."""
        from backend.core.auction import McAfeeAuction, Bid
        from backend.core.token import SHAKTIToken
        from backend.core.agents import Prosumer
        from backend.core.database import Database

        # Set up fresh database
        db_path = tempfile.mktemp(suffix="_pipeline.db")
        db = Database(db_path)
        db.init_db()

        try:
            # Create simulation
            sim_id = db.save_simulation({
                "n_agents": 10,
                "n_days": 1
            })

            # Create agents
            agents = []
            for i in range(10):
                agent = Prosumer(
                    agent_id=f"agent_{i}",
                    agent_type="residential",
                    battery_capacity=50,
                    initial_soc=0.3 + i * 0.05
                )
                agents.append(agent)

            # Create token
            token = SHAKTIToken(initial_staking_rate=0.2)

            # Simulate 24 hours
            total_volume = 0
            prices = []

            for hour in range(24):
                auction = McAfeeAuction()

                # Generate bids
                for agent in agents:
                    bid = agent.generate_bid(hour=hour)
                    if bid:
                        auction.add_bid(Bid(
                            agent_id=agent.agent_id,
                            quantity=bid.quantity,
                            price=bid.price,
                            is_buy=bid.is_buy
                        ))

                # Clear market
                result = auction.clear_market()

                if result.clearing_price:
                    volume_inr = result.total_quantity * result.clearing_price
                    token.process_transaction(volume_inr=volume_inr)

                    total_volume += result.total_quantity
                    prices.append(result.clearing_price)

                    # Save to database
                    db.save_period({
                        "simulation_id": sim_id,
                        "period": hour,
                        "hour": hour,
                        "clearing_price": result.clearing_price,
                        "volume": result.total_quantity,
                        "n_buyers": len(result.matched_buyers),
                        "n_sellers": len(result.matched_sellers)
                    })

            # Update simulation
            avg_price = sum(prices) / len(prices) if prices else 0
            db.update_simulation(sim_id, {
                "status": "completed",
                "avg_price": avg_price,
                "total_volume": total_volume
            })

            # Verify results
            saved_sim = db.get_simulation(sim_id)
            assert saved_sim["status"] == "completed"

            periods = db.get_periods(sim_id)
            assert len(periods) > 0

        finally:
            db.close()
            if os.path.exists(db_path):
                os.unlink(db_path)


class TestStressScenarios:
    """Test stress scenarios and edge cases."""

    def test_high_frequency_trading(self):
        """Test high-frequency market clearing."""
        from backend.core.auction import McAfeeAuction, Bid
        from backend.core.token import SHAKTIToken

        token = SHAKTIToken()

        # Simulate 1000 rapid market clearings
        start_time = time.perf_counter()

        for _ in range(1000):
            auction = McAfeeAuction()

            for i in range(50):
                auction.add_bid(Bid(f"buyer_{i}", 10.0, 10.0 + i * 0.1, is_buy=True))
                auction.add_bid(Bid(f"seller_{i}", 10.0, 5.0 + i * 0.1, is_buy=False))

            result = auction.clear_market()
            if result.clearing_price:
                token.process_transaction(
                    volume_inr=result.total_quantity * result.clearing_price
                )

        elapsed = time.perf_counter() - start_time

        # Should complete 1000 iterations quickly
        assert elapsed < 30.0  # Less than 30 seconds

    def test_extreme_market_conditions(self):
        """Test behavior under extreme market conditions."""
        from backend.core.auction import McAfeeAuction, Bid

        # All buyers, no sellers
        auction1 = McAfeeAuction()
        for i in range(100):
            auction1.add_bid(Bid(f"buyer_{i}", 10.0, 15.0, is_buy=True))

        result1 = auction1.clear_market()
        assert result1.clearing_price is None
        assert result1.total_quantity == 0

        # All sellers, no buyers
        auction2 = McAfeeAuction()
        for i in range(100):
            auction2.add_bid(Bid(f"seller_{i}", 10.0, 5.0, is_buy=False))

        result2 = auction2.clear_market()
        assert result2.clearing_price is None

        # Very imbalanced market (99 buyers, 1 seller)
        auction3 = McAfeeAuction()
        for i in range(99):
            auction3.add_bid(Bid(f"buyer_{i}", 10.0, 10.0 + i * 0.1, is_buy=True))
        auction3.add_bid(Bid("seller_0", 10.0, 5.0, is_buy=False))

        result3 = auction3.clear_market()
        # Should complete without error
        assert result3 is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
