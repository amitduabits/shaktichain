#!/usr/bin/env python3
"""
V2G Marketplace CLI - Command-line interface for energy trading simulations.

Usage:
    python cli.py simulate --agents 100 --days 7 --output results.json
    python cli.py analyze results.json
    python cli.py report results.json --format html --output report.html
    python cli.py report results.json --format csv --output data.csv
    python cli.py --help
"""

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from core.reports.generator import ReportGenerator
    REPORTS_AVAILABLE = True
except ImportError:
    REPORTS_AVAILABLE = False


# =============================================================================
# ANSI Color Codes (no external dependencies)
# =============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Background colors
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"

    @classmethod
    def disable(cls):
        """Disable colors (e.g., for non-TTY output)."""
        for attr in dir(cls):
            if not attr.startswith('_') and attr.isupper():
                setattr(cls, attr, '')


def colored(text: str, color: str) -> str:
    """Wrap text in color codes."""
    return f"{color}{text}{Colors.RESET}"


def print_header(text: str):
    """Print a styled header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 60}{Colors.RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{Colors.GREEN}✓{Colors.RESET} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{Colors.RED}✗{Colors.RESET} {text}", file=sys.stderr)


def print_info(text: str):
    """Print info message."""
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {text}")


# =============================================================================
# Progress Bar
# =============================================================================

class ProgressBar:
    """Simple text-based progress bar."""

    def __init__(self, total: int, width: int = 40, prefix: str = "Progress"):
        self.total = total
        self.width = width
        self.prefix = prefix
        self.current = 0
        self.start_time = time.time()

    def update(self, current: int = None, increment: int = 1):
        """Update progress bar."""
        if current is not None:
            self.current = current
        else:
            self.current += increment

        self._render()

    def _render(self):
        """Render the progress bar to terminal."""
        percent = self.current / self.total if self.total > 0 else 1
        filled = int(self.width * percent)
        empty = self.width - filled

        bar = f"{Colors.GREEN}{'█' * filled}{Colors.DIM}{'░' * empty}{Colors.RESET}"
        percent_str = f"{percent * 100:5.1f}%"

        # Calculate ETA
        elapsed = time.time() - self.start_time
        if self.current > 0:
            eta = (elapsed / self.current) * (self.total - self.current)
            eta_str = f"ETA: {eta:.1f}s" if eta > 0 else "Done!"
        else:
            eta_str = "Calculating..."

        # Print progress bar (overwrite previous line)
        line = f"\r{Colors.CYAN}{self.prefix}{Colors.RESET} [{bar}] {percent_str} {Colors.DIM}{eta_str}{Colors.RESET}"
        print(line, end='', flush=True)

        if self.current >= self.total:
            print()  # New line when complete

    def finish(self):
        """Mark progress as complete."""
        self.current = self.total
        self._render()


# =============================================================================
# Simulation Data Models
# =============================================================================

@dataclass
class Agent:
    """Represents an EV/prosumer agent in the marketplace."""
    id: int
    battery_capacity_kwh: float  # Battery capacity in kWh
    soc: float  # State of charge (0-1)
    min_soc: float  # Minimum SOC to maintain
    max_charge_rate_kw: float  # Max charging rate
    max_discharge_rate_kw: float  # Max V2G discharge rate
    price_sensitivity: float  # How price-sensitive the agent is (0-1)


@dataclass
class MarketOrder:
    """A bid or ask in the energy market."""
    agent_id: int
    order_type: str  # 'bid' or 'ask'
    quantity_kwh: float
    price_per_kwh: float
    timestamp: str


@dataclass
class ClearingResult:
    """Result of a market clearing event."""
    timestamp: str
    clearing_price: float
    total_volume_kwh: float
    num_bids_matched: int
    num_asks_matched: int
    hour_of_day: int
    is_peak_hour: bool


# =============================================================================
# Market Simulation Engine
# =============================================================================

class MarketSimulator:
    """Simulates a V2G energy marketplace."""

    # Peak hours (6 PM - 10 PM)
    PEAK_HOURS = {18, 19, 20, 21}

    # Base prices (INR/kWh) - aligned with Indian tariffs
    BASE_PRICE_PEAK = 8.0
    BASE_PRICE_OFFPEAK = 4.5

    def __init__(self, num_agents: int, seed: int = None):
        """Initialize the simulator."""
        if seed is not None:
            random.seed(seed)

        self.agents = self._create_agents(num_agents)
        self.clearing_results: List[ClearingResult] = []
        self.all_orders: List[MarketOrder] = []

    def _create_agents(self, num_agents: int) -> List[Agent]:
        """Create diverse agent population."""
        agents = []
        for i in range(num_agents):
            # Variety of EV types
            battery_capacity = random.choice([40, 50, 60, 75, 100])  # kWh
            agents.append(Agent(
                id=i,
                battery_capacity_kwh=battery_capacity,
                soc=random.uniform(0.3, 0.9),
                min_soc=random.uniform(0.15, 0.3),
                max_charge_rate_kw=random.choice([7.4, 11, 22]),  # AC/DC charging
                max_discharge_rate_kw=random.choice([5, 7.4, 10]),  # V2G rate
                price_sensitivity=random.uniform(0.3, 1.0)
            ))
        return agents

    def _get_base_price(self, hour: int) -> float:
        """Get base price based on time of day."""
        if hour in self.PEAK_HOURS:
            return self.BASE_PRICE_PEAK
        return self.BASE_PRICE_OFFPEAK

    def _generate_orders(self, current_time: datetime) -> List[MarketOrder]:
        """Generate buy/sell orders from agents."""
        hour = current_time.hour
        base_price = self._get_base_price(hour)
        is_peak = hour in self.PEAK_HOURS
        orders = []

        for agent in self.agents:
            # Decision logic based on SOC, price sensitivity, and time
            available_discharge = (agent.soc - agent.min_soc) * agent.battery_capacity_kwh
            available_charge = (1 - agent.soc) * agent.battery_capacity_kwh

            if is_peak and available_discharge > 1 and random.random() < 0.6:
                # Tend to sell during peak hours if have capacity
                quantity = min(
                    available_discharge * random.uniform(0.3, 0.7),
                    agent.max_discharge_rate_kw
                )
                # Higher price sensitivity = higher ask price
                price = base_price * (1 + agent.price_sensitivity * random.uniform(0.1, 0.4))
                orders.append(MarketOrder(
                    agent_id=agent.id,
                    order_type='ask',
                    quantity_kwh=round(quantity, 2),
                    price_per_kwh=round(price, 2),
                    timestamp=current_time.isoformat()
                ))
            elif not is_peak and available_charge > 1 and random.random() < 0.5:
                # Tend to buy during off-peak
                quantity = min(
                    available_charge * random.uniform(0.3, 0.6),
                    agent.max_charge_rate_kw
                )
                # Higher price sensitivity = lower bid price
                price = base_price * (1 - agent.price_sensitivity * random.uniform(0.05, 0.2))
                orders.append(MarketOrder(
                    agent_id=agent.id,
                    order_type='bid',
                    quantity_kwh=round(quantity, 2),
                    price_per_kwh=round(price, 2),
                    timestamp=current_time.isoformat()
                ))
            else:
                # Random participation
                if random.random() < 0.2:
                    if random.random() < 0.5 and available_discharge > 1:
                        quantity = min(available_discharge * 0.2, agent.max_discharge_rate_kw)
                        price = base_price * random.uniform(0.9, 1.3)
                        orders.append(MarketOrder(
                            agent_id=agent.id,
                            order_type='ask',
                            quantity_kwh=round(quantity, 2),
                            price_per_kwh=round(price, 2),
                            timestamp=current_time.isoformat()
                        ))
                    elif available_charge > 1:
                        quantity = min(available_charge * 0.2, agent.max_charge_rate_kw)
                        price = base_price * random.uniform(0.8, 1.1)
                        orders.append(MarketOrder(
                            agent_id=agent.id,
                            order_type='bid',
                            quantity_kwh=round(quantity, 2),
                            price_per_kwh=round(price, 2),
                            timestamp=current_time.isoformat()
                        ))

        return orders

    def _clear_market(self, orders: List[MarketOrder], current_time: datetime) -> ClearingResult:
        """Run double auction clearing mechanism."""
        bids = sorted([o for o in orders if o.order_type == 'bid'],
                     key=lambda x: x.price_per_kwh, reverse=True)
        asks = sorted([o for o in orders if o.order_type == 'ask'],
                     key=lambda x: x.price_per_kwh)

        if not bids or not asks:
            # No clearing possible
            hour = current_time.hour
            return ClearingResult(
                timestamp=current_time.isoformat(),
                clearing_price=self._get_base_price(hour),
                total_volume_kwh=0,
                num_bids_matched=0,
                num_asks_matched=0,
                hour_of_day=hour,
                is_peak_hour=hour in self.PEAK_HOURS
            )

        # Find intersection (simplified uniform price auction)
        total_volume = 0
        matched_bids = 0
        matched_asks = 0
        clearing_price = (bids[0].price_per_kwh + asks[0].price_per_kwh) / 2

        bid_idx, ask_idx = 0, 0
        while bid_idx < len(bids) and ask_idx < len(asks):
            if bids[bid_idx].price_per_kwh >= asks[ask_idx].price_per_kwh:
                # Match possible
                matched_qty = min(bids[bid_idx].quantity_kwh, asks[ask_idx].quantity_kwh)
                total_volume += matched_qty
                clearing_price = (bids[bid_idx].price_per_kwh + asks[ask_idx].price_per_kwh) / 2
                matched_bids += 1
                matched_asks += 1
                bid_idx += 1
                ask_idx += 1
            else:
                break

        hour = current_time.hour
        return ClearingResult(
            timestamp=current_time.isoformat(),
            clearing_price=round(clearing_price, 2),
            total_volume_kwh=round(total_volume, 2),
            num_bids_matched=matched_bids,
            num_asks_matched=matched_asks,
            hour_of_day=hour,
            is_peak_hour=hour in self.PEAK_HOURS
        )

    def _update_agent_soc(self, result: ClearingResult, orders: List[MarketOrder]):
        """Update agent SOC based on clearing results."""
        # Simplified: update SOC for participating agents
        for order in orders:
            agent = self.agents[order.agent_id]
            if order.order_type == 'bid':
                # Bought energy (charged)
                delta = order.quantity_kwh / agent.battery_capacity_kwh
                agent.soc = min(1.0, agent.soc + delta * 0.3)  # Partial fill
            else:
                # Sold energy (discharged)
                delta = order.quantity_kwh / agent.battery_capacity_kwh
                agent.soc = max(agent.min_soc, agent.soc - delta * 0.3)

    def run(self, num_days: int, progress_callback=None) -> Dict[str, Any]:
        """Run the full simulation."""
        start_date = datetime(2024, 1, 1, 0, 0, 0)
        total_intervals = num_days * 24  # Hourly intervals

        for interval in range(total_intervals):
            current_time = start_date + timedelta(hours=interval)

            # Generate orders
            orders = self._generate_orders(current_time)
            self.all_orders.extend(orders)

            # Clear market
            result = self._clear_market(orders, current_time)
            self.clearing_results.append(result)

            # Update agent states
            self._update_agent_soc(result, orders)

            # Progress callback
            if progress_callback:
                progress_callback(interval + 1, total_intervals)

        return self._compile_results(num_days)

    def _compile_results(self, num_days: int) -> Dict[str, Any]:
        """Compile simulation results into output format."""
        return {
            "metadata": {
                "num_agents": len(self.agents),
                "num_days": num_days,
                "total_intervals": len(self.clearing_results),
                "simulation_date": datetime.now().isoformat(),
                "peak_hours": list(self.PEAK_HOURS)
            },
            "clearing_results": [asdict(r) for r in self.clearing_results],
            "summary": {
                "total_orders": len(self.all_orders),
                "total_bids": sum(1 for o in self.all_orders if o.order_type == 'bid'),
                "total_asks": sum(1 for o in self.all_orders if o.order_type == 'ask')
            }
        }


# =============================================================================
# Analysis Functions
# =============================================================================

def analyze_results(data: Dict[str, Any]) -> Dict[str, float]:
    """Analyze simulation results and compute statistics."""
    clearing_results = data.get("clearing_results", [])

    if not clearing_results:
        return {}

    prices = [r["clearing_price"] for r in clearing_results]
    volumes = [r["total_volume_kwh"] for r in clearing_results]

    # Separate peak and off-peak prices
    peak_prices = [r["clearing_price"] for r in clearing_results if r["is_peak_hour"]]
    offpeak_prices = [r["clearing_price"] for r in clearing_results if not r["is_peak_hour"]]

    # Calculate statistics
    avg_price = sum(prices) / len(prices)
    total_energy = sum(volumes)

    # Price volatility (standard deviation)
    variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
    std_dev = variance ** 0.5

    # Peak vs off-peak difference
    avg_peak = sum(peak_prices) / len(peak_prices) if peak_prices else 0
    avg_offpeak = sum(offpeak_prices) / len(offpeak_prices) if offpeak_prices else 0

    return {
        "average_clearing_price": round(avg_price, 2),
        "total_energy_traded_kwh": round(total_energy, 2),
        "price_volatility_std": round(std_dev, 2),
        "avg_peak_price": round(avg_peak, 2),
        "avg_offpeak_price": round(avg_offpeak, 2),
        "peak_offpeak_difference": round(avg_peak - avg_offpeak, 2),
        "num_clearing_events": len(clearing_results),
        "avg_volume_per_interval": round(total_energy / len(clearing_results), 2)
    }


def print_analysis(stats: Dict[str, float], metadata: Dict[str, Any] = None):
    """Print formatted analysis results."""
    print_header("V2G Marketplace Analysis Report")

    if metadata:
        print(f"{Colors.DIM}Simulation: {metadata.get('num_agents', 'N/A')} agents, "
              f"{metadata.get('num_days', 'N/A')} days, "
              f"{metadata.get('total_intervals', 'N/A')} intervals{Colors.RESET}\n")

    # Price statistics
    print(f"{Colors.BOLD}{Colors.YELLOW}📊 Price Statistics{Colors.RESET}")
    print(f"   Average Clearing Price:  {Colors.GREEN}₹{stats['average_clearing_price']:.2f}/kWh{Colors.RESET}")
    print(f"   Price Volatility (σ):    {Colors.CYAN}₹{stats['price_volatility_std']:.2f}{Colors.RESET}")
    print()

    # Energy statistics
    print(f"{Colors.BOLD}{Colors.YELLOW}⚡ Energy Statistics{Colors.RESET}")
    print(f"   Total Energy Traded:     {Colors.GREEN}{stats['total_energy_traded_kwh']:,.2f} kWh{Colors.RESET}")
    print(f"   Avg Volume/Interval:     {Colors.CYAN}{stats['avg_volume_per_interval']:.2f} kWh{Colors.RESET}")
    print(f"   Clearing Events:         {stats['num_clearing_events']}")
    print()

    # Peak vs Off-peak
    print(f"{Colors.BOLD}{Colors.YELLOW}🕐 Peak vs Off-Peak Pricing{Colors.RESET}")
    print(f"   Peak Hours Price:        {Colors.RED}₹{stats['avg_peak_price']:.2f}/kWh{Colors.RESET}")
    print(f"   Off-Peak Hours Price:    {Colors.GREEN}₹{stats['avg_offpeak_price']:.2f}/kWh{Colors.RESET}")
    diff = stats['peak_offpeak_difference']
    diff_color = Colors.RED if diff > 0 else Colors.GREEN
    print(f"   Price Difference:        {diff_color}₹{diff:+.2f}/kWh{Colors.RESET}")
    print()


# =============================================================================
# CLI Commands
# =============================================================================

def cmd_simulate(args):
    """Execute simulation command."""
    print_header("V2G Marketplace Simulation")

    print_info(f"Agents: {args.agents}")
    print_info(f"Duration: {args.days} days ({args.days * 24} hourly intervals)")
    print_info(f"Output: {args.output}")
    print()

    # Initialize simulator
    simulator = MarketSimulator(num_agents=args.agents, seed=args.seed)

    # Progress bar
    progress = ProgressBar(
        total=args.days * 24,
        prefix="Simulating"
    )

    def update_progress(current, total):
        progress.update(current=current)

    # Run simulation
    results = simulator.run(num_days=args.days, progress_callback=update_progress)

    # Save results
    try:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print()
        print_success(f"Results saved to {Colors.BOLD}{args.output}{Colors.RESET}")

        # Quick summary
        stats = analyze_results(results)
        print()
        print(f"{Colors.DIM}Quick Summary:{Colors.RESET}")
        print(f"  • Avg Price: ₹{stats['average_clearing_price']:.2f}/kWh")
        print(f"  • Total Energy: {stats['total_energy_traded_kwh']:,.2f} kWh")
        print(f"  • Peak Premium: ₹{stats['peak_offpeak_difference']:+.2f}/kWh")

    except IOError as e:
        print_error(f"Failed to save results: {e}")
        return 1

    return 0


def cmd_analyze(args):
    """Execute analyze command."""
    try:
        with open(args.file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print_error(f"File not found: {args.file}")
        return 1
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON file: {e}")
        return 1

    stats = analyze_results(data)
    if not stats:
        print_error("No clearing results found in data")
        return 1

    print_analysis(stats, data.get("metadata"))

    # Export option
    if args.export:
        try:
            with open(args.export, 'w') as f:
                json.dump(stats, f, indent=2)
            print_success(f"Statistics exported to {args.export}")
        except IOError as e:
            print_error(f"Failed to export: {e}")
            return 1

    return 0


def cmd_report(args):
    """Execute report generation command."""
    if not REPORTS_AVAILABLE:
        print_error("Report generation module not available.")
        print_info("Ensure backend/core/reports/generator.py exists.")
        return 1

    # Load input data
    try:
        with open(args.file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print_error(f"File not found: {args.file}")
        return 1
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON file: {e}")
        return 1

    # Validate data has required structure
    if 'clearing_results' not in data:
        print_error("Invalid results file: missing 'clearing_results' key")
        return 1

    print_header("V2G Marketplace Report Generator")
    print_info(f"Input: {args.file}")
    print_info(f"Format: {args.format}")
    print_info(f"Output: {args.output}")
    print()

    generator = ReportGenerator()

    try:
        if args.format == 'html':
            generator.generate_html_report(data, args.output)
            print_success(f"HTML report generated: {Colors.BOLD}{args.output}{Colors.RESET}")

            # Print summary
            summary = generator.generate_summary_json(data)
            print()
            print(f"{Colors.DIM}Report Summary:{Colors.RESET}")
            print(f"  • Avg Price: ₹{summary['avg_price']:.2f}/kWh")
            print(f"  • Total Volume: {summary['total_volume']:,.2f} kWh")
            print(f"  • Price Volatility: ₹{summary['price_volatility']:.2f}")
            print(f"  • Total Welfare: ₹{summary['total_welfare']:,.2f}")

        elif args.format == 'csv':
            generator.generate_csv_export(data, args.output)
            print_success(f"CSV export generated: {Colors.BOLD}{args.output}{Colors.RESET}")

            # Print stats
            num_rows = len(data.get('clearing_results', []))
            print()
            print(f"{Colors.DIM}Export Summary:{Colors.RESET}")
            print(f"  • Rows exported: {num_rows}")
            print(f"  • Columns: period, hour, day, price, volume, token_price, staking_rate")

        elif args.format == 'json':
            summary = generator.generate_summary_json(data)
            with open(args.output, 'w') as f:
                json.dump(summary, f, indent=2)
            print_success(f"JSON summary generated: {Colors.BOLD}{args.output}{Colors.RESET}")

            # Print summary
            print()
            print(f"{Colors.DIM}Summary Metrics:{Colors.RESET}")
            for key, value in summary.items():
                if isinstance(value, float):
                    print(f"  • {key}: {value:,.4f}")
                else:
                    print(f"  • {key}: {value}")

        else:
            print_error(f"Unknown format: {args.format}")
            return 1

    except IOError as e:
        print_error(f"Failed to write output: {e}")
        return 1
    except Exception as e:
        print_error(f"Report generation failed: {e}")
        return 1

    return 0


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main CLI entry point."""
    # Check if output is a TTY (for color support)
    if not sys.stdout.isatty():
        Colors.disable()

    parser = argparse.ArgumentParser(
        prog='v2g-marketplace',
        description=f'{Colors.BOLD}V2G Marketplace CLI{Colors.RESET} - Energy trading simulation and analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.CYAN}Examples:{Colors.RESET}
  %(prog)s simulate --agents 100 --days 7 --output results.json
  %(prog)s analyze results.json
  %(prog)s analyze results.json --export stats.json
  %(prog)s report results.json --format html --output report.html
  %(prog)s report results.json --format csv --output data.csv

{Colors.CYAN}For more information:{Colors.RESET}
  https://github.com/shaktichain/v2g-marketplace
"""
    )

    subparsers = parser.add_subparsers(
        title='commands',
        dest='command',
        help='available commands'
    )

    # Simulate command
    simulate_parser = subparsers.add_parser(
        'simulate',
        help='Run V2G marketplace simulation',
        description='Simulate energy trading between EV agents in a marketplace'
    )
    simulate_parser.add_argument(
        '--agents', '-a',
        type=int,
        default=100,
        metavar='N',
        help='Number of EV agents to simulate (default: 100)'
    )
    simulate_parser.add_argument(
        '--days', '-d',
        type=int,
        default=7,
        metavar='N',
        help='Number of days to simulate (default: 7)'
    )
    simulate_parser.add_argument(
        '--output', '-o',
        type=str,
        default='results.json',
        metavar='FILE',
        help='Output file for results (default: results.json)'
    )
    simulate_parser.add_argument(
        '--seed', '-s',
        type=int,
        default=None,
        metavar='N',
        help='Random seed for reproducibility'
    )

    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze simulation results',
        description='Analyze results from a previous simulation run'
    )
    analyze_parser.add_argument(
        'file',
        type=str,
        metavar='FILE',
        help='JSON file containing simulation results'
    )
    analyze_parser.add_argument(
        '--export', '-e',
        type=str,
        metavar='FILE',
        help='Export statistics to JSON file'
    )

    # Report command
    report_parser = subparsers.add_parser(
        'report',
        help='Generate reports from simulation results',
        description='Generate HTML, CSV, or JSON reports from simulation results'
    )
    report_parser.add_argument(
        'file',
        type=str,
        metavar='FILE',
        help='JSON file containing simulation results'
    )
    report_parser.add_argument(
        '--format', '-f',
        type=str,
        choices=['html', 'csv', 'json'],
        default='html',
        metavar='FORMAT',
        help='Output format: html, csv, or json (default: html)'
    )
    report_parser.add_argument(
        '--output', '-o',
        type=str,
        default='report.html',
        metavar='FILE',
        help='Output file path (default: report.html)'
    )

    # Parse arguments
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Execute command
    if args.command == 'simulate':
        return cmd_simulate(args)
    elif args.command == 'analyze':
        return cmd_analyze(args)
    elif args.command == 'report':
        return cmd_report(args)

    return 0


if __name__ == '__main__':
    sys.exit(main())
