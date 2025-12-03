"""Main Anomaly Detector class for SHAKTI-CHAIN.

Orchestrates multiple detection models and provides
unified scoring and reporting interface.
"""

import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of anomalies detected."""
    # Trading anomalies
    WASH_TRADING = auto()
    PRICE_MANIPULATION = auto()
    SPOOFING = auto()
    VOLUME_SPIKE = auto()
    COORDINATED_TRADING = auto()

    # Delivery anomalies
    FALSE_DELIVERY_CLAIM = auto()
    SYSTEMATIC_NON_DELIVERY = auto()
    ENERGY_ACCOUNTING_DISCREPANCY = auto()

    # Account anomalies
    REPUTATION_MANIPULATION = auto()
    UNUSUAL_REGISTRATION = auto()
    SYBIL_CLUSTER = auto()

    # General
    UNKNOWN = auto()


class AlertLevel(Enum):
    """Alert severity levels."""
    CRITICAL = 4  # Score > 0.9, immediate action
    HIGH = 3      # Score > 0.8, immediate alert
    MEDIUM = 2    # Score > 0.6, queue for review
    LOW = 1       # Score > 0.4, log for patterns
    INFO = 0      # Score <= 0.4, informational


@dataclass
class AnomalyScore:
    """Anomaly score with breakdown and explanation."""
    # Component scores (0-1, higher = more anomalous)
    trade_anomaly: float = 0.0
    pattern_anomaly: float = 0.0
    network_anomaly: float = 0.0
    delivery_anomaly: float = 0.0
    account_anomaly: float = 0.0

    # Overall score
    overall_score: float = 0.0

    # Classification
    anomaly_type: AnomalyType = AnomalyType.UNKNOWN
    alert_level: AlertLevel = AlertLevel.INFO

    # Explanation
    explanation: str = ""
    contributing_factors: List[str] = field(default_factory=list)

    # Confidence
    confidence: float = 0.0

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    entity_id: str = ""
    entity_type: str = ""  # "trade", "account", "delivery"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'trade_anomaly': self.trade_anomaly,
            'pattern_anomaly': self.pattern_anomaly,
            'network_anomaly': self.network_anomaly,
            'delivery_anomaly': self.delivery_anomaly,
            'account_anomaly': self.account_anomaly,
            'overall_score': self.overall_score,
            'anomaly_type': self.anomaly_type.name,
            'alert_level': self.alert_level.name,
            'explanation': self.explanation,
            'contributing_factors': self.contributing_factors,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'entity_id': self.entity_id,
            'entity_type': self.entity_type,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnomalyScore':
        """Create from dictionary."""
        return cls(
            trade_anomaly=data.get('trade_anomaly', 0.0),
            pattern_anomaly=data.get('pattern_anomaly', 0.0),
            network_anomaly=data.get('network_anomaly', 0.0),
            delivery_anomaly=data.get('delivery_anomaly', 0.0),
            account_anomaly=data.get('account_anomaly', 0.0),
            overall_score=data.get('overall_score', 0.0),
            anomaly_type=AnomalyType[data.get('anomaly_type', 'UNKNOWN')],
            alert_level=AlertLevel[data.get('alert_level', 'INFO')],
            explanation=data.get('explanation', ''),
            contributing_factors=data.get('contributing_factors', []),
            confidence=data.get('confidence', 0.0),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(),
            entity_id=data.get('entity_id', ''),
            entity_type=data.get('entity_type', ''),
        )


@dataclass
class AnomalyReport:
    """Comprehensive anomaly analysis report."""
    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime

    # Summary statistics
    total_entities_analyzed: int = 0
    total_anomalies_detected: int = 0
    critical_alerts: int = 0
    high_alerts: int = 0
    medium_alerts: int = 0
    low_alerts: int = 0

    # Breakdown by type
    anomalies_by_type: Dict[str, int] = field(default_factory=dict)

    # Top anomalies
    top_anomalies: List[AnomalyScore] = field(default_factory=list)

    # Patterns detected
    patterns: List[Dict[str, Any]] = field(default_factory=list)

    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """Generate markdown report."""
        md = f"""# SHAKTI-CHAIN Anomaly Detection Report

**Report ID:** {self.report_id}
**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M:%S')}
**Period:** {self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}

## Executive Summary

| Metric | Value |
|--------|-------|
| Entities Analyzed | {self.total_entities_analyzed:,} |
| Anomalies Detected | {self.total_anomalies_detected:,} |
| Detection Rate | {self.total_anomalies_detected/max(self.total_entities_analyzed, 1)*100:.2f}% |

### Alert Breakdown

| Level | Count | Action Required |
|-------|-------|-----------------|
| 🔴 Critical | {self.critical_alerts} | Immediate investigation |
| 🟠 High | {self.high_alerts} | Alert security team |
| 🟡 Medium | {self.medium_alerts} | Queue for review |
| 🟢 Low | {self.low_alerts} | Log for patterns |

## Anomalies by Type

"""
        for anomaly_type, count in sorted(self.anomalies_by_type.items(), key=lambda x: -x[1]):
            md += f"- **{anomaly_type}**: {count}\n"

        md += "\n## Top Anomalies\n\n"

        for i, anomaly in enumerate(self.top_anomalies[:10], 1):
            md += f"""### {i}. {anomaly.entity_type.title()} - {anomaly.entity_id}

- **Score:** {anomaly.overall_score:.3f}
- **Type:** {anomaly.anomaly_type.name}
- **Alert Level:** {anomaly.alert_level.name}
- **Explanation:** {anomaly.explanation}
- **Contributing Factors:**
"""
            for factor in anomaly.contributing_factors:
                md += f"  - {factor}\n"
            md += "\n"

        if self.patterns:
            md += "## Detected Patterns\n\n"
            for pattern in self.patterns:
                md += f"- **{pattern.get('name', 'Unknown')}**: {pattern.get('description', '')}\n"

        if self.recommendations:
            md += "\n## Recommendations\n\n"
            for i, rec in enumerate(self.recommendations, 1):
                md += f"{i}. {rec}\n"

        return md


class AnomalyDetector:
    """Main anomaly detection orchestrator.

    Combines multiple detection models:
    - Isolation Forest for point anomalies
    - LSTM Autoencoder for sequential patterns
    - GNN for network/graph anomalies
    """

    def __init__(
        self,
        isolation_forest_model=None,
        autoencoder_model=None,
        gnn_model=None,
        feature_extractors: Optional[Dict[str, Any]] = None,
        alert_thresholds: Optional[Dict[str, float]] = None,
    ):
        """Initialize anomaly detector.

        Args:
            isolation_forest_model: Pre-trained Isolation Forest
            autoencoder_model: Pre-trained LSTM Autoencoder
            gnn_model: Pre-trained Graph Neural Network
            feature_extractors: Dictionary of feature extractors
            alert_thresholds: Custom alert thresholds
        """
        self.isolation_forest = isolation_forest_model
        self.autoencoder = autoencoder_model
        self.gnn = gnn_model
        self.feature_extractors = feature_extractors or {}

        # Alert thresholds
        self.thresholds = alert_thresholds or {
            'critical': 0.9,
            'high': 0.8,
            'medium': 0.6,
            'low': 0.4,
        }

        # Score weights for combining models
        self.weights = {
            'trade': 0.3,
            'pattern': 0.25,
            'network': 0.25,
            'delivery': 0.1,
            'account': 0.1,
        }

        # Score history for trending
        self.score_history: List[AnomalyScore] = []

        logger.info("AnomalyDetector initialized")

    def score_trade(
        self,
        trade: Dict[str, Any],
        account_history: Optional[List[Dict]] = None,
        network_context: Optional[Dict] = None,
    ) -> AnomalyScore:
        """Score a single trade for anomalies in real-time.

        Args:
            trade: Trade data dictionary
            account_history: Historical trades for this account
            network_context: Network/graph context for this trade

        Returns:
            AnomalyScore with detailed breakdown
        """
        scores = {}
        factors = []

        # 1. Point anomaly detection (Isolation Forest)
        trade_score = self._score_trade_point_anomaly(trade)
        scores['trade'] = trade_score
        if trade_score > 0.5:
            factors.append(f"Unusual trade characteristics (score: {trade_score:.2f})")

        # 2. Pattern anomaly detection (LSTM Autoencoder)
        pattern_score = 0.0
        if account_history:
            pattern_score = self._score_pattern_anomaly(trade, account_history)
            scores['pattern'] = pattern_score
            if pattern_score > 0.5:
                factors.append(f"Deviation from historical pattern (score: {pattern_score:.2f})")

        # 3. Network anomaly detection (GNN)
        network_score = 0.0
        if network_context:
            network_score = self._score_network_anomaly(trade, network_context)
            scores['network'] = network_score
            if network_score > 0.5:
                factors.append(f"Suspicious network activity (score: {network_score:.2f})")

        # 4. Specific anomaly checks
        specific_scores = self._check_specific_anomalies(trade, account_history)
        scores.update(specific_scores)

        # Calculate overall score
        overall = self._calculate_overall_score(scores)

        # Determine anomaly type
        anomaly_type = self._classify_anomaly_type(scores, trade)

        # Generate explanation
        explanation = self._generate_explanation(anomaly_type, scores, factors)

        # Determine alert level
        alert_level = self._determine_alert_level(overall)

        # Create score object
        result = AnomalyScore(
            trade_anomaly=scores.get('trade', 0.0),
            pattern_anomaly=scores.get('pattern', 0.0),
            network_anomaly=scores.get('network', 0.0),
            delivery_anomaly=scores.get('delivery', 0.0),
            account_anomaly=scores.get('account', 0.0),
            overall_score=overall,
            anomaly_type=anomaly_type,
            alert_level=alert_level,
            explanation=explanation,
            contributing_factors=factors,
            confidence=self._calculate_confidence(scores),
            entity_id=trade.get('trade_id', ''),
            entity_type='trade',
        )

        # Store for trending
        self.score_history.append(result)

        return result

    def score_delivery(
        self,
        delivery: Dict[str, Any],
        meter_data: Optional[Dict] = None,
        historical_deliveries: Optional[List[Dict]] = None,
    ) -> AnomalyScore:
        """Score a delivery claim for anomalies.

        Args:
            delivery: Delivery claim data
            meter_data: Associated meter readings
            historical_deliveries: Historical delivery patterns

        Returns:
            AnomalyScore for the delivery
        """
        scores = {}
        factors = []

        # Check delivery vs meter discrepancy
        if meter_data:
            claimed = delivery.get('energy_kwh', 0)
            metered = meter_data.get('energy_kwh', 0)

            if claimed > 0:
                discrepancy = abs(claimed - metered) / claimed
                if discrepancy > 0.1:  # >10% discrepancy
                    scores['delivery'] = min(1.0, discrepancy)
                    factors.append(f"Energy discrepancy: claimed {claimed:.1f} kWh, metered {metered:.1f} kWh")

        # Check for systematic non-delivery
        if historical_deliveries:
            success_rate = sum(1 for d in historical_deliveries if d.get('completed', False)) / len(historical_deliveries)
            if success_rate < 0.8:
                scores['delivery'] = max(scores.get('delivery', 0), 1 - success_rate)
                factors.append(f"Low delivery success rate: {success_rate*100:.1f}%")

        # Check timing anomalies
        delivery_time = delivery.get('timestamp')
        if delivery_time:
            hour = delivery_time.hour if hasattr(delivery_time, 'hour') else 12
            if 0 <= hour <= 5:
                scores['delivery'] = max(scores.get('delivery', 0), 0.3)
                factors.append("Unusual delivery timing (late night)")

        overall = scores.get('delivery', 0.0)
        alert_level = self._determine_alert_level(overall)

        return AnomalyScore(
            delivery_anomaly=overall,
            overall_score=overall,
            anomaly_type=AnomalyType.ENERGY_ACCOUNTING_DISCREPANCY if overall > 0.5 else AnomalyType.UNKNOWN,
            alert_level=alert_level,
            explanation=self._generate_explanation(AnomalyType.ENERGY_ACCOUNTING_DISCREPANCY, scores, factors),
            contributing_factors=factors,
            confidence=0.8 if meter_data else 0.5,
            entity_id=delivery.get('delivery_id', ''),
            entity_type='delivery',
        )

    def score_account(
        self,
        account: Dict[str, Any],
        network_graph: Optional[Any] = None,
        all_accounts: Optional[List[Dict]] = None,
    ) -> AnomalyScore:
        """Score an account for anomalies (Sybil detection, etc.).

        Args:
            account: Account data
            network_graph: Network graph for Sybil detection
            all_accounts: All accounts for pattern matching

        Returns:
            AnomalyScore for the account
        """
        scores = {}
        factors = []

        # Check reputation changes
        reputation = account.get('reputation', 0)
        reputation_change = account.get('reputation_change_30d', 0)

        if abs(reputation_change) > 50:  # Unusual change
            scores['account'] = min(1.0, abs(reputation_change) / 100)
            factors.append(f"Unusual reputation change: {reputation_change:+d} in 30 days")

        # Check registration patterns
        registration_time = account.get('created_at')
        if registration_time and all_accounts:
            # Check for batch registrations
            similar_time_accounts = [
                a for a in all_accounts
                if a.get('created_at') and abs((a['created_at'] - registration_time).total_seconds()) < 3600
            ]
            if len(similar_time_accounts) > 10:
                scores['account'] = max(scores.get('account', 0), 0.7)
                factors.append(f"Part of batch registration: {len(similar_time_accounts)} accounts within 1 hour")

        # Check for Sybil clusters (via GNN)
        if network_graph and self.gnn:
            sybil_score = self._detect_sybil_cluster(account, network_graph)
            if sybil_score > 0.5:
                scores['account'] = max(scores.get('account', 0), sybil_score)
                factors.append(f"Potential Sybil cluster detected (score: {sybil_score:.2f})")

        # Check trading patterns
        avg_trade_size = account.get('avg_trade_size', 0)
        trade_count = account.get('trade_count', 0)

        if trade_count > 100 and avg_trade_size < 1:
            scores['account'] = max(scores.get('account', 0), 0.6)
            factors.append("High frequency small trades pattern (potential wash trading)")

        overall = scores.get('account', 0.0)
        alert_level = self._determine_alert_level(overall)

        anomaly_type = AnomalyType.UNKNOWN
        if overall > 0.5:
            if 'Sybil' in str(factors):
                anomaly_type = AnomalyType.SYBIL_CLUSTER
            elif 'reputation' in str(factors).lower():
                anomaly_type = AnomalyType.REPUTATION_MANIPULATION
            elif 'registration' in str(factors).lower():
                anomaly_type = AnomalyType.UNUSUAL_REGISTRATION

        return AnomalyScore(
            account_anomaly=overall,
            overall_score=overall,
            anomaly_type=anomaly_type,
            alert_level=alert_level,
            explanation=self._generate_explanation(anomaly_type, scores, factors),
            contributing_factors=factors,
            confidence=0.7,
            entity_id=account.get('account_id', ''),
            entity_type='account',
        )

    def batch_analyze(
        self,
        trades_df,
        deliveries_df=None,
        accounts_df=None,
    ) -> AnomalyReport:
        """Perform batch analysis on multiple entities.

        Args:
            trades_df: DataFrame of trades
            deliveries_df: Optional DataFrame of deliveries
            accounts_df: Optional DataFrame of accounts

        Returns:
            Comprehensive AnomalyReport
        """
        import uuid
        from collections import defaultdict

        logger.info(f"Starting batch analysis on {len(trades_df)} trades")

        all_scores: List[AnomalyScore] = []
        anomalies_by_type = defaultdict(int)

        # Analyze trades
        for idx, trade in trades_df.iterrows():
            trade_dict = trade.to_dict()

            # Get account history
            account_id = trade_dict.get('account_id')
            account_history = None
            if account_id:
                account_history = trades_df[trades_df['account_id'] == account_id].to_dict('records')

            score = self.score_trade(trade_dict, account_history)
            all_scores.append(score)

            if score.alert_level.value >= AlertLevel.LOW.value:
                anomalies_by_type[score.anomaly_type.name] += 1

        # Analyze deliveries
        if deliveries_df is not None:
            for idx, delivery in deliveries_df.iterrows():
                score = self.score_delivery(delivery.to_dict())
                all_scores.append(score)

                if score.alert_level.value >= AlertLevel.LOW.value:
                    anomalies_by_type[score.anomaly_type.name] += 1

        # Analyze accounts
        if accounts_df is not None:
            all_accounts = accounts_df.to_dict('records')
            for idx, account in accounts_df.iterrows():
                score = self.score_account(account.to_dict(), all_accounts=all_accounts)
                all_scores.append(score)

                if score.alert_level.value >= AlertLevel.LOW.value:
                    anomalies_by_type[score.anomaly_type.name] += 1

        # Count alerts by level
        critical = sum(1 for s in all_scores if s.alert_level == AlertLevel.CRITICAL)
        high = sum(1 for s in all_scores if s.alert_level == AlertLevel.HIGH)
        medium = sum(1 for s in all_scores if s.alert_level == AlertLevel.MEDIUM)
        low = sum(1 for s in all_scores if s.alert_level == AlertLevel.LOW)

        # Get top anomalies
        sorted_scores = sorted(all_scores, key=lambda x: -x.overall_score)
        top_anomalies = sorted_scores[:20]

        # Detect patterns
        patterns = self._detect_patterns(all_scores)

        # Generate recommendations
        recommendations = self._generate_recommendations(anomalies_by_type, patterns)

        # Create report
        report = AnomalyReport(
            report_id=str(uuid.uuid4())[:8],
            generated_at=datetime.now(),
            period_start=trades_df.index.min() if hasattr(trades_df.index, 'min') else datetime.now(),
            period_end=trades_df.index.max() if hasattr(trades_df.index, 'max') else datetime.now(),
            total_entities_analyzed=len(all_scores),
            total_anomalies_detected=critical + high + medium + low,
            critical_alerts=critical,
            high_alerts=high,
            medium_alerts=medium,
            low_alerts=low,
            anomalies_by_type=dict(anomalies_by_type),
            top_anomalies=top_anomalies,
            patterns=patterns,
            recommendations=recommendations,
        )

        logger.info(f"Batch analysis complete: {report.total_anomalies_detected} anomalies detected")
        return report

    def _score_trade_point_anomaly(self, trade: Dict[str, Any]) -> float:
        """Score trade using Isolation Forest."""
        if self.isolation_forest is None:
            # Fallback to heuristic scoring
            return self._heuristic_trade_score(trade)

        # Extract features and score
        features = self._extract_trade_features(trade)
        score = self.isolation_forest.score_samples([features])[0]

        # Convert to 0-1 range (IF returns negative scores)
        return max(0, min(1, -score))

    def _score_pattern_anomaly(
        self,
        trade: Dict[str, Any],
        history: List[Dict],
    ) -> float:
        """Score trade against historical patterns using autoencoder."""
        if self.autoencoder is None or len(history) < 10:
            return 0.0

        # Build sequence from history
        sequence = self._build_sequence(history[-24:])  # Last 24 trades

        # Get reconstruction error
        reconstruction_error = self.autoencoder.get_reconstruction_error(sequence)

        # Normalize to 0-1
        return min(1.0, reconstruction_error / 2.0)

    def _score_network_anomaly(
        self,
        trade: Dict[str, Any],
        network_context: Dict,
    ) -> float:
        """Score trade for network anomalies using GNN."""
        if self.gnn is None:
            return 0.0

        # Use GNN to detect unusual network patterns
        return self.gnn.score_node(trade.get('account_id'), network_context)

    def _check_specific_anomalies(
        self,
        trade: Dict[str, Any],
        history: Optional[List[Dict]],
    ) -> Dict[str, float]:
        """Check for specific anomaly types."""
        scores = {}

        # Wash trading detection
        if history:
            wash_score = self._detect_wash_trading(trade, history)
            if wash_score > 0:
                scores['wash_trading'] = wash_score

        # Volume spike detection
        volume = trade.get('quantity', 0)
        avg_volume = trade.get('avg_market_volume', 100)
        if volume > avg_volume * 3:
            scores['volume_spike'] = min(1.0, (volume / avg_volume - 1) / 5)

        # Price manipulation detection
        price = trade.get('price', 0)
        market_price = trade.get('market_price', price)
        if market_price > 0:
            price_deviation = abs(price - market_price) / market_price
            if price_deviation > 0.1:
                scores['price_manipulation'] = min(1.0, price_deviation)

        return scores

    def _detect_wash_trading(
        self,
        trade: Dict[str, Any],
        history: List[Dict],
    ) -> float:
        """Detect potential wash trading patterns."""
        if len(history) < 5:
            return 0.0

        account_id = trade.get('account_id')
        counterparty = trade.get('counterparty_id')

        # Check for frequent trades with same counterparty
        same_counterparty = sum(1 for t in history if t.get('counterparty_id') == counterparty)

        if same_counterparty > len(history) * 0.5:
            return min(1.0, same_counterparty / len(history))

        # Check for round-trip trades (buy then sell immediately)
        buy_sell_pairs = 0
        for i in range(len(history) - 1):
            if (history[i].get('trade_type') == 'buy' and
                history[i+1].get('trade_type') == 'sell' and
                abs(history[i].get('quantity', 0) - history[i+1].get('quantity', 0)) < 0.1):
                buy_sell_pairs += 1

        if buy_sell_pairs > 3:
            return min(1.0, buy_sell_pairs / 10)

        return 0.0

    def _detect_sybil_cluster(
        self,
        account: Dict[str, Any],
        network_graph: Any,
    ) -> float:
        """Detect Sybil account clusters."""
        if self.gnn is None:
            return 0.0

        # Use GNN community detection
        return self.gnn.detect_sybil_score(account.get('account_id'), network_graph)

    def _heuristic_trade_score(self, trade: Dict[str, Any]) -> float:
        """Fallback heuristic scoring when IF not available."""
        score = 0.0
        factors = 0

        # Size anomaly
        quantity = trade.get('quantity', 0)
        if quantity > 100:
            score += 0.3
            factors += 1
        elif quantity < 0.1:
            score += 0.2
            factors += 1

        # Price anomaly
        price = trade.get('price', 5)
        if price > 20 or price < 1:
            score += 0.3
            factors += 1

        # Timing anomaly
        hour = trade.get('hour', 12)
        if 0 <= hour <= 4:
            score += 0.2
            factors += 1

        return score / max(factors, 1)

    def _extract_trade_features(self, trade: Dict[str, Any]) -> np.ndarray:
        """Extract feature vector from trade."""
        return np.array([
            trade.get('quantity', 0),
            trade.get('price', 5),
            trade.get('hour', 12),
            1 if trade.get('trade_type') == 'buy' else 0,
            trade.get('account_age_days', 30),
            trade.get('account_trade_count', 10),
        ])

    def _build_sequence(self, history: List[Dict]) -> np.ndarray:
        """Build sequence array from history."""
        features = []
        for trade in history:
            features.append(self._extract_trade_features(trade))
        return np.array(features)

    def _calculate_overall_score(self, scores: Dict[str, float]) -> float:
        """Calculate weighted overall anomaly score."""
        weighted_sum = 0.0
        weight_sum = 0.0

        for category, score in scores.items():
            weight = self.weights.get(category, 0.1)
            weighted_sum += score * weight
            weight_sum += weight

        if weight_sum == 0:
            return 0.0

        return min(1.0, weighted_sum / weight_sum)

    def _classify_anomaly_type(
        self,
        scores: Dict[str, float],
        trade: Dict[str, Any],
    ) -> AnomalyType:
        """Classify the most likely anomaly type."""
        if max(scores.values(), default=0) < 0.3:
            return AnomalyType.UNKNOWN

        # Find highest scoring category
        max_category = max(scores, key=scores.get)

        type_mapping = {
            'wash_trading': AnomalyType.WASH_TRADING,
            'price_manipulation': AnomalyType.PRICE_MANIPULATION,
            'volume_spike': AnomalyType.VOLUME_SPIKE,
            'network': AnomalyType.COORDINATED_TRADING,
            'delivery': AnomalyType.ENERGY_ACCOUNTING_DISCREPANCY,
            'account': AnomalyType.REPUTATION_MANIPULATION,
        }

        return type_mapping.get(max_category, AnomalyType.UNKNOWN)

    def _determine_alert_level(self, score: float) -> AlertLevel:
        """Determine alert level from score."""
        if score >= self.thresholds['critical']:
            return AlertLevel.CRITICAL
        elif score >= self.thresholds['high']:
            return AlertLevel.HIGH
        elif score >= self.thresholds['medium']:
            return AlertLevel.MEDIUM
        elif score >= self.thresholds['low']:
            return AlertLevel.LOW
        else:
            return AlertLevel.INFO

    def _generate_explanation(
        self,
        anomaly_type: AnomalyType,
        scores: Dict[str, float],
        factors: List[str],
    ) -> str:
        """Generate human-readable explanation."""
        if anomaly_type == AnomalyType.UNKNOWN:
            return "No significant anomalies detected."

        explanations = {
            AnomalyType.WASH_TRADING: "Potential wash trading detected: repeated trades with same counterparty or immediate round-trip patterns.",
            AnomalyType.PRICE_MANIPULATION: "Price manipulation suspected: significant deviation from market price.",
            AnomalyType.SPOOFING: "Spoofing pattern detected: orders placed and quickly cancelled.",
            AnomalyType.VOLUME_SPIKE: "Unusual volume spike: trade size significantly exceeds normal market volume.",
            AnomalyType.COORDINATED_TRADING: "Coordinated trading pattern: unusual network of related trades.",
            AnomalyType.FALSE_DELIVERY_CLAIM: "False delivery claim: claimed energy does not match meter readings.",
            AnomalyType.SYSTEMATIC_NON_DELIVERY: "Systematic non-delivery: consistent failure to deliver committed energy.",
            AnomalyType.ENERGY_ACCOUNTING_DISCREPANCY: "Energy accounting discrepancy: mismatch between claimed and metered values.",
            AnomalyType.REPUTATION_MANIPULATION: "Reputation manipulation: unusual changes in reputation score.",
            AnomalyType.UNUSUAL_REGISTRATION: "Unusual registration pattern: part of suspected batch registration.",
            AnomalyType.SYBIL_CLUSTER: "Sybil cluster detected: account appears to be part of coordinated fake account network.",
        }

        base = explanations.get(anomaly_type, "Anomaly detected.")

        if factors:
            base += " Contributing factors: " + "; ".join(factors[:3])

        return base

    def _calculate_confidence(self, scores: Dict[str, float]) -> float:
        """Calculate confidence in the anomaly score."""
        # Higher confidence when multiple signals agree
        high_scores = sum(1 for s in scores.values() if s > 0.5)
        return min(1.0, 0.5 + high_scores * 0.1)

    def _detect_patterns(self, scores: List[AnomalyScore]) -> List[Dict[str, Any]]:
        """Detect patterns across all anomaly scores."""
        patterns = []

        # Time-based clustering
        high_score_times = [s.timestamp.hour for s in scores if s.overall_score > 0.6]
        if high_score_times:
            from collections import Counter
            time_counts = Counter(high_score_times)
            peak_hour = time_counts.most_common(1)[0]
            if peak_hour[1] > len(high_score_times) * 0.3:
                patterns.append({
                    'name': 'Time Clustering',
                    'description': f'High anomaly concentration at hour {peak_hour[0]}:00',
                    'severity': 'medium',
                })

        # Type clustering
        anomaly_types = [s.anomaly_type.name for s in scores if s.anomaly_type != AnomalyType.UNKNOWN]
        if anomaly_types:
            from collections import Counter
            type_counts = Counter(anomaly_types)
            dominant_type = type_counts.most_common(1)[0]
            if dominant_type[1] > len(anomaly_types) * 0.5:
                patterns.append({
                    'name': 'Dominant Anomaly Type',
                    'description': f'{dominant_type[0]} accounts for {dominant_type[1]/len(anomaly_types)*100:.0f}% of anomalies',
                    'severity': 'high',
                })

        return patterns

    def _generate_recommendations(
        self,
        anomalies_by_type: Dict[str, int],
        patterns: List[Dict],
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        if anomalies_by_type.get('WASH_TRADING', 0) > 5:
            recommendations.append(
                "Implement stricter trade velocity limits to prevent wash trading patterns."
            )

        if anomalies_by_type.get('SYBIL_CLUSTER', 0) > 0:
            recommendations.append(
                "Review account verification process - Sybil clusters detected."
            )

        if anomalies_by_type.get('ENERGY_ACCOUNTING_DISCREPANCY', 0) > 3:
            recommendations.append(
                "Audit meter integration - multiple energy accounting discrepancies found."
            )

        if any(p.get('severity') == 'high' for p in patterns):
            recommendations.append(
                "Investigate high-severity patterns immediately with security team."
            )

        if not recommendations:
            recommendations.append(
                "Continue monitoring - no immediate actions required."
            )

        return recommendations
