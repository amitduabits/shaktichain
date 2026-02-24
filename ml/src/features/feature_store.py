"""Feature store management using Feast."""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

try:
    from feast import Entity, Feature, FeatureStore as FeastFeatureStore, FeatureView, FileSource, ValueType
    from feast.data_format import ParquetFormat
except ImportError:
    Entity = Feature = FeatureView = FileSource = ValueType = ParquetFormat = None
    FeastFeatureStore = None

logger = logging.getLogger(__name__)


class ShaktiChainFeatureStore:
    """Wrapper for Feast feature store with SHAKTI-CHAIN specific features."""

    def __init__(self, repo_path: str = "feature_repo"):
        """Initialize feature store.

        Args:
            repo_path: Path to feature repository
        """
        self.repo_path = Path(repo_path)
        self.repo_path.mkdir(parents=True, exist_ok=True)

        if FeastFeatureStore is None:
            logger.warning("Feast is not installed; ShaktiChainFeatureStore disabled")
            self.store = None
        else:
            try:
                self.store = FeastFeatureStore(repo_path=str(self.repo_path))
                logger.info(f"Initialized Feast feature store at {self.repo_path}")
            except Exception as e:
                logger.warning(f"Could not initialize Feast store: {e}")
                self.store = None

    def create_feature_definitions(self) -> None:
        """Create feature definitions for SHAKTI-CHAIN."""
        # This is a simplified example - actual Feast setup requires
        # separate feature_store.yaml and feature definition files

        logger.info("Feature definitions should be created in feature_repo/")
        logger.info("See example_feature_repo.py for structure")

    def materialize_features(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> None:
        """Materialize features to online store.

        Args:
            start_date: Start date for materialization
            end_date: End date for materialization
        """
        if not self.store:
            logger.error("Feature store not initialized")
            return

        try:
            self.store.materialize(start_date, end_date)
            logger.info(f"Materialized features from {start_date} to {end_date}")
        except Exception as e:
            logger.error(f"Failed to materialize features: {e}")

    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        features: List[str],
    ) -> pd.DataFrame:
        """Get historical features for training.

        Args:
            entity_df: DataFrame with entity keys and timestamps
            features: List of feature references

        Returns:
            DataFrame with historical features
        """
        if not self.store:
            logger.error("Feature store not initialized")
            return pd.DataFrame()

        try:
            training_df = self.store.get_historical_features(
                entity_df=entity_df,
                features=features,
            ).to_df()

            logger.info(f"Retrieved {len(training_df)} historical feature records")
            return training_df

        except Exception as e:
            logger.error(f"Failed to get historical features: {e}")
            return pd.DataFrame()

    def get_online_features(
        self,
        entity_rows: List[dict],
        features: List[str],
    ) -> dict:
        """Get online features for inference.

        Args:
            entity_rows: List of entity dictionaries
            features: List of feature references

        Returns:
            Dictionary with feature values
        """
        if not self.store:
            logger.error("Feature store not initialized")
            return {}

        try:
            feature_vector = self.store.get_online_features(
                entity_rows=entity_rows,
                features=features,
            ).to_dict()

            logger.info("Retrieved online features")
            return feature_vector

        except Exception as e:
            logger.error(f"Failed to get online features: {e}")
            return {}


class ParquetFeatureStore:
    """Simple Parquet-based feature store alternative to Feast."""

    def __init__(self, store_path: str = "data/features"):
        """Initialize Parquet feature store.

        Args:
            store_path: Path to store feature files
        """
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized Parquet feature store at {self.store_path}")

    def save_features(
        self,
        features: pd.DataFrame,
        feature_name: str,
        partition_cols: Optional[List[str]] = None,
    ) -> None:
        """Save features to Parquet.

        Args:
            features: DataFrame with features
            feature_name: Name of feature set
            partition_cols: Columns to partition by
        """
        output_path = self.store_path / f"{feature_name}.parquet"

        features.to_parquet(
            output_path,
            engine="pyarrow",
            compression="snappy",
            index=False,
            partition_cols=partition_cols,
        )

        logger.info(f"Saved {len(features)} records to {output_path}")

    def load_features(
        self,
        feature_name: str,
        filters: Optional[List[tuple]] = None,
    ) -> pd.DataFrame:
        """Load features from Parquet.

        Args:
            feature_name: Name of feature set
            filters: Optional filters for reading

        Returns:
            DataFrame with features
        """
        input_path = self.store_path / f"{feature_name}.parquet"

        if not input_path.exists():
            logger.error(f"Feature file not found: {input_path}")
            return pd.DataFrame()

        features = pd.read_parquet(input_path, filters=filters)
        logger.info(f"Loaded {len(features)} records from {input_path}")

        return features

    def get_latest_features(
        self,
        feature_name: str,
        timestamp_col: str = "timestamp",
        lookback_hours: int = 168,
    ) -> pd.DataFrame:
        """Get latest features within lookback window.

        Args:
            feature_name: Name of feature set
            timestamp_col: Name of timestamp column
            lookback_hours: Hours to look back

        Returns:
            DataFrame with recent features
        """
        features = self.load_features(feature_name)

        if features.empty:
            return features

        cutoff_time = pd.Timestamp.now() - pd.Timedelta(hours=lookback_hours)
        features = features[features[timestamp_col] >= cutoff_time]

        logger.info(
            f"Retrieved {len(features)} records from last {lookback_hours} hours"
        )

        return features

    def merge_features(
        self,
        feature_names: List[str],
        on: str = "timestamp",
        how: str = "inner",
    ) -> pd.DataFrame:
        """Merge multiple feature sets.

        Args:
            feature_names: List of feature set names
            on: Column to merge on
            how: Type of merge

        Returns:
            Merged DataFrame
        """
        if not feature_names:
            return pd.DataFrame()

        # Load first feature set
        merged = self.load_features(feature_names[0])

        # Merge with remaining feature sets
        for feature_name in feature_names[1:]:
            features = self.load_features(feature_name)
            merged = merged.merge(features, on=on, how=how)

        logger.info(
            f"Merged {len(feature_names)} feature sets, "
            f"resulting in {len(merged)} records"
        )

        return merged


class FeatureStore:
    """Backward-compatible lightweight feature store for integration tests."""

    def __init__(self, backend: str = "memory", redis_url: Optional[str] = None):
        self.backend = backend
        self.redis_url = redis_url
        self._memory: Dict[str, pd.DataFrame] = {}

    def write(
        self,
        features: pd.DataFrame,
        entity_id: str,
        feature_names: List[str],
    ) -> None:
        if features.empty:
            self._memory[entity_id] = pd.DataFrame(columns=["timestamp", *feature_names])
            return

        frame = features.copy()
        if "timestamp" in frame.columns:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"])
            frame = frame.sort_values("timestamp")

        selected_cols = ["timestamp", *[c for c in feature_names if c in frame.columns]]
        self._memory[entity_id] = frame[selected_cols].reset_index(drop=True)

    def read(
        self,
        entity_id: str,
        feature_names: List[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> pd.DataFrame:
        frame = self._memory.get(entity_id)
        if frame is None or frame.empty:
            return pd.DataFrame(columns=["timestamp", *feature_names])

        result = frame.copy()
        if "timestamp" in result.columns:
            if start_time is not None:
                result = result[result["timestamp"] >= pd.Timestamp(start_time)]
            if end_time is not None:
                result = result[result["timestamp"] <= pd.Timestamp(end_time)]

        keep_cols = ["timestamp", *[c for c in feature_names if c in result.columns]]
        return result[keep_cols].reset_index(drop=True)
