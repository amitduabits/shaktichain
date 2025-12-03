"""Blockchain event integration for real-time anomaly monitoring.

Provides:
- Real-time event streaming from blockchain
- Event parsing and normalization
- Integration with anomaly detection pipeline
- Transaction pattern analysis
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading
from queue import Queue
import time

logger = logging.getLogger(__name__)


class BlockchainEventType(Enum):
    """Types of blockchain events."""
    TRADE_EXECUTED = "trade_executed"
    TRADE_CANCELLED = "trade_cancelled"
    ORDER_PLACED = "order_placed"
    ORDER_CANCELLED = "order_cancelled"
    DELIVERY_COMMITTED = "delivery_committed"
    DELIVERY_CONFIRMED = "delivery_confirmed"
    DELIVERY_DISPUTED = "delivery_disputed"
    ACCOUNT_CREATED = "account_created"
    ACCOUNT_UPDATED = "account_updated"
    REPUTATION_CHANGED = "reputation_changed"
    PENALTY_APPLIED = "penalty_applied"
    REWARD_DISTRIBUTED = "reward_distributed"
    CONTRACT_DEPLOYED = "contract_deployed"
    CONTRACT_UPGRADED = "contract_upgraded"


@dataclass
class BlockchainEvent:
    """Normalized blockchain event."""
    event_id: str
    event_type: BlockchainEventType
    block_number: int
    block_timestamp: datetime
    transaction_hash: str
    contract_address: str
    emitter: str
    data: Dict[str, Any]
    raw_log: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'block_number': self.block_number,
            'block_timestamp': self.block_timestamp.isoformat(),
            'transaction_hash': self.transaction_hash,
            'contract_address': self.contract_address,
            'emitter': self.emitter,
            'data': self.data,
        }


@dataclass
class EventFilter:
    """Filter criteria for blockchain events."""
    event_types: Optional[List[BlockchainEventType]] = None
    contract_addresses: Optional[List[str]] = None
    emitters: Optional[List[str]] = None
    min_block: Optional[int] = None
    max_block: Optional[int] = None
    data_filters: Optional[Dict[str, Any]] = None

    def matches(self, event: BlockchainEvent) -> bool:
        """Check if event matches filter."""
        if self.event_types and event.event_type not in self.event_types:
            return False
        if self.contract_addresses and event.contract_address not in self.contract_addresses:
            return False
        if self.emitters and event.emitter not in self.emitters:
            return False
        if self.min_block and event.block_number < self.min_block:
            return False
        if self.max_block and event.block_number > self.max_block:
            return False
        if self.data_filters:
            for key, value in self.data_filters.items():
                if event.data.get(key) != value:
                    return False
        return True


class EventParser:
    """Parse raw blockchain events into normalized format."""

    # Event signature to type mapping
    EVENT_SIGNATURES = {
        "TradeExecuted": BlockchainEventType.TRADE_EXECUTED,
        "TradeCancelled": BlockchainEventType.TRADE_CANCELLED,
        "OrderPlaced": BlockchainEventType.ORDER_PLACED,
        "OrderCancelled": BlockchainEventType.ORDER_CANCELLED,
        "DeliveryCommitted": BlockchainEventType.DELIVERY_COMMITTED,
        "DeliveryConfirmed": BlockchainEventType.DELIVERY_CONFIRMED,
        "DeliveryDisputed": BlockchainEventType.DELIVERY_DISPUTED,
        "AccountCreated": BlockchainEventType.ACCOUNT_CREATED,
        "AccountUpdated": BlockchainEventType.ACCOUNT_UPDATED,
        "ReputationChanged": BlockchainEventType.REPUTATION_CHANGED,
        "PenaltyApplied": BlockchainEventType.PENALTY_APPLIED,
        "RewardDistributed": BlockchainEventType.REWARD_DISTRIBUTED,
    }

    def __init__(self):
        """Initialize parser."""
        self._event_counter = 0

    def parse(self, raw_event: Dict[str, Any]) -> Optional[BlockchainEvent]:
        """Parse raw event into normalized format.

        Args:
            raw_event: Raw event from blockchain

        Returns:
            Normalized BlockchainEvent or None if parsing fails
        """
        try:
            # Extract event name/signature
            event_name = raw_event.get('event', '')
            event_type = self.EVENT_SIGNATURES.get(event_name)

            if not event_type:
                logger.debug(f"Unknown event type: {event_name}")
                return None

            # Generate event ID
            self._event_counter += 1
            block_num = raw_event.get('blockNumber', 0)
            tx_hash = raw_event.get('transactionHash', '')
            log_index = raw_event.get('logIndex', 0)
            event_id = f"EVT-{block_num}-{log_index}-{self._event_counter}"

            # Parse timestamp
            timestamp = raw_event.get('blockTimestamp')
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            else:
                timestamp = datetime.now()

            # Extract data fields
            data = self._extract_data(event_type, raw_event)

            return BlockchainEvent(
                event_id=event_id,
                event_type=event_type,
                block_number=block_num,
                block_timestamp=timestamp,
                transaction_hash=tx_hash,
                contract_address=raw_event.get('address', ''),
                emitter=raw_event.get('args', {}).get('from', ''),
                data=data,
                raw_log=raw_event,
            )

        except Exception as e:
            logger.error(f"Failed to parse event: {e}")
            return None

    def _extract_data(
        self,
        event_type: BlockchainEventType,
        raw_event: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Extract relevant data fields based on event type."""
        args = raw_event.get('args', {})

        if event_type == BlockchainEventType.TRADE_EXECUTED:
            return {
                'trade_id': args.get('tradeId', ''),
                'buyer': args.get('buyer', ''),
                'seller': args.get('seller', ''),
                'price': float(args.get('price', 0)) / 1e18,  # Convert from wei
                'quantity': float(args.get('quantity', 0)),
                'energy_kwh': float(args.get('energyKwh', 0)),
                'trade_type': args.get('tradeType', 'spot'),
            }

        elif event_type == BlockchainEventType.ORDER_PLACED:
            return {
                'order_id': args.get('orderId', ''),
                'trader': args.get('trader', ''),
                'side': args.get('side', 'buy'),
                'price': float(args.get('price', 0)) / 1e18,
                'quantity': float(args.get('quantity', 0)),
                'expires_at': args.get('expiresAt', 0),
            }

        elif event_type == BlockchainEventType.ORDER_CANCELLED:
            return {
                'order_id': args.get('orderId', ''),
                'trader': args.get('trader', ''),
                'reason': args.get('reason', ''),
            }

        elif event_type == BlockchainEventType.DELIVERY_COMMITTED:
            return {
                'delivery_id': args.get('deliveryId', ''),
                'provider': args.get('provider', ''),
                'consumer': args.get('consumer', ''),
                'energy_kwh': float(args.get('energyKwh', 0)),
                'scheduled_time': args.get('scheduledTime', 0),
            }

        elif event_type == BlockchainEventType.DELIVERY_CONFIRMED:
            return {
                'delivery_id': args.get('deliveryId', ''),
                'actual_kwh': float(args.get('actualKwh', 0)),
                'meter_reading': args.get('meterReading', ''),
                'confirmed_by': args.get('confirmedBy', ''),
            }

        elif event_type == BlockchainEventType.DELIVERY_DISPUTED:
            return {
                'delivery_id': args.get('deliveryId', ''),
                'disputant': args.get('disputant', ''),
                'reason': args.get('reason', ''),
                'claimed_kwh': float(args.get('claimedKwh', 0)),
                'actual_kwh': float(args.get('actualKwh', 0)),
            }

        elif event_type == BlockchainEventType.ACCOUNT_CREATED:
            return {
                'account_id': args.get('accountId', ''),
                'owner': args.get('owner', ''),
                'account_type': args.get('accountType', ''),
                'initial_stake': float(args.get('initialStake', 0)) / 1e18,
            }

        elif event_type == BlockchainEventType.REPUTATION_CHANGED:
            return {
                'account_id': args.get('accountId', ''),
                'old_reputation': float(args.get('oldReputation', 0)) / 1e18,
                'new_reputation': float(args.get('newReputation', 0)) / 1e18,
                'reason': args.get('reason', ''),
            }

        elif event_type == BlockchainEventType.PENALTY_APPLIED:
            return {
                'account_id': args.get('accountId', ''),
                'penalty_amount': float(args.get('penaltyAmount', 0)) / 1e18,
                'reason': args.get('reason', ''),
                'related_tx': args.get('relatedTx', ''),
            }

        else:
            return dict(args)


class BlockchainEventStream:
    """Stream blockchain events in real-time."""

    def __init__(
        self,
        rpc_url: str,
        contract_addresses: List[str],
        start_block: Optional[int] = None,
        poll_interval: float = 2.0,
    ):
        """Initialize event stream.

        Args:
            rpc_url: JSON-RPC endpoint URL
            contract_addresses: Contract addresses to monitor
            start_block: Starting block number (None for latest)
            poll_interval: Seconds between polls
        """
        self.rpc_url = rpc_url
        self.contract_addresses = contract_addresses
        self.poll_interval = poll_interval

        self.parser = EventParser()
        self._current_block = start_block
        self._running = False
        self._event_queue: Queue = Queue()
        self._callbacks: List[Callable[[BlockchainEvent], None]] = []

        # Try to import web3
        self._has_web3 = False
        self._w3 = None
        try:
            from web3 import Web3
            self._w3 = Web3(Web3.HTTPProvider(rpc_url))
            self._has_web3 = True
        except ImportError:
            logger.warning("web3 not available, using mock event stream")

    def add_callback(self, callback: Callable[[BlockchainEvent], None]) -> None:
        """Add callback for new events."""
        self._callbacks.append(callback)

    def start(self) -> None:
        """Start the event stream in background thread."""
        if self._running:
            return

        self._running = True
        self._stream_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._stream_thread.start()
        logger.info("Blockchain event stream started")

    def stop(self) -> None:
        """Stop the event stream."""
        self._running = False
        if hasattr(self, '_stream_thread'):
            self._stream_thread.join(timeout=5)
        logger.info("Blockchain event stream stopped")

    def _poll_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                events = self._fetch_events()
                for event in events:
                    self._event_queue.put(event)
                    for callback in self._callbacks:
                        try:
                            callback(event)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")
            except Exception as e:
                logger.error(f"Poll error: {e}")

            time.sleep(self.poll_interval)

    def _fetch_events(self) -> List[BlockchainEvent]:
        """Fetch new events from blockchain."""
        if not self._has_web3 or not self._w3:
            return self._mock_events()

        try:
            # Get latest block
            latest_block = self._w3.eth.block_number

            if self._current_block is None:
                self._current_block = latest_block - 10  # Start from recent blocks

            if self._current_block >= latest_block:
                return []

            # Fetch logs
            events = []
            for address in self.contract_addresses:
                logs = self._w3.eth.get_logs({
                    'fromBlock': self._current_block,
                    'toBlock': latest_block,
                    'address': address,
                })

                for log in logs:
                    # Convert to dict and parse
                    raw_event = dict(log)
                    raw_event['blockTimestamp'] = self._w3.eth.get_block(
                        log['blockNumber']
                    )['timestamp']

                    event = self.parser.parse(raw_event)
                    if event:
                        events.append(event)

            self._current_block = latest_block + 1
            return events

        except Exception as e:
            logger.error(f"Failed to fetch events: {e}")
            return []

    def _mock_events(self) -> List[BlockchainEvent]:
        """Generate mock events for testing."""
        import random

        # Occasionally generate mock events
        if random.random() > 0.3:
            return []

        event_types = [
            BlockchainEventType.TRADE_EXECUTED,
            BlockchainEventType.ORDER_PLACED,
            BlockchainEventType.DELIVERY_CONFIRMED,
        ]

        event_type = random.choice(event_types)

        if event_type == BlockchainEventType.TRADE_EXECUTED:
            data = {
                'trade_id': f"TRADE-{random.randint(1000, 9999)}",
                'buyer': f"0x{random.randbytes(20).hex()}",
                'seller': f"0x{random.randbytes(20).hex()}",
                'price': random.uniform(0.05, 0.20),
                'quantity': random.uniform(1, 100),
                'energy_kwh': random.uniform(10, 500),
            }
        elif event_type == BlockchainEventType.ORDER_PLACED:
            data = {
                'order_id': f"ORDER-{random.randint(1000, 9999)}",
                'trader': f"0x{random.randbytes(20).hex()}",
                'side': random.choice(['buy', 'sell']),
                'price': random.uniform(0.05, 0.20),
                'quantity': random.uniform(1, 100),
            }
        else:
            data = {
                'delivery_id': f"DEL-{random.randint(1000, 9999)}",
                'actual_kwh': random.uniform(10, 500),
            }

        self._current_block = (self._current_block or 0) + 1

        return [BlockchainEvent(
            event_id=f"EVT-{self._current_block}-0-1",
            event_type=event_type,
            block_number=self._current_block,
            block_timestamp=datetime.now(),
            transaction_hash=f"0x{random.randbytes(32).hex()}",
            contract_address=random.choice(self.contract_addresses) if self.contract_addresses else "0x0",
            emitter=data.get('buyer', data.get('trader', '')),
            data=data,
        )]

    def get_events(self, timeout: float = 0.1) -> List[BlockchainEvent]:
        """Get queued events without blocking.

        Args:
            timeout: Max time to wait

        Returns:
            List of events
        """
        events = []
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                event = self._event_queue.get_nowait()
                events.append(event)
            except:
                break

        return events


class BlockchainAnomalyMonitor:
    """Real-time anomaly monitoring for blockchain events."""

    def __init__(
        self,
        event_stream: BlockchainEventStream,
        anomaly_detector: Any,  # AnomalyDetector instance
        alert_system: Any,  # AlertSystem instance
    ):
        """Initialize monitor.

        Args:
            event_stream: Blockchain event stream
            anomaly_detector: Anomaly detection system
            alert_system: Alert system for notifications
        """
        self.event_stream = event_stream
        self.detector = anomaly_detector
        self.alert_system = alert_system

        # Event buffers for pattern analysis
        self.trade_buffer: List[Dict] = []
        self.order_buffer: List[Dict] = []
        self.delivery_buffer: List[Dict] = []
        self.account_activity: Dict[str, List[Dict]] = defaultdict(list)

        # Configuration
        self.buffer_size = 1000
        self.analysis_interval = 60  # seconds

        # Statistics
        self.stats = {
            'events_processed': 0,
            'trades_analyzed': 0,
            'anomalies_detected': 0,
            'alerts_generated': 0,
        }

        # Register callback
        self.event_stream.add_callback(self._on_event)

    def start(self) -> None:
        """Start monitoring."""
        self.event_stream.start()
        self._analysis_thread = threading.Thread(
            target=self._periodic_analysis,
            daemon=True,
        )
        self._running = True
        self._analysis_thread.start()
        logger.info("Blockchain anomaly monitor started")

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        self.event_stream.stop()
        logger.info("Blockchain anomaly monitor stopped")

    def _on_event(self, event: BlockchainEvent) -> None:
        """Handle incoming blockchain event."""
        self.stats['events_processed'] += 1

        # Route to appropriate buffer
        if event.event_type == BlockchainEventType.TRADE_EXECUTED:
            self._handle_trade(event)
        elif event.event_type in [BlockchainEventType.ORDER_PLACED, BlockchainEventType.ORDER_CANCELLED]:
            self._handle_order(event)
        elif event.event_type in [BlockchainEventType.DELIVERY_COMMITTED, BlockchainEventType.DELIVERY_CONFIRMED]:
            self._handle_delivery(event)
        elif event.event_type in [BlockchainEventType.ACCOUNT_CREATED, BlockchainEventType.REPUTATION_CHANGED]:
            self._handle_account(event)

    def _handle_trade(self, event: BlockchainEvent) -> None:
        """Process trade event."""
        trade_data = {
            'trade_id': event.data.get('trade_id'),
            'buyer_id': event.data.get('buyer'),
            'seller_id': event.data.get('seller'),
            'price': event.data.get('price', 0),
            'quantity': event.data.get('quantity', 0),
            'timestamp': event.block_timestamp,
            'tx_hash': event.transaction_hash,
        }

        self.trade_buffer.append(trade_data)
        if len(self.trade_buffer) > self.buffer_size:
            self.trade_buffer = self.trade_buffer[-self.buffer_size:]

        # Track per-account activity
        for account_id in [trade_data['buyer_id'], trade_data['seller_id']]:
            if account_id:
                self.account_activity[account_id].append({
                    'type': 'trade',
                    'data': trade_data,
                    'timestamp': event.block_timestamp,
                })

        # Real-time analysis for high-frequency patterns
        self._check_rapid_trading(trade_data)

        self.stats['trades_analyzed'] += 1

    def _handle_order(self, event: BlockchainEvent) -> None:
        """Process order event."""
        order_data = {
            'order_id': event.data.get('order_id'),
            'trader': event.data.get('trader'),
            'side': event.data.get('side'),
            'price': event.data.get('price', 0),
            'quantity': event.data.get('quantity', 0),
            'timestamp': event.block_timestamp,
            'cancelled': event.event_type == BlockchainEventType.ORDER_CANCELLED,
        }

        self.order_buffer.append(order_data)
        if len(self.order_buffer) > self.buffer_size:
            self.order_buffer = self.order_buffer[-self.buffer_size:]

        # Track for spoofing detection
        if order_data['cancelled']:
            self._check_spoofing_pattern(order_data)

    def _handle_delivery(self, event: BlockchainEvent) -> None:
        """Process delivery event."""
        delivery_data = {
            'delivery_id': event.data.get('delivery_id'),
            'provider': event.data.get('provider'),
            'consumer': event.data.get('consumer'),
            'energy_kwh': event.data.get('energy_kwh', 0),
            'actual_kwh': event.data.get('actual_kwh'),
            'timestamp': event.block_timestamp,
            'confirmed': event.event_type == BlockchainEventType.DELIVERY_CONFIRMED,
        }

        self.delivery_buffer.append(delivery_data)
        if len(self.delivery_buffer) > self.buffer_size:
            self.delivery_buffer = self.delivery_buffer[-self.buffer_size:]

        # Check for delivery discrepancies
        if delivery_data['confirmed'] and delivery_data['actual_kwh'] is not None:
            self._check_delivery_discrepancy(delivery_data)

    def _handle_account(self, event: BlockchainEvent) -> None:
        """Process account event."""
        account_id = event.data.get('account_id')
        if not account_id:
            return

        self.account_activity[account_id].append({
            'type': 'account_event',
            'event_type': event.event_type.value,
            'data': event.data,
            'timestamp': event.block_timestamp,
        })

        # Check for rapid reputation changes
        if event.event_type == BlockchainEventType.REPUTATION_CHANGED:
            self._check_reputation_manipulation(event.data)

    def _check_rapid_trading(self, trade: Dict) -> None:
        """Check for suspiciously rapid trading patterns."""
        # Get recent trades for this buyer/seller pair
        buyer = trade.get('buyer_id')
        seller = trade.get('seller_id')

        if not buyer or not seller:
            return

        recent_cutoff = trade['timestamp'] - timedelta(minutes=5)
        pair_trades = [
            t for t in self.trade_buffer[-100:]
            if t.get('timestamp', datetime.min) >= recent_cutoff
            and ((t.get('buyer_id') == buyer and t.get('seller_id') == seller)
                 or (t.get('buyer_id') == seller and t.get('seller_id') == buyer))
        ]

        if len(pair_trades) >= 5:
            # Potential wash trading
            score = min(1.0, len(pair_trades) / 10)
            self._generate_alert(
                anomaly_type="WASH_TRADING",
                score=score,
                entity_id=buyer,
                entity_type="account",
                details={
                    'pair_trades_5min': len(pair_trades),
                    'counterparty': seller,
                    'total_volume': sum(t.get('quantity', 0) for t in pair_trades),
                },
            )

    def _check_spoofing_pattern(self, order: Dict) -> None:
        """Check for order spoofing patterns."""
        trader = order.get('trader')
        if not trader:
            return

        # Get recent orders for this trader
        recent_cutoff = order['timestamp'] - timedelta(minutes=10)
        trader_orders = [
            o for o in self.order_buffer[-200:]
            if o.get('timestamp', datetime.min) >= recent_cutoff
            and o.get('trader') == trader
        ]

        cancelled = sum(1 for o in trader_orders if o.get('cancelled'))
        total = len(trader_orders)

        if total >= 5 and cancelled / total > 0.8:
            score = min(1.0, (cancelled / total) * (total / 10))
            self._generate_alert(
                anomaly_type="SPOOFING",
                score=score,
                entity_id=trader,
                entity_type="account",
                details={
                    'orders_10min': total,
                    'cancelled': cancelled,
                    'cancel_rate': cancelled / total,
                },
            )

    def _check_delivery_discrepancy(self, delivery: Dict) -> None:
        """Check for energy delivery discrepancies."""
        claimed = delivery.get('energy_kwh', 0)
        actual = delivery.get('actual_kwh', claimed)

        if claimed <= 0:
            return

        discrepancy_pct = abs(claimed - actual) / claimed

        if discrepancy_pct > 0.2:  # More than 20% discrepancy
            score = min(1.0, discrepancy_pct)
            self._generate_alert(
                anomaly_type="ENERGY_ACCOUNTING_DISCREPANCY",
                score=score,
                entity_id=delivery.get('delivery_id', ''),
                entity_type="delivery",
                details={
                    'claimed_kwh': claimed,
                    'actual_kwh': actual,
                    'discrepancy_pct': discrepancy_pct * 100,
                    'provider': delivery.get('provider'),
                },
            )

    def _check_reputation_manipulation(self, data: Dict) -> None:
        """Check for reputation manipulation patterns."""
        account_id = data.get('account_id')
        old_rep = data.get('old_reputation', 0)
        new_rep = data.get('new_reputation', 0)

        if old_rep <= 0:
            return

        change_pct = (new_rep - old_rep) / old_rep

        # Suspiciously large reputation jump
        if change_pct > 0.5:  # More than 50% increase
            # Check for coordinated activity
            recent_activity = self.account_activity.get(account_id, [])
            recent = [a for a in recent_activity
                     if a.get('timestamp', datetime.min) >= datetime.now() - timedelta(hours=24)]

            if len(recent) > 20:  # High activity
                score = min(1.0, change_pct * len(recent) / 50)
                self._generate_alert(
                    anomaly_type="REPUTATION_MANIPULATION",
                    score=score,
                    entity_id=account_id,
                    entity_type="account",
                    details={
                        'old_reputation': old_rep,
                        'new_reputation': new_rep,
                        'change_pct': change_pct * 100,
                        'recent_activity_count': len(recent),
                    },
                )

    def _generate_alert(
        self,
        anomaly_type: str,
        score: float,
        entity_id: str,
        entity_type: str,
        details: Dict,
    ) -> None:
        """Generate alert through alert system."""
        self.stats['anomalies_detected'] += 1

        if self.alert_system:
            alert = self.alert_system.process_anomaly(
                anomaly_type=anomaly_type,
                score=score,
                entity_id=entity_id,
                entity_type=entity_type,
                details=details,
            )
            if alert:
                self.stats['alerts_generated'] += 1

    def _periodic_analysis(self) -> None:
        """Run periodic batch analysis on buffered events."""
        while self._running:
            time.sleep(self.analysis_interval)

            try:
                # Analyze trade patterns
                self._analyze_trade_patterns()

                # Analyze network patterns
                self._analyze_network_patterns()

                # Clean up old activity data
                self._cleanup_activity()

            except Exception as e:
                logger.error(f"Periodic analysis error: {e}")

    def _analyze_trade_patterns(self) -> None:
        """Batch analyze recent trades for patterns."""
        if len(self.trade_buffer) < 10:
            return

        # Look for coordinated trading
        price_times = defaultdict(list)
        for trade in self.trade_buffer[-100:]:
            price = round(trade.get('price', 0), 4)
            price_times[price].append(trade['timestamp'])

        # Check for price clustering
        for price, times in price_times.items():
            if len(times) >= 5:
                time_diffs = []
                sorted_times = sorted(times)
                for i in range(1, len(sorted_times)):
                    diff = (sorted_times[i] - sorted_times[i-1]).total_seconds()
                    time_diffs.append(diff)

                if time_diffs and max(time_diffs) < 60:  # All within 60 seconds
                    # Potential coordinated trading
                    traders = set()
                    for trade in self.trade_buffer[-100:]:
                        if round(trade.get('price', 0), 4) == price:
                            traders.add(trade.get('buyer_id'))
                            traders.add(trade.get('seller_id'))

                    if len(traders) >= 3:
                        self._generate_alert(
                            anomaly_type="COORDINATED_TRADING",
                            score=min(1.0, len(traders) / 10),
                            entity_id=f"price_{price}",
                            entity_type="pattern",
                            details={
                                'price': price,
                                'trade_count': len(times),
                                'unique_traders': len(traders),
                                'time_span_seconds': (max(times) - min(times)).total_seconds(),
                            },
                        )

    def _analyze_network_patterns(self) -> None:
        """Analyze trading network for suspicious patterns."""
        # Build adjacency from recent trades
        edges = defaultdict(int)
        for trade in self.trade_buffer[-500:]:
            buyer = trade.get('buyer_id')
            seller = trade.get('seller_id')
            if buyer and seller:
                edge = tuple(sorted([buyer, seller]))
                edges[edge] += 1

        # Look for dense clusters
        high_frequency_pairs = [
            (pair, count) for pair, count in edges.items()
            if count >= 10
        ]

        if len(high_frequency_pairs) >= 3:
            # Check if they share nodes
            nodes = set()
            for pair, _ in high_frequency_pairs:
                nodes.update(pair)

            if len(nodes) <= len(high_frequency_pairs) + 2:
                # Tight cluster - potential collusion
                total_trades = sum(c for _, c in high_frequency_pairs)
                self._generate_alert(
                    anomaly_type="COORDINATED_TRADING",
                    score=min(1.0, total_trades / 50),
                    entity_id=f"cluster_{len(nodes)}",
                    entity_type="network",
                    details={
                        'cluster_size': len(nodes),
                        'high_freq_pairs': len(high_frequency_pairs),
                        'total_trades': total_trades,
                    },
                )

    def _cleanup_activity(self) -> None:
        """Clean up old activity data."""
        cutoff = datetime.now() - timedelta(hours=24)

        for account_id in list(self.account_activity.keys()):
            self.account_activity[account_id] = [
                a for a in self.account_activity[account_id]
                if a.get('timestamp', datetime.min) >= cutoff
            ]

            if not self.account_activity[account_id]:
                del self.account_activity[account_id]

    def get_statistics(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            **self.stats,
            'buffer_sizes': {
                'trades': len(self.trade_buffer),
                'orders': len(self.order_buffer),
                'deliveries': len(self.delivery_buffer),
                'accounts_tracked': len(self.account_activity),
            },
        }
