#!/usr/bin/env python3
"""Run anomaly detection demo for SHAKTI-CHAIN platform.

This script demonstrates:
- Feature extraction from trades, deliveries, and accounts
- Anomaly scoring with multiple models
- Alert generation and handling
- Blockchain event monitoring (mock mode)
"""

import argparse
import logging
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from anomaly import (
    # Core detector
    AnomalyDetector,
    AnomalyType,
    # Feature extractors
    TradingFeatureExtractor,
    DeliveryFeatureExtractor,
    AccountFeatureExtractor,
    GraphFeatureExtractor,
    # Models
    IsolationForestDetector,
    LSTMAutoencoder,
    GraphAnomalyDetector,
    # Alert system
    AlertSystem,
    AlertStore,
    LoggingHandler,
    FileHandler,
    AlertSeverity,
    # Blockchain integration
    BlockchainEventStream,
    BlockchainAnomalyMonitor,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_mock_trades(n_trades: int = 100, anomaly_rate: float = 0.1):
    """Generate mock trade data with some anomalies."""
    trades = []
    base_price = 0.10  # Base energy price per kWh

    # Generate normal trading accounts
    accounts = [f"0x{random.randbytes(20).hex()}" for _ in range(20)]

    # Generate some suspicious account pairs
    suspicious_pairs = [
        (accounts[0], accounts[1]),  # Wash trading pair
        (accounts[2], accounts[3]),
    ]

    for i in range(n_trades):
        timestamp = datetime.now() - timedelta(hours=random.randint(0, 24))

        # Decide if this trade should be anomalous
        is_anomaly = random.random() < anomaly_rate

        if is_anomaly and random.random() < 0.3:
            # Wash trading - same pair, rapid trades
            buyer, seller = random.choice(suspicious_pairs)
            price = base_price * random.uniform(0.95, 1.05)
            quantity = random.uniform(50, 60)  # Consistent quantity
        elif is_anomaly and random.random() < 0.5:
            # Price manipulation - extreme price
            buyer = random.choice(accounts)
            seller = random.choice([a for a in accounts if a != buyer])
            price = base_price * random.uniform(2.0, 5.0)  # Very high
            quantity = random.uniform(1, 10)
        elif is_anomaly:
            # Volume spike
            buyer = random.choice(accounts)
            seller = random.choice([a for a in accounts if a != buyer])
            price = base_price * random.uniform(0.9, 1.1)
            quantity = random.uniform(500, 1000)  # Very high volume
        else:
            # Normal trade
            buyer = random.choice(accounts)
            seller = random.choice([a for a in accounts if a != buyer])
            price = base_price * random.uniform(0.9, 1.1)
            quantity = random.uniform(10, 100)

        trades.append({
            'trade_id': f"TRADE-{i:05d}",
            'buyer_id': buyer,
            'seller_id': seller,
            'counterparty': seller,
            'account_id': buyer,
            'price': price,
            'quantity': quantity,
            'energy_kwh': quantity * 10,
            'timestamp': timestamp,
            'side': 'buy',
        })

    return trades, accounts


def generate_mock_deliveries(n_deliveries: int = 50, anomaly_rate: float = 0.15):
    """Generate mock delivery data with some anomalies."""
    deliveries = []
    providers = [f"0x{random.randbytes(20).hex()}" for _ in range(10)]

    for i in range(n_deliveries):
        timestamp = datetime.now() - timedelta(hours=random.randint(0, 48))
        provider = random.choice(providers)

        # Decide if anomalous
        is_anomaly = random.random() < anomaly_rate

        if is_anomaly and random.random() < 0.5:
            # False claim - claimed much more than actual
            claimed = random.uniform(100, 200)
            actual = claimed * random.uniform(0.3, 0.6)  # Only 30-60% delivered
        elif is_anomaly:
            # Energy discrepancy
            claimed = random.uniform(50, 150)
            actual = claimed * random.uniform(0.7, 0.85)  # 70-85% delivered
        else:
            # Normal delivery
            claimed = random.uniform(50, 150)
            actual = claimed * random.uniform(0.95, 1.02)  # ~100% accurate

        deliveries.append({
            'delivery_id': f"DEL-{i:05d}",
            'account_id': provider,
            'provider': provider,
            'claimed_energy_kwh': claimed,
            'actual_energy_kwh': actual,
            'duration_minutes': random.uniform(30, 120),
            'timestamp': timestamp,
        })

    return deliveries, providers


def generate_mock_accounts(accounts: list, trade_history: dict):
    """Generate mock account data."""
    account_data = []

    for account_id in accounts:
        trades = trade_history.get(account_id, [])
        account_age = random.randint(7, 365)

        account_data.append({
            'account_id': account_id,
            'created_at': datetime.now() - timedelta(days=account_age),
            'reputation': random.uniform(0.3, 0.95),
            'reputation_history': [random.uniform(0.3, 0.9) for _ in range(10)],
            'total_trades': len(trades),
            'total_volume': sum(t.get('quantity', 0) for t in trades),
            'positive_feedback': random.randint(5, 50),
            'total_feedback': random.randint(10, 60),
            'failed_deliveries': random.randint(0, 5),
            'total_deliveries': random.randint(10, 50),
            'disputes': random.randint(0, 3),
        })

    return account_data


def demo_feature_extraction():
    """Demonstrate feature extraction."""
    logger.info("=" * 60)
    logger.info("FEATURE EXTRACTION DEMO")
    logger.info("=" * 60)

    # Generate mock data
    trades, accounts = generate_mock_trades(50)
    deliveries, providers = generate_mock_deliveries(30)

    # Extract trading features
    logger.info("\n--- Trading Feature Extraction ---")
    trade_extractor = TradingFeatureExtractor()

    for trade in trades[:5]:
        features = trade_extractor.extract(trade)
        logger.info(f"Trade {trade['trade_id']}:")
        logger.info(f"  Price z-score: {features.price_zscore:.3f}")
        logger.info(f"  Volume z-score: {features.volume_zscore:.3f}")
        logger.info(f"  Round-trip detected: {features.round_trip_detected}")

    # Extract delivery features
    logger.info("\n--- Delivery Feature Extraction ---")
    delivery_extractor = DeliveryFeatureExtractor()

    for delivery in deliveries[:5]:
        features = delivery_extractor.extract(delivery)
        logger.info(f"Delivery {delivery['delivery_id']}:")
        logger.info(f"  Discrepancy: {features.energy_discrepancy:.2f} kWh")
        logger.info(f"  Discrepancy %: {features.energy_discrepancy_pct:.1f}%")
        logger.info(f"  Physically feasible: {features.is_physically_feasible}")

    # Extract account features
    logger.info("\n--- Account Feature Extraction ---")
    account_extractor = AccountFeatureExtractor()

    # Build trade history
    trade_history = {}
    for trade in trades:
        buyer = trade['buyer_id']
        if buyer not in trade_history:
            trade_history[buyer] = []
        trade_history[buyer].append(trade)

    account_data = generate_mock_accounts(accounts[:5], trade_history)

    for account in account_data[:3]:
        history = trade_history.get(account['account_id'], [])
        features = account_extractor.extract(account, history)
        logger.info(f"Account {account['account_id'][:10]}...:")
        logger.info(f"  Age: {features.account_age_days} days")
        logger.info(f"  Trades: {features.total_trades}")
        logger.info(f"  Reputation: {features.current_reputation:.3f}")


def demo_anomaly_detection():
    """Demonstrate anomaly detection with models."""
    logger.info("\n" + "=" * 60)
    logger.info("ANOMALY DETECTION DEMO")
    logger.info("=" * 60)

    # Generate mock data
    trades, accounts = generate_mock_trades(200, anomaly_rate=0.15)
    deliveries, providers = generate_mock_deliveries(100, anomaly_rate=0.2)

    # Build trade history
    trade_history = {}
    for trade in trades:
        buyer = trade['buyer_id']
        if buyer not in trade_history:
            trade_history[buyer] = []
        trade_history[buyer].append(trade)

    # Initialize detector
    detector = AnomalyDetector()

    # Score some trades
    logger.info("\n--- Trade Anomaly Scoring ---")
    anomalous_trades = []

    for trade in trades[:30]:
        account_id = trade['account_id']
        history = trade_history.get(account_id, [])

        score = detector.score_trade(trade, history)

        if score.score > 0.5:
            anomalous_trades.append((trade, score))
            logger.info(f"Trade {trade['trade_id']}: score={score.score:.3f}, type={score.anomaly_type.name}")

    logger.info(f"\nFound {len(anomalous_trades)} anomalous trades out of 30 analyzed")

    # Score deliveries
    logger.info("\n--- Delivery Anomaly Scoring ---")
    anomalous_deliveries = []

    for delivery in deliveries[:30]:
        score = detector.score_delivery(delivery)

        if score.score > 0.5:
            anomalous_deliveries.append((delivery, score))
            discrepancy = delivery['claimed_energy_kwh'] - delivery['actual_energy_kwh']
            logger.info(
                f"Delivery {delivery['delivery_id']}: score={score.score:.3f}, "
                f"discrepancy={discrepancy:.1f} kWh"
            )

    logger.info(f"\nFound {len(anomalous_deliveries)} anomalous deliveries out of 30 analyzed")


def demo_alert_system():
    """Demonstrate alert system."""
    logger.info("\n" + "=" * 60)
    logger.info("ALERT SYSTEM DEMO")
    logger.info("=" * 60)

    # Setup alert system
    store = AlertStore()  # In-memory for demo
    alert_system = AlertSystem(
        store=store,
        handlers=[
            LoggingHandler("demo_logger"),
        ]
    )

    # Generate some anomaly scores
    test_anomalies = [
        ("WASH_TRADING", 0.95, "acc-001", "Critical wash trading"),
        ("PRICE_MANIPULATION", 0.85, "acc-002", "Price manipulation"),
        ("SPOOFING", 0.65, "acc-003", "Potential spoofing"),
        ("VOLUME_SPIKE", 0.55, "acc-004", "Volume spike"),
        ("FALSE_DELIVERY_CLAIM", 0.82, "del-001", "False delivery"),
        ("SYBIL_CLUSTER", 0.92, "network-001", "Sybil cluster"),
    ]

    logger.info("\nProcessing anomalies...")
    alerts_generated = []

    for anomaly_type, score, entity_id, description in test_anomalies:
        alert = alert_system.process_anomaly(
            anomaly_type=anomaly_type,
            score=score,
            entity_id=entity_id,
            entity_type="account" if entity_id.startswith("acc") else "delivery",
            details={'description': description},
        )

        if alert:
            alerts_generated.append(alert)
            logger.info(f"  Generated alert: {alert.alert_id} - {alert.severity.name}")
        else:
            logger.info(f"  No alert for {anomaly_type} (score={score:.2f})")

    # Get statistics
    logger.info("\n--- Alert Statistics ---")
    stats = alert_system.get_statistics()
    logger.info(f"Total alerts: {stats['total']}")
    logger.info(f"By severity: {stats.get('by_severity', {})}")
    logger.info(f"By category: {stats.get('by_category', {})}")

    # Get trending entities
    logger.info("\n--- Trending Entities ---")

    # Simulate multiple scores for same entity to create trend
    for _ in range(5):
        alert_system.process_anomaly(
            anomaly_type="WASH_TRADING",
            score=random.uniform(0.7, 0.9),
            entity_id="acc-001",
            entity_type="account",
        )

    trending = alert_system.get_trending_entities(
        window_hours=24,
        min_alerts=2,
        increasing_only=False,
    )

    for trend in trending[:3]:
        logger.info(f"Entity {trend['entity_id']}: {trend['count']} alerts, trend={trend['trend']}")


def demo_blockchain_monitoring():
    """Demonstrate blockchain event monitoring."""
    logger.info("\n" + "=" * 60)
    logger.info("BLOCKCHAIN MONITORING DEMO")
    logger.info("=" * 60)

    # Setup components
    detector = AnomalyDetector()
    alert_system = AlertSystem(handlers=[LoggingHandler("blockchain")])

    # Create mock event stream (no actual blockchain connection)
    event_stream = BlockchainEventStream(
        rpc_url="http://localhost:8545",  # Won't actually connect
        contract_addresses=["0x" + "0" * 40],
        poll_interval=1.0,
    )

    # Create monitor
    monitor = BlockchainAnomalyMonitor(
        event_stream=event_stream,
        anomaly_detector=detector,
        alert_system=alert_system,
    )

    logger.info("Starting blockchain monitor (mock mode)...")
    monitor.start()

    # Let it run for a few seconds
    for i in range(5):
        time.sleep(1)
        stats = monitor.get_statistics()
        logger.info(
            f"[{i+1}s] Events: {stats['events_processed']}, "
            f"Trades: {stats['trades_analyzed']}, "
            f"Anomalies: {stats['anomalies_detected']}"
        )

    monitor.stop()
    logger.info("Monitor stopped")

    # Final statistics
    final_stats = monitor.get_statistics()
    logger.info(f"\nFinal statistics: {final_stats}")


def main():
    parser = argparse.ArgumentParser(description="SHAKTI-CHAIN Anomaly Detection Demo")
    parser.add_argument(
        "--demo",
        choices=["features", "detection", "alerts", "blockchain", "all"],
        default="all",
        help="Which demo to run",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="demo_output",
        help="Directory for output files",
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("SHAKTI-CHAIN Anomaly Detection System")
    logger.info(f"Output directory: {output_dir}")
    logger.info("")

    if args.demo in ["features", "all"]:
        demo_feature_extraction()

    if args.demo in ["detection", "all"]:
        demo_anomaly_detection()

    if args.demo in ["alerts", "all"]:
        demo_alert_system()

    if args.demo in ["blockchain", "all"]:
        demo_blockchain_monitoring()

    logger.info("\n" + "=" * 60)
    logger.info("DEMO COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
