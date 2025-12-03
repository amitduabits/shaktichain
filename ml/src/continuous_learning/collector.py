"""Data collection for continuous learning.

Provides:
- Stream predictions and actuals to data lake
- Partition by date for efficient querying
- Label with ground truth
- Support for S3/GCS/local storage
"""

import asyncio
import logging
import json
import gzip
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class StorageBackend(Enum):
    """Storage backend types."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"


@dataclass
class DataLakeConfig:
    """Configuration for data lake storage."""
    backend: StorageBackend = StorageBackend.LOCAL
    base_path: str = "./data/lake"

    # Cloud storage
    bucket: Optional[str] = None
    prefix: str = "shakti/ml"

    # Partitioning
    partition_by: str = "date"  # date, hour, model
    compress: bool = True

    # Batching
    batch_size: int = 100
    flush_interval_seconds: float = 60.0

    # Retention
    retention_days: int = 90


@dataclass
class PredictionRecord:
    """Record of a model prediction."""
    prediction_id: str
    model_name: str
    model_version: str
    timestamp: datetime
    input_features: Dict[str, Any]
    prediction: Union[float, List[float], Dict[str, Any]]
    confidence: Optional[float] = None
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prediction_id": self.prediction_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "timestamp": self.timestamp.isoformat(),
            "input_features": self.input_features,
            "prediction": self.prediction,
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionRecord":
        """Create from dictionary."""
        return cls(
            prediction_id=data["prediction_id"],
            model_name=data["model_name"],
            model_version=data["model_version"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            input_features=data["input_features"],
            prediction=data["prediction"],
            confidence=data.get("confidence"),
            latency_ms=data.get("latency_ms", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ActualRecord:
    """Record of actual/ground truth values."""
    actual_id: str
    prediction_id: Optional[str]  # Link to prediction
    model_name: str
    timestamp: datetime
    actual_value: Union[float, List[float], Dict[str, Any]]
    label_source: str  # Where the label came from
    label_timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "actual_id": self.actual_id,
            "prediction_id": self.prediction_id,
            "model_name": self.model_name,
            "timestamp": self.timestamp.isoformat(),
            "actual_value": self.actual_value,
            "label_source": self.label_source,
            "label_timestamp": self.label_timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActualRecord":
        """Create from dictionary."""
        return cls(
            actual_id=data["actual_id"],
            prediction_id=data.get("prediction_id"),
            model_name=data["model_name"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            actual_value=data["actual_value"],
            label_source=data["label_source"],
            label_timestamp=datetime.fromisoformat(data.get("label_timestamp", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DataPartition:
    """Represents a data partition."""
    partition_key: str  # e.g., "2024/01/15"
    record_type: str  # predictions, actuals
    record_count: int
    size_bytes: int
    created_at: datetime
    path: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "partition_key": self.partition_key,
            "record_type": self.record_type,
            "record_count": self.record_count,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at.isoformat(),
            "path": self.path,
        }


class DataCollector:
    """Collect and store predictions and actuals for continuous learning."""

    def __init__(self, config: Optional[DataLakeConfig] = None):
        """Initialize data collector.

        Args:
            config: Data lake configuration
        """
        self.config = config or DataLakeConfig()

        # Buffers for batching
        self._prediction_buffer: List[PredictionRecord] = []
        self._actual_buffer: List[ActualRecord] = []

        # Storage clients
        self._s3_client = None
        self._gcs_client = None

        # Background flush task
        self._flush_task: Optional[asyncio.Task] = None
        self._running = False

        # Statistics
        self._stats = {
            "predictions_collected": 0,
            "actuals_collected": 0,
            "batches_written": 0,
            "bytes_written": 0,
        }

        # Initialize storage
        self._init_storage()

    def _init_storage(self):
        """Initialize storage backend."""
        if self.config.backend == StorageBackend.LOCAL:
            Path(self.config.base_path).mkdir(parents=True, exist_ok=True)

        elif self.config.backend == StorageBackend.S3:
            try:
                import boto3
                self._s3_client = boto3.client("s3")
            except ImportError:
                logger.warning("boto3 not installed, falling back to local storage")
                self.config.backend = StorageBackend.LOCAL

        elif self.config.backend == StorageBackend.GCS:
            try:
                from google.cloud import storage
                self._gcs_client = storage.Client()
            except ImportError:
                logger.warning("google-cloud-storage not installed, falling back to local")
                self.config.backend = StorageBackend.LOCAL

    async def start(self):
        """Start background flush task."""
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("Data collector started")

    async def stop(self):
        """Stop collector and flush remaining data."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Final flush
        await self.flush()
        logger.info("Data collector stopped")

    async def _flush_loop(self):
        """Background loop to periodically flush buffers."""
        while self._running:
            try:
                await asyncio.sleep(self.config.flush_interval_seconds)
                await self.flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush loop error: {e}")

    async def record_prediction(
        self,
        model_name: str,
        model_version: str,
        input_features: Dict[str, Any],
        prediction: Union[float, List[float], Dict[str, Any]],
        confidence: Optional[float] = None,
        latency_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record a model prediction.

        Args:
            model_name: Name of the model
            model_version: Version of the model
            input_features: Input features used
            prediction: Model prediction
            confidence: Prediction confidence
            latency_ms: Inference latency
            metadata: Additional metadata

        Returns:
            Prediction ID
        """
        prediction_id = str(uuid.uuid4())

        record = PredictionRecord(
            prediction_id=prediction_id,
            model_name=model_name,
            model_version=model_version,
            timestamp=datetime.now(),
            input_features=input_features,
            prediction=prediction,
            confidence=confidence,
            latency_ms=latency_ms,
            metadata=metadata or {},
        )

        self._prediction_buffer.append(record)
        self._stats["predictions_collected"] += 1

        # Flush if buffer is full
        if len(self._prediction_buffer) >= self.config.batch_size:
            await self._flush_predictions()

        return prediction_id

    async def record_actual(
        self,
        model_name: str,
        actual_value: Union[float, List[float], Dict[str, Any]],
        timestamp: datetime,
        prediction_id: Optional[str] = None,
        label_source: str = "ground_truth",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Record actual/ground truth value.

        Args:
            model_name: Name of the model
            actual_value: Actual value
            timestamp: When the actual occurred
            prediction_id: Linked prediction ID
            label_source: Source of the label
            metadata: Additional metadata

        Returns:
            Actual ID
        """
        actual_id = str(uuid.uuid4())

        record = ActualRecord(
            actual_id=actual_id,
            prediction_id=prediction_id,
            model_name=model_name,
            timestamp=timestamp,
            actual_value=actual_value,
            label_source=label_source,
            metadata=metadata or {},
        )

        self._actual_buffer.append(record)
        self._stats["actuals_collected"] += 1

        if len(self._actual_buffer) >= self.config.batch_size:
            await self._flush_actuals()

        return actual_id

    async def flush(self):
        """Flush all buffers to storage."""
        await self._flush_predictions()
        await self._flush_actuals()

    async def _flush_predictions(self):
        """Flush prediction buffer to storage."""
        if not self._prediction_buffer:
            return

        records = self._prediction_buffer
        self._prediction_buffer = []

        await self._write_records(records, "predictions")

    async def _flush_actuals(self):
        """Flush actuals buffer to storage."""
        if not self._actual_buffer:
            return

        records = self._actual_buffer
        self._actual_buffer = []

        await self._write_records(records, "actuals")

    async def _write_records(
        self,
        records: List[Union[PredictionRecord, ActualRecord]],
        record_type: str,
    ):
        """Write records to storage.

        Args:
            records: Records to write
            record_type: Type of records (predictions/actuals)
        """
        if not records:
            return

        # Group by partition
        partitions: Dict[str, List] = {}
        for record in records:
            key = self._get_partition_key(record.timestamp)
            if key not in partitions:
                partitions[key] = []
            partitions[key].append(record)

        # Write each partition
        for partition_key, partition_records in partitions.items():
            await self._write_partition(partition_key, partition_records, record_type)

    def _get_partition_key(self, timestamp: datetime) -> str:
        """Get partition key for timestamp."""
        if self.config.partition_by == "date":
            return timestamp.strftime("%Y/%m/%d")
        elif self.config.partition_by == "hour":
            return timestamp.strftime("%Y/%m/%d/%H")
        else:
            return timestamp.strftime("%Y/%m/%d")

    async def _write_partition(
        self,
        partition_key: str,
        records: List[Union[PredictionRecord, ActualRecord]],
        record_type: str,
    ):
        """Write records to a partition.

        Args:
            partition_key: Partition key
            records: Records to write
            record_type: Type of records
        """
        # Serialize records
        data = [r.to_dict() for r in records]
        content = "\n".join(json.dumps(d) for d in data)

        if self.config.compress:
            content_bytes = gzip.compress(content.encode())
            extension = ".jsonl.gz"
        else:
            content_bytes = content.encode()
            extension = ".jsonl"

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{record_type}_{timestamp}_{uuid.uuid4().hex[:8]}{extension}"

        # Write based on backend
        if self.config.backend == StorageBackend.LOCAL:
            await self._write_local(partition_key, record_type, filename, content_bytes)
        elif self.config.backend == StorageBackend.S3:
            await self._write_s3(partition_key, record_type, filename, content_bytes)
        elif self.config.backend == StorageBackend.GCS:
            await self._write_gcs(partition_key, record_type, filename, content_bytes)

        self._stats["batches_written"] += 1
        self._stats["bytes_written"] += len(content_bytes)

        logger.debug(f"Wrote {len(records)} {record_type} to {partition_key}/{filename}")

    async def _write_local(
        self,
        partition_key: str,
        record_type: str,
        filename: str,
        content: bytes,
    ):
        """Write to local filesystem."""
        path = Path(self.config.base_path) / record_type / partition_key
        path.mkdir(parents=True, exist_ok=True)

        file_path = path / filename
        file_path.write_bytes(content)

    async def _write_s3(
        self,
        partition_key: str,
        record_type: str,
        filename: str,
        content: bytes,
    ):
        """Write to S3."""
        if not self._s3_client:
            return

        key = f"{self.config.prefix}/{record_type}/{partition_key}/{filename}"

        self._s3_client.put_object(
            Bucket=self.config.bucket,
            Key=key,
            Body=content,
        )

    async def _write_gcs(
        self,
        partition_key: str,
        record_type: str,
        filename: str,
        content: bytes,
    ):
        """Write to GCS."""
        if not self._gcs_client:
            return

        bucket = self._gcs_client.bucket(self.config.bucket)
        blob_name = f"{self.config.prefix}/{record_type}/{partition_key}/{filename}"
        blob = bucket.blob(blob_name)
        blob.upload_from_string(content)

    async def read_predictions(
        self,
        model_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10000,
    ) -> List[PredictionRecord]:
        """Read predictions from storage.

        Args:
            model_name: Filter by model name
            start_date: Start date
            end_date: End date
            limit: Maximum records

        Returns:
            List of prediction records
        """
        return await self._read_records(
            "predictions",
            model_name,
            start_date,
            end_date,
            limit,
            PredictionRecord.from_dict,
        )

    async def read_actuals(
        self,
        model_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 10000,
    ) -> List[ActualRecord]:
        """Read actuals from storage.

        Args:
            model_name: Filter by model name
            start_date: Start date
            end_date: End date
            limit: Maximum records

        Returns:
            List of actual records
        """
        return await self._read_records(
            "actuals",
            model_name,
            start_date,
            end_date,
            limit,
            ActualRecord.from_dict,
        )

    async def _read_records(
        self,
        record_type: str,
        model_name: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        limit: int,
        record_class,
    ) -> List:
        """Read records from storage."""
        records = []

        if self.config.backend == StorageBackend.LOCAL:
            base_path = Path(self.config.base_path) / record_type

            if not base_path.exists():
                return records

            # Find matching files
            for file_path in sorted(base_path.rglob("*.jsonl*")):
                # Check date filter from path
                try:
                    parts = file_path.relative_to(base_path).parts
                    if len(parts) >= 3:
                        file_date = datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                        if start_date and file_date < start_date.replace(hour=0, minute=0, second=0):
                            continue
                        if end_date and file_date > end_date:
                            continue
                except (ValueError, IndexError):
                    pass

                # Read file
                content = file_path.read_bytes()
                if file_path.suffix == ".gz":
                    content = gzip.decompress(content)

                for line in content.decode().strip().split("\n"):
                    if not line:
                        continue
                    data = json.loads(line)

                    # Filter by model name
                    if model_name and data.get("model_name") != model_name:
                        continue

                    records.append(record_class(data))

                    if len(records) >= limit:
                        return records

        return records

    async def join_predictions_actuals(
        self,
        model_name: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Join predictions with their corresponding actuals.

        Args:
            model_name: Model name
            start_date: Start date
            end_date: End date

        Returns:
            List of joined records
        """
        predictions = await self.read_predictions(model_name, start_date, end_date)
        actuals = await self.read_actuals(model_name, start_date, end_date)

        # Index actuals by prediction_id
        actuals_by_pred = {a.prediction_id: a for a in actuals if a.prediction_id}

        joined = []
        for pred in predictions:
            actual = actuals_by_pred.get(pred.prediction_id)
            joined.append({
                "prediction_id": pred.prediction_id,
                "timestamp": pred.timestamp,
                "input_features": pred.input_features,
                "prediction": pred.prediction,
                "actual": actual.actual_value if actual else None,
                "has_actual": actual is not None,
            })

        return joined

    def get_partitions(self, record_type: str = "predictions") -> List[DataPartition]:
        """Get list of data partitions.

        Args:
            record_type: Type of records

        Returns:
            List of partitions
        """
        partitions = []

        if self.config.backend == StorageBackend.LOCAL:
            base_path = Path(self.config.base_path) / record_type

            if not base_path.exists():
                return partitions

            for date_dir in base_path.iterdir():
                if date_dir.is_dir():
                    for subdir in date_dir.rglob("*"):
                        if subdir.is_dir():
                            files = list(subdir.glob("*.jsonl*"))
                            if files:
                                size = sum(f.stat().st_size for f in files)
                                count = len(files)

                                partitions.append(DataPartition(
                                    partition_key=str(subdir.relative_to(base_path)),
                                    record_type=record_type,
                                    record_count=count,
                                    size_bytes=size,
                                    created_at=datetime.fromtimestamp(subdir.stat().st_mtime),
                                    path=str(subdir),
                                ))

        return partitions

    def get_stats(self) -> Dict[str, Any]:
        """Get collector statistics."""
        return {
            **self._stats,
            "buffer_predictions": len(self._prediction_buffer),
            "buffer_actuals": len(self._actual_buffer),
            "backend": self.config.backend.value,
        }
