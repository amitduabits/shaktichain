"""
Blockchain Service Module.

Main service class that provides a unified interface for all blockchain operations.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from web3 import Web3

from .provider import Web3Provider, get_web3_provider, NetworkType
from .contracts import ContractManager, get_contract_manager
from .transactions import TransactionManager, TransactionResult, TransactionStatus
from .events import EventListener, BlockchainEvent
from .sync import BlockchainSync, SyncState

logger = logging.getLogger(__name__)


class AuctionState(int, Enum):
    """Auction round states."""
    NONE = 0
    OPEN = 1
    CLEARING = 2
    SETTLED = 3
    CANCELLED = 4


class ReputationTier(int, Enum):
    """Reputation tier levels."""
    UNRANKED = 0
    BRONZE = 1
    SILVER = 2
    GOLD = 3
    PLATINUM = 4


@dataclass
class AuctionStatus:
    """Auction round status."""
    round_id: int
    start_time: int
    end_time: int
    clearing_price: int
    total_bid_volume: int
    total_ask_volume: int
    state: AuctionState
    is_open: bool
    time_remaining: int


@dataclass
class UserReputation:
    """User reputation info."""
    address: str
    reputation: int
    tier: ReputationTier
    tier_name: str
    total_trades: int
    successful_trades: int
    failed_deliveries: int
    disputes_won: int
    disputes_lost: int
    is_kyc_verified: bool
    is_flagged: bool


@dataclass
class StakeInfo:
    """User staking info."""
    address: str
    amount: int
    amount_formatted: str
    shares: int
    staked_at: int
    lock_end_time: int
    pending_rewards: int
    pending_rewards_formatted: str
    is_locked: bool


class BlockchainService:
    """
    Main blockchain service for SHAKTI-CHAIN.

    Provides a unified interface for:
    - Token operations (balance, transfer, approve)
    - Auction operations (submit bid/ask, get status)
    - Staking operations (stake, unstake, claim)
    - Reputation queries
    - Event synchronization
    """

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        private_key: Optional[str] = None,
        network: NetworkType = NetworkType.HARDHAT,
        database: Optional[Any] = None,
    ):
        """
        Initialize blockchain service.

        Args:
            rpc_url: RPC endpoint URL.
            private_key: Private key for signing transactions.
            network: Network type to connect to.
            database: Database instance for sync operations.
        """
        self.provider = Web3Provider(
            rpc_url=rpc_url,
            private_key=private_key,
            network=network,
        )
        self.contracts = ContractManager(self.provider)
        self.transactions = TransactionManager(self.provider)
        self.events = EventListener(self.provider, self.contracts)

        self._sync: Optional[BlockchainSync] = None
        if database:
            self._sync = BlockchainSync(database, self.provider, self.contracts)

    # === Connection Methods ===

    @property
    def is_connected(self) -> bool:
        """Check if connected to blockchain."""
        return self.provider.is_connected

    @property
    def network(self) -> NetworkType:
        """Get current network."""
        return self.provider.network

    @property
    def address(self) -> Optional[str]:
        """Get the signing account address."""
        return self.provider.address

    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information."""
        return {
            "connected": self.is_connected,
            "network": self.network.value,
            "chain_id": self.provider.chain_id,
            "rpc_url": self.provider.rpc_url,
            "account": self.address,
            "block_number": self.provider.get_block_number() if self.is_connected else None,
        }

    # === Token Methods ===

    def get_token_balance(self, address: str) -> int:
        """
        Get SHAKTI token balance.

        Args:
            address: Address to check.

        Returns:
            Balance in wei.
        """
        contract = self.contracts.shakti_token
        if not contract:
            raise ValueError("ShaktiToken not deployed on this network")

        checksum = Web3.to_checksum_address(address)
        return contract.functions.balanceOf(checksum).call()

    def get_token_balance_formatted(self, address: str) -> str:
        """
        Get SHAKTI token balance in human-readable format.

        Args:
            address: Address to check.

        Returns:
            Balance as decimal string.
        """
        balance = self.get_token_balance(address)
        return str(Web3.from_wei(balance, "ether"))

    def transfer_tokens(
        self,
        to: str,
        amount: int,
        wait: bool = True,
    ) -> TransactionResult:
        """
        Transfer SHAKTI tokens.

        Args:
            to: Recipient address.
            amount: Amount in wei.
            wait: Wait for confirmation.

        Returns:
            TransactionResult.
        """
        contract = self.contracts.shakti_token
        if not contract:
            raise ValueError("ShaktiToken not deployed on this network")

        return self.transactions.execute_contract_call(
            contract,
            "transfer",
            Web3.to_checksum_address(to),
            amount,
            description=f"Transfer {Web3.from_wei(amount, 'ether')} SHAKTI to {to[:10]}...",
            wait=wait,
        )

    def approve_tokens(
        self,
        spender: str,
        amount: int,
        wait: bool = True,
    ) -> TransactionResult:
        """
        Approve token spending.

        Args:
            spender: Spender address.
            amount: Amount in wei.
            wait: Wait for confirmation.

        Returns:
            TransactionResult.
        """
        contract = self.contracts.shakti_token
        if not contract:
            raise ValueError("ShaktiToken not deployed on this network")

        return self.transactions.execute_contract_call(
            contract,
            "approve",
            Web3.to_checksum_address(spender),
            amount,
            description=f"Approve {Web3.from_wei(amount, 'ether')} SHAKTI for {spender[:10]}...",
            wait=wait,
        )

    def get_allowance(self, owner: str, spender: str) -> int:
        """
        Get token allowance.

        Args:
            owner: Token owner address.
            spender: Spender address.

        Returns:
            Allowance in wei.
        """
        contract = self.contracts.shakti_token
        if not contract:
            raise ValueError("ShaktiToken not deployed on this network")

        return contract.functions.allowance(
            Web3.to_checksum_address(owner),
            Web3.to_checksum_address(spender),
        ).call()

    # === Auction Methods ===

    def get_current_round(self) -> int:
        """Get current auction round ID."""
        contract = self.contracts.energy_auction
        if not contract:
            raise ValueError("EnergyAuction not deployed on this network")

        return contract.functions.getCurrentRound().call()

    def get_auction_status(self, round_id: Optional[int] = None) -> AuctionStatus:
        """
        Get auction round status.

        Args:
            round_id: Round ID. Uses current round if None.

        Returns:
            AuctionStatus object.
        """
        contract = self.contracts.energy_auction
        if not contract:
            raise ValueError("EnergyAuction not deployed on this network")

        if round_id is None:
            round_id = self.get_current_round()

        info = contract.functions.getRoundInfo(round_id).call()
        start_time, end_time, clearing_price, bid_volume, ask_volume, state = info

        import time
        current_time = int(time.time())
        is_open = state == AuctionState.OPEN
        time_remaining = max(0, end_time - current_time) if is_open else 0

        return AuctionStatus(
            round_id=round_id,
            start_time=start_time,
            end_time=end_time,
            clearing_price=clearing_price,
            total_bid_volume=bid_volume,
            total_ask_volume=ask_volume,
            state=AuctionState(state),
            is_open=is_open,
            time_remaining=time_remaining,
        )

    def submit_bid(
        self,
        quantity: int,
        max_price: int,
        wait: bool = True,
    ) -> TransactionResult:
        """
        Submit a buy order (bid).

        Args:
            quantity: Energy quantity in wei.
            max_price: Maximum price in wei.
            wait: Wait for confirmation.

        Returns:
            TransactionResult.
        """
        contract = self.contracts.energy_auction
        if not contract:
            raise ValueError("EnergyAuction not deployed on this network")

        return self.transactions.execute_contract_call(
            contract,
            "submitBid",
            quantity,
            max_price,
            description=f"Submit bid: {Web3.from_wei(quantity, 'ether')} kWh @ {Web3.from_wei(max_price, 'ether')} SHAKTI",
            wait=wait,
        )

    def submit_ask(
        self,
        quantity: int,
        min_price: int,
        wait: bool = True,
    ) -> TransactionResult:
        """
        Submit a sell order (ask).

        Args:
            quantity: Energy quantity in wei.
            min_price: Minimum price in wei.
            wait: Wait for confirmation.

        Returns:
            TransactionResult.
        """
        contract = self.contracts.energy_auction
        if not contract:
            raise ValueError("EnergyAuction not deployed on this network")

        return self.transactions.execute_contract_call(
            contract,
            "submitAsk",
            quantity,
            min_price,
            description=f"Submit ask: {Web3.from_wei(quantity, 'ether')} kWh @ {Web3.from_wei(min_price, 'ether')} SHAKTI",
            wait=wait,
        )

    def cancel_order(self, order_id: int, wait: bool = True) -> TransactionResult:
        """
        Cancel an order.

        Args:
            order_id: Order ID to cancel.
            wait: Wait for confirmation.

        Returns:
            TransactionResult.
        """
        contract = self.contracts.energy_auction
        if not contract:
            raise ValueError("EnergyAuction not deployed on this network")

        return self.transactions.execute_contract_call(
            contract,
            "cancelOrder",
            order_id,
            description=f"Cancel order #{order_id}",
            wait=wait,
        )

    def get_order(self, order_id: int) -> Dict[str, Any]:
        """
        Get order details.

        Args:
            order_id: Order ID.

        Returns:
            Order details dictionary.
        """
        contract = self.contracts.energy_auction
        if not contract:
            raise ValueError("EnergyAuction not deployed on this network")

        result = contract.functions.getOrder(order_id).call()
        trader, round_id, order_type, quantity, price, status, matched_qty, matched_price = result

        return {
            "order_id": order_id,
            "trader": trader,
            "round_id": round_id,
            "order_type": "bid" if order_type == 0 else "ask",
            "quantity": quantity,
            "quantity_formatted": str(Web3.from_wei(quantity, "ether")),
            "price": price,
            "price_formatted": str(Web3.from_wei(price, "ether")),
            "status": ["pending", "matched", "partial", "cancelled", "expired"][status],
            "matched_quantity": matched_qty,
            "matched_price": matched_price,
        }

    def get_user_orders(self, address: str, round_id: int) -> List[int]:
        """
        Get user's order IDs for a round.

        Args:
            address: User address.
            round_id: Round ID.

        Returns:
            List of order IDs.
        """
        contract = self.contracts.energy_auction
        if not contract:
            raise ValueError("EnergyAuction not deployed on this network")

        return contract.functions.getUserOrders(
            Web3.to_checksum_address(address),
            round_id,
        ).call()

    # === Staking Methods ===

    def get_stake_info(self, address: str) -> StakeInfo:
        """
        Get user's stake information.

        Args:
            address: User address.

        Returns:
            StakeInfo object.
        """
        contract = self.contracts.staking_pool
        if not contract:
            raise ValueError("StakingPool not deployed on this network")

        checksum = Web3.to_checksum_address(address)
        result = contract.functions.getStakeInfo(checksum).call()
        amount, shares, staked_at, lock_end, pending = result

        import time
        current_time = int(time.time())
        is_locked = lock_end > current_time

        return StakeInfo(
            address=address,
            amount=amount,
            amount_formatted=str(Web3.from_wei(amount, "ether")),
            shares=shares,
            staked_at=staked_at,
            lock_end_time=lock_end,
            pending_rewards=pending,
            pending_rewards_formatted=str(Web3.from_wei(pending, "ether")),
            is_locked=is_locked,
        )

    def stake(self, amount: int, wait: bool = True) -> TransactionResult:
        """
        Stake tokens.

        Args:
            amount: Amount to stake in wei.
            wait: Wait for confirmation.

        Returns:
            TransactionResult.
        """
        contract = self.contracts.staking_pool
        if not contract:
            raise ValueError("StakingPool not deployed on this network")

        return self.transactions.execute_contract_call(
            contract,
            "stake",
            amount,
            description=f"Stake {Web3.from_wei(amount, 'ether')} SHAKTI",
            wait=wait,
        )

    def unstake(self, amount: int, wait: bool = True) -> TransactionResult:
        """
        Unstake tokens.

        Args:
            amount: Amount to unstake in wei.
            wait: Wait for confirmation.

        Returns:
            TransactionResult.
        """
        contract = self.contracts.staking_pool
        if not contract:
            raise ValueError("StakingPool not deployed on this network")

        return self.transactions.execute_contract_call(
            contract,
            "unstake",
            amount,
            description=f"Unstake {Web3.from_wei(amount, 'ether')} SHAKTI",
            wait=wait,
        )

    def claim_rewards(self, wait: bool = True) -> TransactionResult:
        """
        Claim staking rewards.

        Args:
            wait: Wait for confirmation.

        Returns:
            TransactionResult.
        """
        contract = self.contracts.staking_pool
        if not contract:
            raise ValueError("StakingPool not deployed on this network")

        return self.transactions.execute_contract_call(
            contract,
            "claimRewards",
            description="Claim staking rewards",
            wait=wait,
        )

    def get_staking_stats(self) -> Dict[str, Any]:
        """Get staking pool statistics."""
        contract = self.contracts.staking_pool
        if not contract:
            raise ValueError("StakingPool not deployed on this network")

        total_staked = contract.functions.totalStaked().call()
        reward_rate = contract.functions.rewardRate().call()
        min_stake = contract.functions.minStakeAmount().call()
        lock_period = contract.functions.lockPeriod().call()

        try:
            apr = contract.functions.getAPR().call()
        except Exception:
            apr = 0

        return {
            "total_staked": total_staked,
            "total_staked_formatted": str(Web3.from_wei(total_staked, "ether")),
            "reward_rate": reward_rate,
            "min_stake_amount": min_stake,
            "min_stake_formatted": str(Web3.from_wei(min_stake, "ether")),
            "lock_period": lock_period,
            "apr": apr / 100 if apr else 0,  # Convert from basis points
        }

    # === Reputation Methods ===

    def get_reputation(self, address: str) -> UserReputation:
        """
        Get user's reputation info.

        Args:
            address: User address.

        Returns:
            UserReputation object.
        """
        contract = self.contracts.reputation_system
        if not contract:
            raise ValueError("ReputationSystem not deployed on this network")

        checksum = Web3.to_checksum_address(address)
        result = contract.functions.getUserInfo(checksum).call()

        reputation, tier, total_trades, successful, failed, won, lost, kyc, flagged = result

        tier_names = ["Unranked", "Bronze", "Silver", "Gold", "Platinum"]

        return UserReputation(
            address=address,
            reputation=reputation,
            tier=ReputationTier(tier),
            tier_name=tier_names[tier],
            total_trades=total_trades,
            successful_trades=successful,
            failed_deliveries=failed,
            disputes_won=won,
            disputes_lost=lost,
            is_kyc_verified=kyc,
            is_flagged=flagged,
        )

    def is_registered(self, address: str) -> bool:
        """Check if user is registered."""
        contract = self.contracts.reputation_system
        if not contract:
            raise ValueError("ReputationSystem not deployed on this network")

        return contract.functions.isRegistered(Web3.to_checksum_address(address)).call()

    def register_user(self, wait: bool = True) -> TransactionResult:
        """
        Register as a prosumer.

        Args:
            wait: Wait for confirmation.

        Returns:
            TransactionResult.
        """
        contract = self.contracts.reputation_system
        if not contract:
            raise ValueError("ReputationSystem not deployed on this network")

        return self.transactions.execute_contract_call(
            contract,
            "register",
            description="Register as prosumer",
            wait=wait,
        )

    # === Sync Methods ===

    def start_sync(self, from_block: Optional[int] = None) -> None:
        """Start background event synchronization."""
        if self._sync:
            self._sync.start_background_sync(from_block)

    def stop_sync(self) -> None:
        """Stop background event synchronization."""
        if self._sync:
            self._sync.stop_background_sync()

    def get_sync_state(self) -> Optional[SyncState]:
        """Get synchronization state."""
        return self._sync.state if self._sync else None

    def get_synced_trades(self, round_id: Optional[int] = None, limit: int = 100) -> List[Dict]:
        """Get synced trades from database."""
        if self._sync:
            return self._sync.get_synced_trades(round_id, limit)
        return []


# Singleton instance
_blockchain_service: Optional[BlockchainService] = None


def get_blockchain_service(
    rpc_url: Optional[str] = None,
    private_key: Optional[str] = None,
    network: Optional[NetworkType] = None,
    database: Optional[Any] = None,
    force_new: bool = False,
) -> BlockchainService:
    """
    Get or create the blockchain service singleton.

    Args:
        rpc_url: RPC endpoint URL.
        private_key: Private key for signing.
        network: Network type.
        database: Database instance.
        force_new: Force creation of new instance.

    Returns:
        BlockchainService instance.
    """
    global _blockchain_service

    if _blockchain_service is None or force_new:
        import os

        # Get network from environment
        if network is None:
            env_network = os.getenv("BLOCKCHAIN_NETWORK", "hardhat").lower()
            network = NetworkType(env_network)

        # Get private key from environment
        if private_key is None:
            private_key = os.getenv("PRIVATE_KEY")

        _blockchain_service = BlockchainService(
            rpc_url=rpc_url,
            private_key=private_key,
            network=network,
            database=database,
        )

        logger.info(f"Blockchain service initialized: {_blockchain_service.get_connection_info()}")

    return _blockchain_service
