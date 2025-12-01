"""
Event Listener Module.

Listens to blockchain events from SHAKTI-CHAIN smart contracts.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from threading import Thread, Event

from web3 import Web3
from web3.contract import Contract

from .provider import Web3Provider, get_web3_provider
from .contracts import ContractManager, get_contract_manager

logger = logging.getLogger(__name__)


@dataclass
class BlockchainEvent:
    """Represents a blockchain event."""
    event_name: str
    contract_name: str
    block_number: int
    transaction_hash: str
    log_index: int
    args: Dict[str, Any]
    timestamp: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_name": self.event_name,
            "contract_name": self.contract_name,
            "block_number": self.block_number,
            "transaction_hash": self.transaction_hash,
            "log_index": self.log_index,
            "args": self.args,
            "timestamp": self.timestamp,
        }


EventCallback = Callable[[BlockchainEvent], None]


@dataclass
class EventSubscription:
    """Represents an event subscription."""
    contract_name: str
    event_name: str
    callback: EventCallback
    from_block: int
    active: bool = True


class EventListener:
    """
    Listens to blockchain events from SHAKTI-CHAIN contracts.

    Supports:
    - Polling for new events
    - Event subscriptions with callbacks
    - Historical event fetching
    """

    def __init__(
        self,
        provider: Optional[Web3Provider] = None,
        contract_manager: Optional[ContractManager] = None,
        poll_interval: int = 5,
    ):
        """
        Initialize event listener.

        Args:
            provider: Web3Provider instance.
            contract_manager: ContractManager instance.
            poll_interval: Polling interval in seconds.
        """
        self.provider = provider or get_web3_provider()
        self.contracts = contract_manager or get_contract_manager(self.provider)
        self.poll_interval = poll_interval

        self._subscriptions: Dict[str, EventSubscription] = {}
        self._last_processed_block: int = 0
        self._running = False
        self._stop_event = Event()
        self._listener_thread: Optional[Thread] = None

    @property
    def web3(self) -> Web3:
        """Get Web3 instance."""
        return self.provider.web3

    def subscribe(
        self,
        contract_name: str,
        event_name: str,
        callback: EventCallback,
        from_block: Optional[int] = None,
    ) -> str:
        """
        Subscribe to a contract event.

        Args:
            contract_name: Name of the contract (e.g., "ShaktiToken").
            event_name: Name of the event (e.g., "Transfer").
            callback: Callback function to handle events.
            from_block: Starting block number. Uses current block if None.

        Returns:
            Subscription ID.
        """
        subscription_id = f"{contract_name}:{event_name}:{id(callback)}"

        if from_block is None:
            from_block = self.web3.eth.block_number

        subscription = EventSubscription(
            contract_name=contract_name,
            event_name=event_name,
            callback=callback,
            from_block=from_block,
        )

        self._subscriptions[subscription_id] = subscription
        logger.info(f"Subscribed to {contract_name}.{event_name} from block {from_block}")

        return subscription_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from an event.

        Args:
            subscription_id: Subscription ID returned from subscribe().

        Returns:
            True if unsubscribed, False if not found.
        """
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            logger.info(f"Unsubscribed: {subscription_id}")
            return True
        return False

    def _get_contract(self, name: str) -> Optional[Contract]:
        """Get contract by name."""
        name_lower = name.lower()
        if name_lower == "shaktitoken":
            return self.contracts.shakti_token
        elif name_lower == "energyauction":
            return self.contracts.energy_auction
        elif name_lower == "stakingpool":
            return self.contracts.staking_pool
        elif name_lower == "reputationsystem":
            return self.contracts.reputation_system
        return None

    def get_events(
        self,
        contract_name: str,
        event_name: str,
        from_block: int,
        to_block: Optional[int] = None,
    ) -> List[BlockchainEvent]:
        """
        Get historical events.

        Args:
            contract_name: Contract name.
            event_name: Event name.
            from_block: Starting block.
            to_block: Ending block. Uses latest if None.

        Returns:
            List of BlockchainEvent objects.
        """
        contract = self._get_contract(contract_name)
        if not contract:
            logger.warning(f"Contract not found: {contract_name}")
            return []

        if to_block is None:
            to_block = self.web3.eth.block_number

        try:
            event_filter = getattr(contract.events, event_name)
            logs = event_filter.get_logs(fromBlock=from_block, toBlock=to_block)

            events = []
            for log in logs:
                # Get block timestamp
                block = self.web3.eth.get_block(log["blockNumber"])
                timestamp = block["timestamp"] if block else None

                event = BlockchainEvent(
                    event_name=event_name,
                    contract_name=contract_name,
                    block_number=log["blockNumber"],
                    transaction_hash=log["transactionHash"].hex(),
                    log_index=log["logIndex"],
                    args=dict(log["args"]),
                    timestamp=timestamp,
                )
                events.append(event)

            return events

        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return []

    def _poll_events(self) -> None:
        """Poll for new events (runs in background thread)."""
        while not self._stop_event.is_set():
            try:
                current_block = self.web3.eth.block_number

                # Process each subscription
                for sub_id, subscription in list(self._subscriptions.items()):
                    if not subscription.active:
                        continue

                    from_block = max(subscription.from_block, self._last_processed_block + 1)

                    if from_block > current_block:
                        continue

                    events = self.get_events(
                        subscription.contract_name,
                        subscription.event_name,
                        from_block,
                        current_block,
                    )

                    for event in events:
                        try:
                            subscription.callback(event)
                        except Exception as e:
                            logger.error(f"Event callback error: {e}")

                self._last_processed_block = current_block

            except Exception as e:
                logger.error(f"Event polling error: {e}")

            # Wait for next poll
            self._stop_event.wait(self.poll_interval)

    def start(self, from_block: Optional[int] = None) -> None:
        """
        Start the event listener.

        Args:
            from_block: Starting block for all subscriptions.
        """
        if self._running:
            logger.warning("Event listener already running")
            return

        if from_block is not None:
            self._last_processed_block = from_block
        else:
            self._last_processed_block = self.web3.eth.block_number

        self._running = True
        self._stop_event.clear()
        self._listener_thread = Thread(target=self._poll_events, daemon=True)
        self._listener_thread.start()

        logger.info(f"Event listener started from block {self._last_processed_block}")

    def stop(self) -> None:
        """Stop the event listener."""
        if not self._running:
            return

        self._stop_event.set()
        self._running = False

        if self._listener_thread:
            self._listener_thread.join(timeout=10)
            self._listener_thread = None

        logger.info("Event listener stopped")

    @property
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running

    @property
    def last_processed_block(self) -> int:
        """Get the last processed block number."""
        return self._last_processed_block


# Convenience functions for getting specific events

def get_recent_transfers(
    provider: Optional[Web3Provider] = None,
    blocks: int = 1000,
) -> List[BlockchainEvent]:
    """
    Get recent token transfer events.

    Args:
        provider: Web3Provider instance.
        blocks: Number of blocks to look back.

    Returns:
        List of Transfer events.
    """
    listener = EventListener(provider=provider)
    current_block = listener.web3.eth.block_number
    from_block = max(0, current_block - blocks)

    return listener.get_events("ShaktiToken", "Transfer", from_block, current_block)


def get_recent_trades(
    provider: Optional[Web3Provider] = None,
    blocks: int = 1000,
) -> List[BlockchainEvent]:
    """
    Get recent trade execution events.

    Args:
        provider: Web3Provider instance.
        blocks: Number of blocks to look back.

    Returns:
        List of TradeExecuted events.
    """
    listener = EventListener(provider=provider)
    current_block = listener.web3.eth.block_number
    from_block = max(0, current_block - blocks)

    return listener.get_events("EnergyAuction", "TradeExecuted", from_block, current_block)


def get_recent_bids(
    provider: Optional[Web3Provider] = None,
    blocks: int = 1000,
) -> List[BlockchainEvent]:
    """
    Get recent bid submission events.

    Args:
        provider: Web3Provider instance.
        blocks: Number of blocks to look back.

    Returns:
        List of BidSubmitted events.
    """
    listener = EventListener(provider=provider)
    current_block = listener.web3.eth.block_number
    from_block = max(0, current_block - blocks)

    return listener.get_events("EnergyAuction", "BidSubmitted", from_block, current_block)
