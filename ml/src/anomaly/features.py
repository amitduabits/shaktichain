"""Feature extractors for anomaly detection.

Provides specialized feature extraction for:
- Trading patterns (wash trading, manipulation, spoofing)
- Delivery verification (false claims, discrepancies)
- Account behavior (reputation gaming, Sybil detection)
- Graph/network features (coordinated behavior)
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class TradeFeatures:
    """Features extracted from a single trade."""
    # Basic features
    price: float
    quantity: float
    timestamp: datetime

    # Price features
    price_deviation_from_mean: float
    price_deviation_from_median: float
    price_zscore: float
    price_percentile: float

    # Volume features
    volume_deviation: float
    volume_zscore: float
    volume_percentile: float

    # Timing features
    time_since_last_trade: float
    trades_in_last_minute: int
    trades_in_last_hour: int
    hour_of_day: int
    day_of_week: int

    # Counterparty features
    same_counterparty_ratio: float
    unique_counterparties_24h: int

    # Sequence features
    consecutive_same_direction: int
    price_momentum: float
    volume_trend: float

    # Wash trading indicators
    round_trip_detected: bool
    self_trade_indicator: float
    circular_trade_indicator: float

    def to_array(self) -> np.ndarray:
        """Convert to numpy array for ML models."""
        return np.array([
            self.price,
            self.quantity,
            self.price_deviation_from_mean,
            self.price_deviation_from_median,
            self.price_zscore,
            self.price_percentile,
            self.volume_deviation,
            self.volume_zscore,
            self.volume_percentile,
            self.time_since_last_trade,
            self.trades_in_last_minute,
            self.trades_in_last_hour,
            self.hour_of_day,
            self.day_of_week,
            self.same_counterparty_ratio,
            self.unique_counterparties_24h,
            self.consecutive_same_direction,
            self.price_momentum,
            self.volume_trend,
            float(self.round_trip_detected),
            self.self_trade_indicator,
            self.circular_trade_indicator,
        ])


@dataclass
class DeliveryFeatures:
    """Features extracted from energy delivery claims."""
    # Basic features
    claimed_energy_kwh: float
    actual_energy_kwh: float
    delivery_duration_minutes: float

    # Discrepancy features
    energy_discrepancy: float
    energy_discrepancy_pct: float
    discrepancy_zscore: float

    # Timing features
    delivery_time_deviation: float
    expected_vs_actual_duration: float

    # Historical features
    historical_accuracy: float
    delivery_success_rate: float
    avg_discrepancy_30d: float

    # Pattern features
    consistent_overdelivery: bool
    consistent_underdelivery: bool
    discrepancy_trend: float

    # Physical feasibility
    power_rate_kw: float
    is_physically_feasible: bool
    efficiency_ratio: float

    def to_array(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array([
            self.claimed_energy_kwh,
            self.actual_energy_kwh,
            self.delivery_duration_minutes,
            self.energy_discrepancy,
            self.energy_discrepancy_pct,
            self.discrepancy_zscore,
            self.delivery_time_deviation,
            self.expected_vs_actual_duration,
            self.historical_accuracy,
            self.delivery_success_rate,
            self.avg_discrepancy_30d,
            float(self.consistent_overdelivery),
            float(self.consistent_underdelivery),
            self.discrepancy_trend,
            self.power_rate_kw,
            float(self.is_physically_feasible),
            self.efficiency_ratio,
        ])


@dataclass
class AccountFeatures:
    """Features extracted from account behavior."""
    # Basic features
    account_age_days: float
    total_trades: int
    total_volume: float

    # Activity features
    avg_trades_per_day: float
    trade_frequency_variance: float
    active_hours_count: int

    # Reputation features
    current_reputation: float
    reputation_change_30d: float
    reputation_volatility: float
    positive_feedback_ratio: float

    # Network features
    unique_counterparties: int
    counterparty_concentration: float
    avg_counterparty_reputation: float

    # Behavioral features
    avg_trade_size: float
    trade_size_variance: float
    preferred_trading_hours: List[int]
    weekend_activity_ratio: float

    # Risk indicators
    failed_delivery_rate: float
    dispute_rate: float
    suspicious_pattern_count: int

    def to_array(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array([
            self.account_age_days,
            self.total_trades,
            self.total_volume,
            self.avg_trades_per_day,
            self.trade_frequency_variance,
            self.active_hours_count,
            self.current_reputation,
            self.reputation_change_30d,
            self.reputation_volatility,
            self.positive_feedback_ratio,
            self.unique_counterparties,
            self.counterparty_concentration,
            self.avg_counterparty_reputation,
            self.avg_trade_size,
            self.trade_size_variance,
            len(self.preferred_trading_hours),
            self.weekend_activity_ratio,
            self.failed_delivery_rate,
            self.dispute_rate,
            self.suspicious_pattern_count,
        ])


@dataclass
class GraphFeatures:
    """Features extracted from network/graph analysis."""
    # Node features
    degree_centrality: float
    betweenness_centrality: float
    clustering_coefficient: float
    pagerank: float

    # Community features
    community_id: int
    community_size: int
    intra_community_ratio: float

    # Structural features
    avg_neighbor_degree: float
    neighbor_reputation_variance: float

    # Temporal graph features
    edge_creation_rate: float
    new_connection_ratio_7d: float

    # Sybil indicators
    similar_behavior_neighbors: int
    registration_time_clustering: float
    shared_attribute_score: float

    def to_array(self) -> np.ndarray:
        """Convert to numpy array."""
        return np.array([
            self.degree_centrality,
            self.betweenness_centrality,
            self.clustering_coefficient,
            self.pagerank,
            self.community_id,
            self.community_size,
            self.intra_community_ratio,
            self.avg_neighbor_degree,
            self.neighbor_reputation_variance,
            self.edge_creation_rate,
            self.new_connection_ratio_7d,
            self.similar_behavior_neighbors,
            self.registration_time_clustering,
            self.shared_attribute_score,
        ])


class TradingFeatureExtractor:
    """Extract features from trading data for anomaly detection."""

    def __init__(
        self,
        lookback_minutes: int = 60,
        lookback_hours: int = 24,
        price_history_size: int = 1000,
    ):
        """Initialize feature extractor.

        Args:
            lookback_minutes: Minutes to look back for short-term features
            lookback_hours: Hours to look back for medium-term features
            price_history_size: Number of prices to keep for statistics
        """
        self.lookback_minutes = lookback_minutes
        self.lookback_hours = lookback_hours
        self.price_history_size = price_history_size

        # Rolling statistics
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.trade_times: List[datetime] = []

    def extract(
        self,
        trade: Dict[str, Any],
        account_history: Optional[List[Dict]] = None,
        market_context: Optional[Dict] = None,
    ) -> TradeFeatures:
        """Extract features from a trade.

        Args:
            trade: Trade dictionary with price, quantity, timestamp, etc.
            account_history: Historical trades for the account
            market_context: Current market state

        Returns:
            TradeFeatures dataclass
        """
        price = float(trade.get('price', 0))
        quantity = float(trade.get('quantity', 0))
        timestamp = trade.get('timestamp', datetime.now())
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        # Update history
        self.price_history.append(price)
        self.volume_history.append(quantity)
        self.trade_times.append(timestamp)

        # Trim history
        if len(self.price_history) > self.price_history_size:
            self.price_history = self.price_history[-self.price_history_size:]
            self.volume_history = self.volume_history[-self.price_history_size:]
            self.trade_times = self.trade_times[-self.price_history_size:]

        # Calculate price features
        prices_arr = np.array(self.price_history)
        price_mean = np.mean(prices_arr) if len(prices_arr) > 0 else price
        price_median = np.median(prices_arr) if len(prices_arr) > 0 else price
        price_std = np.std(prices_arr) if len(prices_arr) > 1 else 1.0

        price_deviation_from_mean = price - price_mean
        price_deviation_from_median = price - price_median
        price_zscore = (price - price_mean) / (price_std + 1e-8)
        price_percentile = np.mean(prices_arr <= price) * 100 if len(prices_arr) > 0 else 50.0

        # Volume features
        volumes_arr = np.array(self.volume_history)
        volume_mean = np.mean(volumes_arr) if len(volumes_arr) > 0 else quantity
        volume_std = np.std(volumes_arr) if len(volumes_arr) > 1 else 1.0

        volume_deviation = quantity - volume_mean
        volume_zscore = (quantity - volume_mean) / (volume_std + 1e-8)
        volume_percentile = np.mean(volumes_arr <= quantity) * 100 if len(volumes_arr) > 0 else 50.0

        # Timing features
        time_since_last = 0.0
        if len(self.trade_times) > 1:
            time_since_last = (timestamp - self.trade_times[-2]).total_seconds()

        cutoff_minute = timestamp - timedelta(minutes=1)
        cutoff_hour = timestamp - timedelta(hours=1)
        trades_in_last_minute = sum(1 for t in self.trade_times if t >= cutoff_minute)
        trades_in_last_hour = sum(1 for t in self.trade_times if t >= cutoff_hour)

        hour_of_day = timestamp.hour
        day_of_week = timestamp.weekday()

        # Counterparty features
        same_counterparty_ratio = 0.0
        unique_counterparties_24h = 0
        if account_history:
            counterparty = trade.get('counterparty')
            cutoff_24h = timestamp - timedelta(hours=24)
            recent_trades = [t for t in account_history if t.get('timestamp', datetime.min) >= cutoff_24h]

            if recent_trades:
                same_party = sum(1 for t in recent_trades if t.get('counterparty') == counterparty)
                same_counterparty_ratio = same_party / len(recent_trades)
                unique_counterparties_24h = len(set(t.get('counterparty') for t in recent_trades))

        # Sequence features
        consecutive_same_direction = self._count_consecutive_direction(trade, account_history)
        price_momentum = self._calculate_momentum(prices_arr)
        volume_trend = self._calculate_trend(volumes_arr)

        # Wash trading indicators
        round_trip = self._detect_round_trip(trade, account_history)
        self_trade = self._calculate_self_trade_indicator(trade)
        circular = self._calculate_circular_indicator(trade, account_history)

        return TradeFeatures(
            price=price,
            quantity=quantity,
            timestamp=timestamp,
            price_deviation_from_mean=price_deviation_from_mean,
            price_deviation_from_median=price_deviation_from_median,
            price_zscore=price_zscore,
            price_percentile=price_percentile,
            volume_deviation=volume_deviation,
            volume_zscore=volume_zscore,
            volume_percentile=volume_percentile,
            time_since_last_trade=time_since_last,
            trades_in_last_minute=trades_in_last_minute,
            trades_in_last_hour=trades_in_last_hour,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            same_counterparty_ratio=same_counterparty_ratio,
            unique_counterparties_24h=unique_counterparties_24h,
            consecutive_same_direction=consecutive_same_direction,
            price_momentum=price_momentum,
            volume_trend=volume_trend,
            round_trip_detected=round_trip,
            self_trade_indicator=self_trade,
            circular_trade_indicator=circular,
        )

    def _count_consecutive_direction(
        self,
        trade: Dict,
        history: Optional[List[Dict]],
    ) -> int:
        """Count consecutive trades in same direction."""
        if not history or len(history) < 2:
            return 1

        direction = trade.get('side', 'buy')
        count = 1

        for t in reversed(history[-10:]):
            if t.get('side') == direction:
                count += 1
            else:
                break

        return count

    def _calculate_momentum(self, prices: np.ndarray, window: int = 10) -> float:
        """Calculate price momentum."""
        if len(prices) < window:
            return 0.0

        recent = prices[-window:]
        return (recent[-1] - recent[0]) / (recent[0] + 1e-8)

    def _calculate_trend(self, values: np.ndarray, window: int = 10) -> float:
        """Calculate trend using linear regression slope."""
        if len(values) < window:
            return 0.0

        recent = values[-window:]
        x = np.arange(len(recent))

        # Simple linear regression
        slope = np.polyfit(x, recent, 1)[0]
        return slope

    def _detect_round_trip(
        self,
        trade: Dict,
        history: Optional[List[Dict]],
    ) -> bool:
        """Detect potential round-trip trades (buy then sell same amount)."""
        if not history:
            return False

        quantity = trade.get('quantity', 0)
        side = trade.get('side', 'buy')
        timestamp = trade.get('timestamp', datetime.now())

        # Look for opposite trade with same quantity in last hour
        opposite = 'sell' if side == 'buy' else 'buy'
        cutoff = timestamp - timedelta(hours=1)

        for t in history:
            t_time = t.get('timestamp', datetime.min)
            if t_time >= cutoff:
                if t.get('side') == opposite and abs(t.get('quantity', 0) - quantity) < 0.01:
                    return True

        return False

    def _calculate_self_trade_indicator(self, trade: Dict) -> float:
        """Calculate indicator for self-trading (same buyer/seller)."""
        buyer = trade.get('buyer_id', '')
        seller = trade.get('seller_id', '')

        if buyer and seller and buyer == seller:
            return 1.0

        # Check for related accounts (simplified)
        return 0.0

    def _calculate_circular_indicator(
        self,
        trade: Dict,
        history: Optional[List[Dict]],
    ) -> float:
        """Calculate indicator for circular trading patterns."""
        if not history or len(history) < 3:
            return 0.0

        # Build simple graph of recent trades
        counterparties = defaultdict(set)
        account = trade.get('account_id', '')

        for t in history[-50:]:
            a = t.get('buyer_id', '')
            b = t.get('seller_id', '')
            if a and b:
                counterparties[a].add(b)
                counterparties[b].add(a)

        # Check for circular patterns (A->B->C->A)
        current_counterparty = trade.get('counterparty', '')
        if not current_counterparty:
            return 0.0

        # Simple check: does counterparty trade with anyone who trades back with us?
        for intermediate in counterparties.get(current_counterparty, []):
            if account in counterparties.get(intermediate, []):
                return 0.5

        return 0.0

    def extract_batch(
        self,
        trades: List[Dict],
        account_histories: Optional[Dict[str, List[Dict]]] = None,
    ) -> np.ndarray:
        """Extract features for multiple trades.

        Args:
            trades: List of trade dictionaries
            account_histories: Dict mapping account_id to trade history

        Returns:
            Feature matrix (n_trades, n_features)
        """
        features = []

        for trade in trades:
            account_id = trade.get('account_id', '')
            history = account_histories.get(account_id) if account_histories else None

            trade_features = self.extract(trade, history)
            features.append(trade_features.to_array())

        return np.array(features)


class DeliveryFeatureExtractor:
    """Extract features from energy delivery data."""

    def __init__(
        self,
        max_power_kw: float = 350.0,  # Max DC fast charging
        efficiency_range: Tuple[float, float] = (0.85, 0.98),
    ):
        """Initialize extractor.

        Args:
            max_power_kw: Maximum physically possible power rate
            efficiency_range: Expected efficiency range
        """
        self.max_power_kw = max_power_kw
        self.efficiency_range = efficiency_range
        self.delivery_history: List[Dict] = []

    def extract(
        self,
        delivery: Dict[str, Any],
        meter_data: Optional[Dict] = None,
        historical_deliveries: Optional[List[Dict]] = None,
    ) -> DeliveryFeatures:
        """Extract features from a delivery claim.

        Args:
            delivery: Delivery claim data
            meter_data: Smart meter readings
            historical_deliveries: Past deliveries for this account

        Returns:
            DeliveryFeatures dataclass
        """
        claimed = float(delivery.get('claimed_energy_kwh', 0))
        actual = float(delivery.get('actual_energy_kwh', claimed))
        if meter_data:
            actual = float(meter_data.get('measured_kwh', actual))

        duration = float(delivery.get('duration_minutes', 60))

        # Discrepancy features
        discrepancy = claimed - actual
        discrepancy_pct = discrepancy / (actual + 1e-8) * 100

        # Historical stats
        discrepancy_zscore = 0.0
        historical_accuracy = 1.0
        success_rate = 1.0
        avg_discrepancy_30d = 0.0
        consistent_over = False
        consistent_under = False
        discrepancy_trend = 0.0

        if historical_deliveries:
            historical_discrepancies = []
            for d in historical_deliveries:
                h_claimed = d.get('claimed_energy_kwh', 0)
                h_actual = d.get('actual_energy_kwh', h_claimed)
                historical_discrepancies.append(h_claimed - h_actual)

            if historical_discrepancies:
                hist_arr = np.array(historical_discrepancies)
                hist_mean = np.mean(hist_arr)
                hist_std = np.std(hist_arr) if len(hist_arr) > 1 else 1.0

                discrepancy_zscore = (discrepancy - hist_mean) / (hist_std + 1e-8)
                avg_discrepancy_30d = hist_mean

                # Accuracy and success rate
                successful = sum(1 for d in hist_arr if abs(d) < 0.1 * claimed)
                success_rate = successful / len(hist_arr)
                historical_accuracy = 1 - np.mean(np.abs(hist_arr)) / (claimed + 1e-8)

                # Patterns
                consistent_over = np.all(hist_arr > 0)
                consistent_under = np.all(hist_arr < 0)

                if len(hist_arr) >= 5:
                    discrepancy_trend = np.polyfit(np.arange(len(hist_arr)), hist_arr, 1)[0]

        # Timing features
        expected_duration = delivery.get('expected_duration_minutes', duration)
        delivery_time_deviation = duration - expected_duration
        expected_vs_actual = duration / (expected_duration + 1e-8)

        # Physical feasibility
        power_rate = (claimed * 60) / (duration + 1e-8)  # kW
        is_feasible = power_rate <= self.max_power_kw

        efficiency = actual / (claimed + 1e-8)
        efficiency_ratio = efficiency

        return DeliveryFeatures(
            claimed_energy_kwh=claimed,
            actual_energy_kwh=actual,
            delivery_duration_minutes=duration,
            energy_discrepancy=discrepancy,
            energy_discrepancy_pct=discrepancy_pct,
            discrepancy_zscore=discrepancy_zscore,
            delivery_time_deviation=delivery_time_deviation,
            expected_vs_actual_duration=expected_vs_actual,
            historical_accuracy=historical_accuracy,
            delivery_success_rate=success_rate,
            avg_discrepancy_30d=avg_discrepancy_30d,
            consistent_overdelivery=consistent_over,
            consistent_underdelivery=consistent_under,
            discrepancy_trend=discrepancy_trend,
            power_rate_kw=power_rate,
            is_physically_feasible=is_feasible,
            efficiency_ratio=efficiency_ratio,
        )

    def extract_batch(
        self,
        deliveries: List[Dict],
        meter_data_map: Optional[Dict[str, Dict]] = None,
        historical_map: Optional[Dict[str, List[Dict]]] = None,
    ) -> np.ndarray:
        """Extract features for multiple deliveries."""
        features = []

        for delivery in deliveries:
            delivery_id = delivery.get('delivery_id', '')
            account_id = delivery.get('account_id', '')

            meter = meter_data_map.get(delivery_id) if meter_data_map else None
            history = historical_map.get(account_id) if historical_map else None

            feat = self.extract(delivery, meter, history)
            features.append(feat.to_array())

        return np.array(features)


class AccountFeatureExtractor:
    """Extract features from account behavior."""

    def __init__(self):
        """Initialize extractor."""
        pass

    def extract(
        self,
        account: Dict[str, Any],
        trade_history: Optional[List[Dict]] = None,
        network_stats: Optional[Dict] = None,
    ) -> AccountFeatures:
        """Extract features from account data.

        Args:
            account: Account data dictionary
            trade_history: Historical trades for account
            network_stats: Network/graph statistics

        Returns:
            AccountFeatures dataclass
        """
        # Basic features
        created_at = account.get('created_at', datetime.now())
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        account_age = (datetime.now() - created_at).days

        total_trades = len(trade_history) if trade_history else 0
        total_volume = 0.0

        # Activity features
        trades_per_day = []
        active_hours = set()
        weekend_trades = 0
        trade_sizes = []
        counterparties = set()

        if trade_history:
            # Process trade history
            daily_counts = defaultdict(int)

            for trade in trade_history:
                quantity = float(trade.get('quantity', 0))
                total_volume += quantity
                trade_sizes.append(quantity)

                timestamp = trade.get('timestamp', datetime.now())
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp)

                daily_counts[timestamp.date()] += 1
                active_hours.add(timestamp.hour)

                if timestamp.weekday() >= 5:
                    weekend_trades += 1

                cp = trade.get('counterparty')
                if cp:
                    counterparties.add(cp)

            trades_per_day = list(daily_counts.values())

        avg_trades_per_day = np.mean(trades_per_day) if trades_per_day else 0.0
        trade_freq_variance = np.var(trades_per_day) if len(trades_per_day) > 1 else 0.0

        # Reputation features
        reputation = float(account.get('reputation', 0.5))
        rep_history = account.get('reputation_history', [])

        rep_change_30d = 0.0
        rep_volatility = 0.0
        if rep_history:
            rep_arr = np.array(rep_history)
            if len(rep_arr) > 1:
                rep_change_30d = rep_arr[-1] - rep_arr[0]
                rep_volatility = np.std(rep_arr)

        positive_feedback = account.get('positive_feedback', 0)
        total_feedback = account.get('total_feedback', 1)
        positive_ratio = positive_feedback / (total_feedback + 1e-8)

        # Network features
        unique_counterparties = len(counterparties)
        counterparty_concentration = 0.0
        avg_counterparty_rep = 0.5

        if network_stats:
            counterparty_concentration = network_stats.get('concentration', 0.0)
            avg_counterparty_rep = network_stats.get('avg_counterparty_reputation', 0.5)

        # Behavioral features
        avg_trade_size = np.mean(trade_sizes) if trade_sizes else 0.0
        trade_size_var = np.var(trade_sizes) if len(trade_sizes) > 1 else 0.0

        # Preferred hours (top 3 most active)
        hour_counts = defaultdict(int)
        if trade_history:
            for trade in trade_history:
                ts = trade.get('timestamp', datetime.now())
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                hour_counts[ts.hour] += 1

        preferred_hours = sorted(hour_counts.keys(), key=lambda h: hour_counts[h], reverse=True)[:3]

        weekend_ratio = weekend_trades / (total_trades + 1e-8) if total_trades > 0 else 0.0

        # Risk indicators
        failed_deliveries = account.get('failed_deliveries', 0)
        total_deliveries = account.get('total_deliveries', 1)
        failed_rate = failed_deliveries / (total_deliveries + 1e-8)

        disputes = account.get('disputes', 0)
        dispute_rate = disputes / (total_trades + 1e-8) if total_trades > 0 else 0.0

        suspicious_count = account.get('suspicious_pattern_count', 0)

        return AccountFeatures(
            account_age_days=account_age,
            total_trades=total_trades,
            total_volume=total_volume,
            avg_trades_per_day=avg_trades_per_day,
            trade_frequency_variance=trade_freq_variance,
            active_hours_count=len(active_hours),
            current_reputation=reputation,
            reputation_change_30d=rep_change_30d,
            reputation_volatility=rep_volatility,
            positive_feedback_ratio=positive_ratio,
            unique_counterparties=unique_counterparties,
            counterparty_concentration=counterparty_concentration,
            avg_counterparty_reputation=avg_counterparty_rep,
            avg_trade_size=avg_trade_size,
            trade_size_variance=trade_size_var,
            preferred_trading_hours=preferred_hours,
            weekend_activity_ratio=weekend_ratio,
            failed_delivery_rate=failed_rate,
            dispute_rate=dispute_rate,
            suspicious_pattern_count=suspicious_count,
        )

    def extract_batch(
        self,
        accounts: List[Dict],
        trade_histories: Optional[Dict[str, List[Dict]]] = None,
        network_stats_map: Optional[Dict[str, Dict]] = None,
    ) -> np.ndarray:
        """Extract features for multiple accounts."""
        features = []

        for account in accounts:
            account_id = account.get('account_id', '')
            history = trade_histories.get(account_id) if trade_histories else None
            network = network_stats_map.get(account_id) if network_stats_map else None

            feat = self.extract(account, history, network)
            features.append(feat.to_array())

        return np.array(features)


class GraphFeatureExtractor:
    """Extract graph/network features for anomaly detection."""

    def __init__(self):
        """Initialize extractor."""
        self._has_networkx = False
        try:
            import networkx as nx
            self._has_networkx = True
            self._nx = nx
        except ImportError:
            logger.warning("networkx not available, using simplified graph features")

    def extract(
        self,
        node_id: str,
        adjacency_list: Dict[str, List[str]],
        node_attributes: Optional[Dict[str, Dict]] = None,
        edge_weights: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> GraphFeatures:
        """Extract graph features for a node.

        Args:
            node_id: ID of the node to analyze
            adjacency_list: Graph as adjacency list
            node_attributes: Attributes for each node
            edge_weights: Edge weights (trade volumes, etc.)

        Returns:
            GraphFeatures dataclass
        """
        if self._has_networkx:
            return self._extract_with_networkx(
                node_id, adjacency_list, node_attributes, edge_weights
            )
        else:
            return self._extract_simple(
                node_id, adjacency_list, node_attributes, edge_weights
            )

    def _extract_with_networkx(
        self,
        node_id: str,
        adjacency_list: Dict[str, List[str]],
        node_attributes: Optional[Dict[str, Dict]] = None,
        edge_weights: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> GraphFeatures:
        """Extract features using networkx."""
        nx = self._nx

        # Build graph
        G = nx.Graph()
        for node, neighbors in adjacency_list.items():
            for neighbor in neighbors:
                weight = 1.0
                if edge_weights:
                    weight = edge_weights.get((node, neighbor),
                             edge_weights.get((neighbor, node), 1.0))
                G.add_edge(node, neighbor, weight=weight)

        if node_id not in G:
            return self._empty_features()

        # Centrality measures
        n_nodes = G.number_of_nodes()
        degree_centrality = G.degree(node_id) / (n_nodes - 1 + 1e-8)

        # Betweenness (expensive, use approximation for large graphs)
        if n_nodes < 1000:
            betweenness = nx.betweenness_centrality(G).get(node_id, 0)
        else:
            betweenness = nx.betweenness_centrality(G, k=min(100, n_nodes)).get(node_id, 0)

        # Clustering
        clustering = nx.clustering(G, node_id)

        # PageRank
        pagerank = nx.pagerank(G).get(node_id, 0)

        # Community detection
        try:
            communities = list(nx.community.greedy_modularity_communities(G))
            community_id = -1
            community_size = 0
            for i, comm in enumerate(communities):
                if node_id in comm:
                    community_id = i
                    community_size = len(comm)
                    break
        except:
            community_id = 0
            community_size = n_nodes

        # Intra-community ratio
        neighbors = list(G.neighbors(node_id))
        intra_community = 0
        if community_id >= 0 and len(communities) > community_id:
            community_members = communities[community_id]
            intra_community = sum(1 for n in neighbors if n in community_members)
        intra_ratio = intra_community / (len(neighbors) + 1e-8)

        # Average neighbor degree
        neighbor_degrees = [G.degree(n) for n in neighbors]
        avg_neighbor_degree = np.mean(neighbor_degrees) if neighbor_degrees else 0.0

        # Neighbor reputation variance
        neighbor_rep_var = 0.0
        if node_attributes and neighbors:
            reps = [node_attributes.get(n, {}).get('reputation', 0.5) for n in neighbors]
            neighbor_rep_var = np.var(reps) if len(reps) > 1 else 0.0

        # Edge creation rate and new connections
        edge_creation_rate = len(neighbors) / 30.0  # Assume 30-day window
        new_connection_ratio = 0.3  # Placeholder

        # Sybil indicators
        similar_behavior = self._count_similar_neighbors(
            node_id, neighbors, node_attributes
        )

        reg_clustering = 0.0
        shared_attr_score = 0.0
        if node_attributes:
            reg_clustering = self._calculate_registration_clustering(
                node_id, neighbors, node_attributes
            )
            shared_attr_score = self._calculate_shared_attributes(
                node_id, neighbors, node_attributes
            )

        return GraphFeatures(
            degree_centrality=degree_centrality,
            betweenness_centrality=betweenness,
            clustering_coefficient=clustering,
            pagerank=pagerank,
            community_id=community_id,
            community_size=community_size,
            intra_community_ratio=intra_ratio,
            avg_neighbor_degree=avg_neighbor_degree,
            neighbor_reputation_variance=neighbor_rep_var,
            edge_creation_rate=edge_creation_rate,
            new_connection_ratio_7d=new_connection_ratio,
            similar_behavior_neighbors=similar_behavior,
            registration_time_clustering=reg_clustering,
            shared_attribute_score=shared_attr_score,
        )

    def _extract_simple(
        self,
        node_id: str,
        adjacency_list: Dict[str, List[str]],
        node_attributes: Optional[Dict[str, Dict]] = None,
        edge_weights: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> GraphFeatures:
        """Extract features without networkx."""
        neighbors = adjacency_list.get(node_id, [])
        n_nodes = len(adjacency_list)

        # Simple degree centrality
        degree_centrality = len(neighbors) / (n_nodes - 1 + 1e-8)

        # Simplified clustering coefficient
        # Count triangles
        triangles = 0
        possible = len(neighbors) * (len(neighbors) - 1) / 2
        for i, n1 in enumerate(neighbors):
            for n2 in neighbors[i+1:]:
                if n2 in adjacency_list.get(n1, []):
                    triangles += 1
        clustering = triangles / (possible + 1e-8) if possible > 0 else 0

        # Average neighbor degree
        neighbor_degrees = [len(adjacency_list.get(n, [])) for n in neighbors]
        avg_neighbor_degree = np.mean(neighbor_degrees) if neighbor_degrees else 0.0

        # Neighbor reputation variance
        neighbor_rep_var = 0.0
        if node_attributes and neighbors:
            reps = [node_attributes.get(n, {}).get('reputation', 0.5) for n in neighbors]
            neighbor_rep_var = np.var(reps) if len(reps) > 1 else 0.0

        return GraphFeatures(
            degree_centrality=degree_centrality,
            betweenness_centrality=0.0,  # Not computed
            clustering_coefficient=clustering,
            pagerank=degree_centrality,  # Approximate
            community_id=0,
            community_size=n_nodes,
            intra_community_ratio=1.0,
            avg_neighbor_degree=avg_neighbor_degree,
            neighbor_reputation_variance=neighbor_rep_var,
            edge_creation_rate=len(neighbors) / 30.0,
            new_connection_ratio_7d=0.3,
            similar_behavior_neighbors=0,
            registration_time_clustering=0.0,
            shared_attribute_score=0.0,
        )

    def _empty_features(self) -> GraphFeatures:
        """Return empty features for missing node."""
        return GraphFeatures(
            degree_centrality=0.0,
            betweenness_centrality=0.0,
            clustering_coefficient=0.0,
            pagerank=0.0,
            community_id=-1,
            community_size=0,
            intra_community_ratio=0.0,
            avg_neighbor_degree=0.0,
            neighbor_reputation_variance=0.0,
            edge_creation_rate=0.0,
            new_connection_ratio_7d=0.0,
            similar_behavior_neighbors=0,
            registration_time_clustering=0.0,
            shared_attribute_score=0.0,
        )

    def _count_similar_neighbors(
        self,
        node_id: str,
        neighbors: List[str],
        node_attributes: Optional[Dict[str, Dict]],
    ) -> int:
        """Count neighbors with similar behavior patterns."""
        if not node_attributes or node_id not in node_attributes:
            return 0

        node_attrs = node_attributes.get(node_id, {})
        node_pattern = node_attrs.get('behavior_pattern', [])

        similar_count = 0
        for neighbor in neighbors:
            neighbor_attrs = node_attributes.get(neighbor, {})
            neighbor_pattern = neighbor_attrs.get('behavior_pattern', [])

            # Compare patterns
            if node_pattern and neighbor_pattern:
                similarity = self._pattern_similarity(node_pattern, neighbor_pattern)
                if similarity > 0.8:
                    similar_count += 1

        return similar_count

    def _pattern_similarity(self, p1: List, p2: List) -> float:
        """Calculate similarity between behavior patterns."""
        if not p1 or not p2:
            return 0.0

        # Convert to arrays and compare
        a1 = np.array(p1[:min(len(p1), len(p2))])
        a2 = np.array(p2[:min(len(p1), len(p2))])

        if len(a1) == 0:
            return 0.0

        # Cosine similarity
        norm1 = np.linalg.norm(a1)
        norm2 = np.linalg.norm(a2)

        if norm1 < 1e-8 or norm2 < 1e-8:
            return 0.0

        return np.dot(a1, a2) / (norm1 * norm2)

    def _calculate_registration_clustering(
        self,
        node_id: str,
        neighbors: List[str],
        node_attributes: Dict[str, Dict],
    ) -> float:
        """Calculate clustering of registration times."""
        reg_times = []

        node_reg = node_attributes.get(node_id, {}).get('registration_time')
        if node_reg:
            reg_times.append(node_reg)

        for neighbor in neighbors:
            reg = node_attributes.get(neighbor, {}).get('registration_time')
            if reg:
                reg_times.append(reg)

        if len(reg_times) < 2:
            return 0.0

        # Calculate time differences
        reg_times = sorted(reg_times)
        diffs = []
        for i in range(1, len(reg_times)):
            if isinstance(reg_times[i], datetime) and isinstance(reg_times[i-1], datetime):
                diffs.append((reg_times[i] - reg_times[i-1]).total_seconds())

        if not diffs:
            return 0.0

        # High clustering = small time differences
        avg_diff = np.mean(diffs)
        # Normalize: 1 hour = high clustering
        return max(0, 1 - avg_diff / 3600)

    def _calculate_shared_attributes(
        self,
        node_id: str,
        neighbors: List[str],
        node_attributes: Dict[str, Dict],
    ) -> float:
        """Calculate shared attribute score (Sybil indicator)."""
        node_attrs = node_attributes.get(node_id, {})

        shared_scores = []
        for neighbor in neighbors:
            neighbor_attrs = node_attributes.get(neighbor, {})

            shared = 0
            total = 0

            # Compare various attributes
            for key in ['ip_subnet', 'device_type', 'location', 'timezone']:
                if key in node_attrs and key in neighbor_attrs:
                    total += 1
                    if node_attrs[key] == neighbor_attrs[key]:
                        shared += 1

            if total > 0:
                shared_scores.append(shared / total)

        return np.mean(shared_scores) if shared_scores else 0.0

    def extract_batch(
        self,
        node_ids: List[str],
        adjacency_list: Dict[str, List[str]],
        node_attributes: Optional[Dict[str, Dict]] = None,
        edge_weights: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> np.ndarray:
        """Extract features for multiple nodes."""
        features = []

        for node_id in node_ids:
            feat = self.extract(node_id, adjacency_list, node_attributes, edge_weights)
            features.append(feat.to_array())

        return np.array(features)
