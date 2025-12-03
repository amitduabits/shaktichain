"""Event definitions for the feature pipeline.

Defines event types from:
- Blockchain (trades, auctions, prices)
- Grid API (load, generation, frequency)
- Weather API
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types of events in the pipeline."""
    # Blockchain events
    TRADE_EXECUTED = "trade_executed"
    AUCTION_OPENED = "auction_opened"
    AUCTION_CLOSED = "auction_closed"
    AUCTION_BID = "auction_bid"
    PRICE_UPDATED = "price_updated"
    ORDER_PLACED = "order_placed"
    ORDER_CANCELLED = "order_cancelled"
    DELIVERY_CONFIRMED = "delivery_confirmed"

    # Grid events
    GRID_LOAD = "grid_load"
    GRID_FREQUENCY = "grid_frequency"
    GRID_GENERATION = "grid_generation"
    GRID_PRICE = "grid_price"

    # Weather events
    WEATHER_UPDATE = "weather_update"
    SOLAR_IRRADIANCE = "solar_irradiance"

    # System events
    HEARTBEAT = "heartbeat"
    ERROR = "error"


@dataclass
class Event(ABC):
    """Base event class."""
    event_id: str
    event_type: EventType
    timestamp: datetime
    source: str
    raw_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create from dictionary."""
        pass


@dataclass
class TradeEvent(Event):
    """Trade execution event from blockchain."""
    trade_id: str = ""
    buyer_id: str = ""
    seller_id: str = ""
    price: float = 0.0
    quantity: float = 0.0
    energy_kwh: float = 0.0
    trade_type: str = "spot"  # spot, forward, auction
    block_number: int = 0
    transaction_hash: str = ""

    def __post_init__(self):
        self.event_type = EventType.TRADE_EXECUTED

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeEvent':
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            event_id=data.get('event_id', ''),
            event_type=EventType.TRADE_EXECUTED,
            timestamp=timestamp or datetime.now(),
            source=data.get('source', 'blockchain'),
            raw_data=data.get('raw_data'),
            trade_id=data.get('trade_id', ''),
            buyer_id=data.get('buyer_id', ''),
            seller_id=data.get('seller_id', ''),
            price=float(data.get('price', 0)),
            quantity=float(data.get('quantity', 0)),
            energy_kwh=float(data.get('energy_kwh', 0)),
            trade_type=data.get('trade_type', 'spot'),
            block_number=int(data.get('block_number', 0)),
            transaction_hash=data.get('transaction_hash', ''),
        )


@dataclass
class PriceEvent(Event):
    """Price update event."""
    market: str = "day_ahead"
    price: float = 0.0
    currency: str = "INR"
    unit: str = "kWh"
    region: str = "default"
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    spread: Optional[float] = None

    def __post_init__(self):
        self.event_type = EventType.PRICE_UPDATED
        if self.bid_price and self.ask_price:
            self.spread = self.ask_price - self.bid_price

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PriceEvent':
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            event_id=data.get('event_id', ''),
            event_type=EventType.PRICE_UPDATED,
            timestamp=timestamp or datetime.now(),
            source=data.get('source', 'market'),
            raw_data=data.get('raw_data'),
            market=data.get('market', 'day_ahead'),
            price=float(data.get('price', 0)),
            currency=data.get('currency', 'INR'),
            unit=data.get('unit', 'kWh'),
            region=data.get('region', 'default'),
            bid_price=data.get('bid_price'),
            ask_price=data.get('ask_price'),
        )


@dataclass
class AuctionEvent(Event):
    """Auction event from blockchain."""
    auction_id: str = ""
    auction_type: str = "energy"  # energy, capacity, ancillary
    status: str = "open"  # open, closed, cancelled
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    min_price: float = 0.0
    max_price: float = 0.0
    total_quantity: float = 0.0
    cleared_price: Optional[float] = None
    cleared_quantity: Optional[float] = None
    num_bids: int = 0
    winning_bids: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if self.status == "open":
            self.event_type = EventType.AUCTION_OPENED
        elif self.status == "closed":
            self.event_type = EventType.AUCTION_CLOSED
        else:
            self.event_type = EventType.AUCTION_BID

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuctionEvent':
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        start_time = data.get('start_time')
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)

        end_time = data.get('end_time')
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)

        status = data.get('status', 'open')
        if status == 'open':
            event_type = EventType.AUCTION_OPENED
        elif status == 'closed':
            event_type = EventType.AUCTION_CLOSED
        else:
            event_type = EventType.AUCTION_BID

        return cls(
            event_id=data.get('event_id', ''),
            event_type=event_type,
            timestamp=timestamp or datetime.now(),
            source=data.get('source', 'blockchain'),
            raw_data=data.get('raw_data'),
            auction_id=data.get('auction_id', ''),
            auction_type=data.get('auction_type', 'energy'),
            status=status,
            start_time=start_time,
            end_time=end_time,
            min_price=float(data.get('min_price', 0)),
            max_price=float(data.get('max_price', 0)),
            total_quantity=float(data.get('total_quantity', 0)),
            cleared_price=data.get('cleared_price'),
            cleared_quantity=data.get('cleared_quantity'),
            num_bids=int(data.get('num_bids', 0)),
            winning_bids=data.get('winning_bids', []),
        )


@dataclass
class GridEvent(Event):
    """Grid state event from utility API."""
    metric_type: str = "load"  # load, frequency, generation, price
    value: float = 0.0
    unit: str = ""
    region: str = "default"
    grid_area: str = ""
    quality: str = "good"  # good, estimated, missing

    # Load-specific
    total_load_mw: Optional[float] = None
    peak_load_mw: Optional[float] = None

    # Frequency-specific
    frequency_hz: Optional[float] = None
    frequency_deviation: Optional[float] = None

    # Generation-specific
    solar_mw: Optional[float] = None
    wind_mw: Optional[float] = None
    thermal_mw: Optional[float] = None
    hydro_mw: Optional[float] = None

    def __post_init__(self):
        if self.metric_type == "load":
            self.event_type = EventType.GRID_LOAD
        elif self.metric_type == "frequency":
            self.event_type = EventType.GRID_FREQUENCY
        elif self.metric_type == "generation":
            self.event_type = EventType.GRID_GENERATION
        else:
            self.event_type = EventType.GRID_PRICE

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GridEvent':
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        metric_type = data.get('metric_type', 'load')
        if metric_type == "load":
            event_type = EventType.GRID_LOAD
        elif metric_type == "frequency":
            event_type = EventType.GRID_FREQUENCY
        elif metric_type == "generation":
            event_type = EventType.GRID_GENERATION
        else:
            event_type = EventType.GRID_PRICE

        return cls(
            event_id=data.get('event_id', ''),
            event_type=event_type,
            timestamp=timestamp or datetime.now(),
            source=data.get('source', 'grid_api'),
            raw_data=data.get('raw_data'),
            metric_type=metric_type,
            value=float(data.get('value', 0)),
            unit=data.get('unit', ''),
            region=data.get('region', 'default'),
            grid_area=data.get('grid_area', ''),
            quality=data.get('quality', 'good'),
            total_load_mw=data.get('total_load_mw'),
            peak_load_mw=data.get('peak_load_mw'),
            frequency_hz=data.get('frequency_hz'),
            frequency_deviation=data.get('frequency_deviation'),
            solar_mw=data.get('solar_mw'),
            wind_mw=data.get('wind_mw'),
            thermal_mw=data.get('thermal_mw'),
            hydro_mw=data.get('hydro_mw'),
        )


@dataclass
class WeatherEvent(Event):
    """Weather update event."""
    location: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    temperature_c: float = 0.0
    humidity_pct: float = 0.0
    wind_speed_mps: float = 0.0
    cloud_cover_pct: float = 0.0
    solar_irradiance_wm2: Optional[float] = None
    precipitation_mm: float = 0.0
    forecast_hours: int = 0

    def __post_init__(self):
        self.event_type = EventType.WEATHER_UPDATE

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeatherEvent':
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            event_id=data.get('event_id', ''),
            event_type=EventType.WEATHER_UPDATE,
            timestamp=timestamp or datetime.now(),
            source=data.get('source', 'weather_api'),
            raw_data=data.get('raw_data'),
            location=data.get('location', ''),
            latitude=float(data.get('latitude', 0)),
            longitude=float(data.get('longitude', 0)),
            temperature_c=float(data.get('temperature_c', 0)),
            humidity_pct=float(data.get('humidity_pct', 0)),
            wind_speed_mps=float(data.get('wind_speed_mps', 0)),
            cloud_cover_pct=float(data.get('cloud_cover_pct', 0)),
            solar_irradiance_wm2=data.get('solar_irradiance_wm2'),
            precipitation_mm=float(data.get('precipitation_mm', 0)),
            forecast_hours=int(data.get('forecast_hours', 0)),
        )


class EventParser:
    """Parse raw events into typed Event objects."""

    # Map event type strings to classes
    EVENT_CLASSES = {
        EventType.TRADE_EXECUTED: TradeEvent,
        EventType.PRICE_UPDATED: PriceEvent,
        EventType.AUCTION_OPENED: AuctionEvent,
        EventType.AUCTION_CLOSED: AuctionEvent,
        EventType.AUCTION_BID: AuctionEvent,
        EventType.GRID_LOAD: GridEvent,
        EventType.GRID_FREQUENCY: GridEvent,
        EventType.GRID_GENERATION: GridEvent,
        EventType.GRID_PRICE: GridEvent,
        EventType.WEATHER_UPDATE: WeatherEvent,
        EventType.SOLAR_IRRADIANCE: WeatherEvent,
    }

    @classmethod
    def parse(cls, data: Union[str, Dict[str, Any]]) -> Optional[Event]:
        """Parse raw data into an Event object.

        Args:
            data: JSON string or dictionary

        Returns:
            Parsed Event or None if parsing fails
        """
        try:
            if isinstance(data, str):
                data = json.loads(data)

            event_type_str = data.get('event_type', '')

            # Try to match event type
            try:
                event_type = EventType(event_type_str)
            except ValueError:
                logger.warning(f"Unknown event type: {event_type_str}")
                return None

            event_class = cls.EVENT_CLASSES.get(event_type)
            if not event_class:
                logger.warning(f"No parser for event type: {event_type}")
                return None

            return event_class.from_dict(data)

        except Exception as e:
            logger.error(f"Failed to parse event: {e}")
            return None

    @classmethod
    def parse_blockchain_log(cls, log: Dict[str, Any]) -> Optional[Event]:
        """Parse blockchain event log.

        Args:
            log: Raw blockchain log from The Graph or web3

        Returns:
            Parsed Event
        """
        try:
            event_name = log.get('event', log.get('__typename', ''))
            args = log.get('args', log)

            # Map blockchain event names to our event types
            event_mapping = {
                'TradeExecuted': EventType.TRADE_EXECUTED,
                'Trade': EventType.TRADE_EXECUTED,
                'PriceUpdated': EventType.PRICE_UPDATED,
                'AuctionOpened': EventType.AUCTION_OPENED,
                'AuctionClosed': EventType.AUCTION_CLOSED,
                'AuctionBid': EventType.AUCTION_BID,
                'OrderPlaced': EventType.ORDER_PLACED,
                'OrderCancelled': EventType.ORDER_CANCELLED,
            }

            event_type = event_mapping.get(event_name)
            if not event_type:
                return None

            # Convert to our format
            timestamp = log.get('blockTimestamp', log.get('timestamp'))
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp)
            elif isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            else:
                timestamp = datetime.now()

            data = {
                'event_id': f"{log.get('blockNumber', 0)}-{log.get('logIndex', 0)}",
                'event_type': event_type.value,
                'timestamp': timestamp,
                'source': 'blockchain',
                'raw_data': log,
            }

            # Extract fields based on event type
            if event_type == EventType.TRADE_EXECUTED:
                data.update({
                    'trade_id': args.get('tradeId', args.get('id', '')),
                    'buyer_id': args.get('buyer', ''),
                    'seller_id': args.get('seller', ''),
                    'price': float(args.get('price', 0)) / 1e18,
                    'quantity': float(args.get('quantity', args.get('amount', 0))),
                    'energy_kwh': float(args.get('energyKwh', args.get('energy', 0))),
                    'block_number': log.get('blockNumber', 0),
                    'transaction_hash': log.get('transactionHash', ''),
                })
            elif event_type == EventType.PRICE_UPDATED:
                data.update({
                    'price': float(args.get('price', args.get('newPrice', 0))) / 1e18,
                    'market': args.get('market', 'spot'),
                })
            elif event_type in [EventType.AUCTION_OPENED, EventType.AUCTION_CLOSED]:
                data.update({
                    'auction_id': args.get('auctionId', args.get('id', '')),
                    'status': 'open' if event_type == EventType.AUCTION_OPENED else 'closed',
                    'cleared_price': args.get('clearingPrice'),
                    'cleared_quantity': args.get('clearedQuantity'),
                })

            return cls.parse(data)

        except Exception as e:
            logger.error(f"Failed to parse blockchain log: {e}")
            return None

    @classmethod
    def parse_grid_api(cls, response: Dict[str, Any], metric_type: str) -> Optional[GridEvent]:
        """Parse grid API response.

        Args:
            response: API response dictionary
            metric_type: Type of grid metric

        Returns:
            Parsed GridEvent
        """
        try:
            timestamp = response.get('timestamp', response.get('time'))
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            elif isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp)
            else:
                timestamp = datetime.now()

            data = {
                'event_id': f"grid-{metric_type}-{timestamp.timestamp()}",
                'event_type': f"grid_{metric_type}",
                'timestamp': timestamp,
                'source': 'grid_api',
                'metric_type': metric_type,
                'region': response.get('region', 'default'),
                'quality': response.get('quality', 'good'),
            }

            if metric_type == 'load':
                data['value'] = float(response.get('load', response.get('demand', 0)))
                data['unit'] = 'MW'
                data['total_load_mw'] = data['value']
                data['peak_load_mw'] = response.get('peak')

            elif metric_type == 'frequency':
                data['value'] = float(response.get('frequency', 50.0))
                data['unit'] = 'Hz'
                data['frequency_hz'] = data['value']
                data['frequency_deviation'] = data['value'] - 50.0

            elif metric_type == 'generation':
                data['value'] = float(response.get('total', 0))
                data['unit'] = 'MW'
                data['solar_mw'] = response.get('solar')
                data['wind_mw'] = response.get('wind')
                data['thermal_mw'] = response.get('thermal')
                data['hydro_mw'] = response.get('hydro')

            elif metric_type == 'price':
                data['value'] = float(response.get('price', 0))
                data['unit'] = 'INR/kWh'

            return GridEvent.from_dict(data)

        except Exception as e:
            logger.error(f"Failed to parse grid API response: {e}")
            return None
