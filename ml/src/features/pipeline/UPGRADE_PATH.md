# SHAKTI-CHAIN Feature Pipeline: Upgrade Path to Kafka + Flink

## Current Architecture (Phase 1)

```
┌─────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│ Blockchain      │───▶│ Redis Streams     │───▶│ Python Processor  │
│ (The Graph)     │    │ (Event Queue)     │    │ (Rolling Stats)   │
└─────────────────┘    └───────────────────┘    └───────────────────┘
                                                          │
┌─────────────────┐                                       ▼
│ Grid API        │─────────────────────────────▶┌───────────────────┐
│ (REST Polling)  │                              │ Redis Feature     │
└─────────────────┘                              │ Store (TTL)       │
                                                 └───────────────────┘
                                                          │
                                                          ▼
                                                 ┌───────────────────┐
                                                 │ FastAPI Feature   │
                                                 │ Serving           │
                                                 └───────────────────┘
```

### Current Stack
- **Event Queue**: Redis Streams with consumer groups
- **Processing**: Python asyncio with in-memory rolling windows
- **Feature Store**: Redis with TTL and freshness tracking
- **Serving**: FastAPI with timeout-based fallbacks

### Limitations
- Single Python process bottleneck (~10K events/sec)
- In-memory state not horizontally scalable
- Limited exactly-once guarantees
- No native stream windowing operators

---

## Target Architecture (Phase 2)

```
┌─────────────────┐    ┌───────────────────┐    ┌───────────────────┐
│ Blockchain      │───▶│ Apache Kafka      │───▶│ Apache Flink      │
│ (The Graph)     │    │ (Event Streaming) │    │ (Stream Processor)│
└─────────────────┘    └───────────────────┘    └───────────────────┘
                                │                         │
┌─────────────────┐             │                         ▼
│ Grid API        │─────────────┘                ┌───────────────────┐
│ (Kafka Connect) │                              │ Feature Store     │
└─────────────────┘                              │ (Redis/Feast)     │
                                                 └───────────────────┘
                                                          │
                                                          ▼
                                                 ┌───────────────────┐
                                                 │ Feature Serving   │
                                                 │ (Feast/Custom)    │
                                                 └───────────────────┘
```

### Target Stack
- **Event Streaming**: Apache Kafka with Confluent Schema Registry
- **Stream Processing**: Apache Flink with exactly-once semantics
- **Feature Store**: Feast or custom Redis + offline store
- **Serving**: Feast online serving or enhanced custom API

---

## Migration Strategy

### Phase 2A: Kafka Integration (Weeks 1-2)

#### 1. Deploy Kafka Cluster

```yaml
# docker-compose.kafka.yml
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  schema-registry:
    image: confluentinc/cp-schema-registry:7.5.0
    depends_on:
      - kafka
    ports:
      - "8081:8081"
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: kafka:29092
```

#### 2. Create Kafka Topics

```bash
# Event topics
kafka-topics --create --topic shakti.events.trades --partitions 6 --replication-factor 1
kafka-topics --create --topic shakti.events.prices --partitions 6 --replication-factor 1
kafka-topics --create --topic shakti.events.grid --partitions 3 --replication-factor 1

# Feature topics (compacted)
kafka-topics --create --topic shakti.features.realtime \
  --partitions 6 --replication-factor 1 \
  --config cleanup.policy=compact
```

#### 3. Update Ingesters to Produce to Kafka

```python
# kafka_ingestion.py
from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

class KafkaEventProducer:
    def __init__(self, bootstrap_servers: str, schema_registry_url: str):
        self.producer = Producer({
            'bootstrap.servers': bootstrap_servers,
            'acks': 'all',
            'enable.idempotence': True,
        })

        self.schema_registry = SchemaRegistryClient({
            'url': schema_registry_url
        })

    async def produce_trade_event(self, event: TradeEvent):
        """Produce trade event to Kafka."""
        self.producer.produce(
            topic='shakti.events.trades',
            key=event.trade_id.encode(),
            value=event.to_avro(),
            callback=self._delivery_callback,
        )

    def _delivery_callback(self, err, msg):
        if err:
            logger.error(f"Delivery failed: {err}")
```

#### 4. Dual-Write During Migration

```python
# hybrid_ingester.py
class HybridEventIngester:
    """Write to both Redis Streams and Kafka during migration."""

    def __init__(
        self,
        redis_queue: RedisEventQueue,
        kafka_producer: KafkaEventProducer,
        enable_kafka: bool = False,
    ):
        self.redis_queue = redis_queue
        self.kafka_producer = kafka_producer
        self.enable_kafka = enable_kafka

    async def publish(self, event: Event) -> bool:
        # Always write to Redis (current system)
        await self.redis_queue.publish(event)

        # Also write to Kafka if enabled
        if self.enable_kafka:
            await self.kafka_producer.produce(event)

        return True
```

---

### Phase 2B: Flink Stream Processing (Weeks 3-4)

#### 1. Deploy Flink Cluster

```yaml
# docker-compose.flink.yml
services:
  jobmanager:
    image: flink:1.18-scala_2.12
    ports:
      - "8082:8081"
    command: jobmanager
    environment:
      FLINK_PROPERTIES: |
        jobmanager.rpc.address: jobmanager
        state.checkpoints.dir: file:///checkpoints
        state.backend: rocksdb

  taskmanager:
    image: flink:1.18-scala_2.12
    depends_on:
      - jobmanager
    command: taskmanager
    environment:
      FLINK_PROPERTIES: |
        jobmanager.rpc.address: jobmanager
        taskmanager.numberOfTaskSlots: 4
```

#### 2. Flink Feature Processing Job (PyFlink)

```python
# flink_feature_job.py
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer, FlinkKafkaProducer
from pyflink.datastream.window import TumblingEventTimeWindows, SlidingEventTimeWindows
from pyflink.common.time import Time

def create_feature_pipeline():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.enable_checkpointing(60000)  # 1 minute checkpoints

    # Kafka source
    kafka_source = FlinkKafkaConsumer(
        topics=['shakti.events.trades', 'shakti.events.prices'],
        deserialization_schema=TradeEventSchema(),
        properties={
            'bootstrap.servers': 'kafka:29092',
            'group.id': 'flink-feature-processor',
        }
    )
    kafka_source.set_start_from_latest()

    # Create stream
    trade_stream = env.add_source(kafka_source)

    # Rolling statistics with sliding window
    rolling_stats = (
        trade_stream
        .key_by(lambda e: e.market)
        .window(SlidingEventTimeWindows.of(Time.hours(1), Time.minutes(1)))
        .aggregate(
            RollingStatsAggregator(),
            output_type=RollingStatsOutput,
        )
    )

    # VWAP calculation
    vwap = (
        trade_stream
        .key_by(lambda e: e.market)
        .window(TumblingEventTimeWindows.of(Time.hours(1)))
        .aggregate(VWAPAggregator())
    )

    # Write to feature store via Kafka
    rolling_stats.add_sink(
        FlinkKafkaProducer(
            topic='shakti.features.realtime',
            serialization_schema=FeatureSchema(),
            producer_config={'bootstrap.servers': 'kafka:29092'},
        )
    )

    return env

class RollingStatsAggregator(AggregateFunction):
    """Flink aggregator for rolling statistics."""

    def create_accumulator(self):
        return {'count': 0, 'sum': 0, 'sum_sq': 0, 'min': float('inf'), 'max': float('-inf')}

    def add(self, value, accumulator):
        accumulator['count'] += 1
        accumulator['sum'] += value.price
        accumulator['sum_sq'] += value.price ** 2
        accumulator['min'] = min(accumulator['min'], value.price)
        accumulator['max'] = max(accumulator['max'], value.price)
        return accumulator

    def get_result(self, accumulator):
        count = accumulator['count']
        if count == 0:
            return None
        mean = accumulator['sum'] / count
        variance = (accumulator['sum_sq'] / count) - (mean ** 2)
        return RollingStatsOutput(
            count=count,
            mean=mean,
            std=variance ** 0.5,
            min=accumulator['min'],
            max=accumulator['max'],
        )

    def merge(self, a, b):
        return {
            'count': a['count'] + b['count'],
            'sum': a['sum'] + b['sum'],
            'sum_sq': a['sum_sq'] + b['sum_sq'],
            'min': min(a['min'], b['min']),
            'max': max(a['max'], b['max']),
        }
```

#### 3. Feature Store Sink Connector

```python
# redis_sink.py
from pyflink.datastream import SinkFunction

class RedisFeatureSink(SinkFunction):
    """Sink features to Redis store."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None

    def open(self, runtime_context):
        import redis
        self._redis = redis.from_url(self.redis_url)

    def invoke(self, feature: FeatureValue, context):
        key = f"feature:{feature.entity_type}:{feature.entity_id}:{feature.name}"
        self._redis.setex(
            key,
            feature.ttl_seconds,
            json.dumps(feature.to_dict()),
        )
```

---

### Phase 2C: Feast Integration (Weeks 5-6)

#### 1. Feature Repository Structure

```
feature_repo/
├── feature_repo.yaml
├── features/
│   ├── trading_features.py
│   ├── forecast_features.py
│   └── anomaly_features.py
└── data_sources/
    ├── kafka_source.py
    └── batch_source.py
```

#### 2. Feature Definitions

```python
# features/trading_features.py
from feast import Entity, Feature, FeatureView, FileSource, KafkaSource
from feast.types import Float64, Int64

# Entity definition
market = Entity(
    name="market",
    description="Energy market identifier",
    value_type=ValueType.STRING,
)

# Kafka source for streaming features
trading_kafka_source = KafkaSource(
    name="trading_stream",
    kafka_bootstrap_servers="kafka:29092",
    topic="shakti.features.realtime",
    timestamp_field="event_timestamp",
    message_format=AvroFormat(schema_registry_url="http://schema-registry:8081"),
)

# Feature view
trading_features = FeatureView(
    name="trading_features",
    entities=[market],
    ttl=timedelta(hours=1),
    features=[
        Feature(name="spot_price", dtype=Float64),
        Feature(name="price_velocity_1m", dtype=Float64),
        Feature(name="price_velocity_5m", dtype=Float64),
        Feature(name="volatility_1h", dtype=Float64),
        Feature(name="vwap_1h", dtype=Float64),
        Feature(name="order_imbalance", dtype=Float64),
        Feature(name="trade_count_1h", dtype=Int64),
        Feature(name="volume_1h", dtype=Float64),
    ],
    online=True,
    source=trading_kafka_source,
)
```

#### 3. Feast Feature Server

```yaml
# feature_repo.yaml
project: shakti_chain
registry: gs://shakti-feast/registry.db
provider: gcp

online_store:
  type: redis
  connection_string: redis://redis:6379

offline_store:
  type: bigquery
  project: shakti-chain
  dataset: feast_offline
```

---

## Interface Compatibility

### Existing Interface (Preserved)

```python
# The FeatureServer interface remains the same
server = FeatureServer(store=redis_store)

# Get features - works with both backends
features = await server.get_features(
    feature_set_name="trading",
    entity_id="spot",
)
```

### New Feast Interface (Added)

```python
# Feast-based serving (optional)
from feast import FeatureStore

store = FeatureStore(repo_path="feature_repo/")

# Online features
features = store.get_online_features(
    features=["trading_features:spot_price", "trading_features:vwap_1h"],
    entity_rows=[{"market": "spot"}],
).to_dict()
```

### Adapter Pattern

```python
# feature_adapter.py
class FeatureStoreAdapter:
    """Adapter to switch between custom and Feast backends."""

    def __init__(self, backend: str = "custom"):
        self.backend = backend

        if backend == "feast":
            self._store = FeatureStore(repo_path="feature_repo/")
        else:
            self._store = RedisFeatureStore()

    async def get_trading_features(self, market: str) -> Dict[str, Any]:
        if self.backend == "feast":
            return self._store.get_online_features(
                features=[
                    "trading_features:spot_price",
                    "trading_features:vwap_1h",
                ],
                entity_rows=[{"market": market}],
            ).to_dict()
        else:
            server = FeatureServer(store=self._store)
            vector = await server.get_features("trading", market)
            return vector.features
```

---

## Migration Checklist

### Pre-Migration
- [ ] Set up Kafka cluster (dev/staging)
- [ ] Configure Schema Registry
- [ ] Create Kafka topics with appropriate partitioning
- [ ] Set up Flink cluster
- [ ] Test Flink jobs in development

### Phase 2A: Kafka
- [ ] Deploy Kafka to production
- [ ] Enable dual-write (Redis + Kafka)
- [ ] Verify message delivery and ordering
- [ ] Monitor Kafka lag and throughput
- [ ] Switch blockchain ingester to Kafka-only
- [ ] Switch grid API ingester to Kafka-only

### Phase 2B: Flink
- [ ] Deploy Flink to production
- [ ] Deploy feature processing jobs
- [ ] Verify exactly-once semantics
- [ ] Compare feature values (old vs new)
- [ ] Gradual traffic shift to Flink-computed features
- [ ] Deprecate Python processor

### Phase 2C: Feast (Optional)
- [ ] Set up Feast repository
- [ ] Define feature views
- [ ] Configure online/offline stores
- [ ] Migrate model service to Feast
- [ ] Set up feature monitoring

---

## Rollback Plan

### Quick Rollback (< 5 minutes)
1. Disable Kafka writes in ingester config
2. Switch feature server to read from Redis (Python-computed)
3. Features continue from last Python-computed values

### Full Rollback (< 30 minutes)
1. Stop Flink jobs
2. Re-enable Python processor
3. Clear Kafka topics or reset consumer offsets
4. Verify feature freshness

---

## Performance Expectations

| Metric | Current (Redis+Python) | Target (Kafka+Flink) |
|--------|------------------------|----------------------|
| Events/sec | ~10,000 | ~1,000,000 |
| Feature latency | ~50ms | ~10ms |
| Exactly-once | Best effort | Guaranteed |
| Horizontal scaling | Manual | Automatic |
| State management | In-memory | RocksDB checkpoints |
| Recovery time | Minutes | Seconds |

---

## Cost Considerations

### Current Stack
- Redis: $50-200/month (managed)
- Python workers: $100-300/month (2-4 instances)
- **Total: ~$150-500/month**

### Target Stack
- Kafka (Confluent Cloud): $200-1000/month
- Flink (managed): $300-1500/month
- Redis: $50-200/month
- **Total: ~$550-2700/month**

### When to Upgrade
- Event volume > 10K/sec sustained
- Need exactly-once guarantees
- Multi-region deployment required
- Feature computation SLA < 100ms p99
