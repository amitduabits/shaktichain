"""
Contract Manager Module.

Manages contract instances and ABIs for SHAKTI-CHAIN smart contracts.
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

from web3 import Web3
from web3.contract import Contract

from .provider import Web3Provider, get_web3_provider, NetworkType

logger = logging.getLogger(__name__)


@dataclass
class ContractInfo:
    """Contract deployment information."""
    name: str
    address: str
    abi: list


# Contract ABIs (minimal for interaction)
SHAKTI_TOKEN_ABI = [
    {"type": "function", "name": "name", "inputs": [], "outputs": [{"type": "string"}], "stateMutability": "view"},
    {"type": "function", "name": "symbol", "inputs": [], "outputs": [{"type": "string"}], "stateMutability": "view"},
    {"type": "function", "name": "decimals", "inputs": [], "outputs": [{"type": "uint8"}], "stateMutability": "view"},
    {"type": "function", "name": "totalSupply", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "balanceOf", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "transfer", "inputs": [{"name": "to", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable"},
    {"type": "function", "name": "allowance", "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "approve", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}], "stateMutability": "nonpayable"},
    {"type": "function", "name": "getVotes", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "delegate", "inputs": [{"name": "delegatee", "type": "address"}], "outputs": [], "stateMutability": "nonpayable"},
    {"type": "event", "name": "Transfer", "inputs": [{"name": "from", "type": "address", "indexed": True}, {"name": "to", "type": "address", "indexed": True}, {"name": "value", "type": "uint256", "indexed": False}]},
    {"type": "event", "name": "Approval", "inputs": [{"name": "owner", "type": "address", "indexed": True}, {"name": "spender", "type": "address", "indexed": True}, {"name": "value", "type": "uint256", "indexed": False}]},
]

ENERGY_AUCTION_ABI = [
    {"type": "function", "name": "getCurrentRound", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "getRoundInfo", "inputs": [{"name": "roundId", "type": "uint256"}], "outputs": [{"name": "startTime", "type": "uint256"}, {"name": "endTime", "type": "uint256"}, {"name": "clearingPrice", "type": "uint256"}, {"name": "totalBidVolume", "type": "uint256"}, {"name": "totalAskVolume", "type": "uint256"}, {"name": "state", "type": "uint8"}], "stateMutability": "view"},
    {"type": "function", "name": "roundDuration", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "minBidAmount", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "maxBidAmount", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "submitBid", "inputs": [{"name": "quantity", "type": "uint256"}, {"name": "maxPrice", "type": "uint256"}], "outputs": [{"name": "orderId", "type": "uint256"}], "stateMutability": "nonpayable"},
    {"type": "function", "name": "submitAsk", "inputs": [{"name": "quantity", "type": "uint256"}, {"name": "minPrice", "type": "uint256"}], "outputs": [{"name": "orderId", "type": "uint256"}], "stateMutability": "nonpayable"},
    {"type": "function", "name": "cancelOrder", "inputs": [{"name": "orderId", "type": "uint256"}], "outputs": [], "stateMutability": "nonpayable"},
    {"type": "function", "name": "getOrder", "inputs": [{"name": "orderId", "type": "uint256"}], "outputs": [{"name": "trader", "type": "address"}, {"name": "roundId", "type": "uint256"}, {"name": "orderType", "type": "uint8"}, {"name": "quantity", "type": "uint256"}, {"name": "price", "type": "uint256"}, {"name": "status", "type": "uint8"}, {"name": "matchedQuantity", "type": "uint256"}, {"name": "matchedPrice", "type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "getUserOrders", "inputs": [{"name": "user", "type": "address"}, {"name": "roundId", "type": "uint256"}], "outputs": [{"type": "uint256[]"}], "stateMutability": "view"},
    {"type": "event", "name": "RoundStarted", "inputs": [{"name": "roundId", "type": "uint256", "indexed": True}, {"name": "startTime", "type": "uint256", "indexed": False}, {"name": "endTime", "type": "uint256", "indexed": False}]},
    {"type": "event", "name": "BidSubmitted", "inputs": [{"name": "roundId", "type": "uint256", "indexed": True}, {"name": "orderId", "type": "uint256", "indexed": True}, {"name": "trader", "type": "address", "indexed": True}, {"name": "quantity", "type": "uint256", "indexed": False}, {"name": "maxPrice", "type": "uint256", "indexed": False}]},
    {"type": "event", "name": "AskSubmitted", "inputs": [{"name": "roundId", "type": "uint256", "indexed": True}, {"name": "orderId", "type": "uint256", "indexed": True}, {"name": "trader", "type": "address", "indexed": True}, {"name": "quantity", "type": "uint256", "indexed": False}, {"name": "minPrice", "type": "uint256", "indexed": False}]},
    {"type": "event", "name": "RoundCleared", "inputs": [{"name": "roundId", "type": "uint256", "indexed": True}, {"name": "clearingPrice", "type": "uint256", "indexed": False}, {"name": "clearedVolume", "type": "uint256", "indexed": False}, {"name": "matchedOrders", "type": "uint256", "indexed": False}]},
    {"type": "event", "name": "TradeExecuted", "inputs": [{"name": "roundId", "type": "uint256", "indexed": True}, {"name": "tradeId", "type": "uint256", "indexed": True}, {"name": "buyer", "type": "address", "indexed": False}, {"name": "seller", "type": "address", "indexed": False}, {"name": "quantity", "type": "uint256", "indexed": False}, {"name": "price", "type": "uint256", "indexed": False}]},
]

STAKING_POOL_ABI = [
    {"type": "function", "name": "totalStaked", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "rewardRate", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "minStakeAmount", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "lockPeriod", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "getStakeInfo", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"name": "amount", "type": "uint256"}, {"name": "shares", "type": "uint256"}, {"name": "stakedAt", "type": "uint256"}, {"name": "lockEndTime", "type": "uint256"}, {"name": "pendingRewards", "type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "earned", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "stake", "inputs": [{"name": "amount", "type": "uint256"}], "outputs": [], "stateMutability": "nonpayable"},
    {"type": "function", "name": "unstake", "inputs": [{"name": "amount", "type": "uint256"}], "outputs": [], "stateMutability": "nonpayable"},
    {"type": "function", "name": "claimRewards", "inputs": [], "outputs": [], "stateMutability": "nonpayable"},
    {"type": "function", "name": "getAPR", "inputs": [], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "event", "name": "Staked", "inputs": [{"name": "user", "type": "address", "indexed": True}, {"name": "amount", "type": "uint256", "indexed": False}, {"name": "shares", "type": "uint256", "indexed": False}]},
    {"type": "event", "name": "Unstaked", "inputs": [{"name": "user", "type": "address", "indexed": True}, {"name": "amount", "type": "uint256", "indexed": False}, {"name": "shares", "type": "uint256", "indexed": False}]},
    {"type": "event", "name": "RewardsClaimed", "inputs": [{"name": "user", "type": "address", "indexed": True}, {"name": "amount", "type": "uint256", "indexed": False}]},
]

REPUTATION_SYSTEM_ABI = [
    {"type": "function", "name": "getReputation", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}], "stateMutability": "view"},
    {"type": "function", "name": "getTier", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint8"}], "stateMutability": "view"},
    {"type": "function", "name": "getUserInfo", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"name": "reputation", "type": "uint256"}, {"name": "tier", "type": "uint8"}, {"name": "totalTrades", "type": "uint256"}, {"name": "successfulTrades", "type": "uint256"}, {"name": "failedDeliveries", "type": "uint256"}, {"name": "disputesWon", "type": "uint256"}, {"name": "disputesLost", "type": "uint256"}, {"name": "isKYCVerified", "type": "bool"}, {"name": "isFlagged", "type": "bool"}], "stateMutability": "view"},
    {"type": "function", "name": "isRegistered", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "bool"}], "stateMutability": "view"},
    {"type": "function", "name": "register", "inputs": [], "outputs": [], "stateMutability": "nonpayable"},
    {"type": "event", "name": "UserRegistered", "inputs": [{"name": "user", "type": "address", "indexed": True}, {"name": "timestamp", "type": "uint256", "indexed": False}]},
    {"type": "event", "name": "ReputationUpdated", "inputs": [{"name": "user", "type": "address", "indexed": True}, {"name": "oldScore", "type": "uint256", "indexed": False}, {"name": "newScore", "type": "uint256", "indexed": False}, {"name": "reason", "type": "string", "indexed": False}]},
    {"type": "event", "name": "TierChanged", "inputs": [{"name": "user", "type": "address", "indexed": True}, {"name": "oldTier", "type": "uint8", "indexed": False}, {"name": "newTier", "type": "uint8", "indexed": False}]},
]

# Default contract addresses per network
DEFAULT_ADDRESSES: Dict[NetworkType, Dict[str, str]] = {
    NetworkType.POLYGON: {
        "ShaktiToken": "0x0000000000000000000000000000000000000000",
        "EnergyAuction": "0x0000000000000000000000000000000000000000",
        "StakingPool": "0x0000000000000000000000000000000000000000",
        "ReputationSystem": "0x0000000000000000000000000000000000000000",
    },
    NetworkType.POLYGON_AMOY: {
        "ShaktiToken": "0x0000000000000000000000000000000000000000",
        "EnergyAuction": "0x0000000000000000000000000000000000000000",
        "StakingPool": "0x0000000000000000000000000000000000000000",
        "ReputationSystem": "0x0000000000000000000000000000000000000000",
    },
    NetworkType.HARDHAT: {
        "ShaktiToken": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
        "EnergyAuction": "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
        "StakingPool": "0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9",
        "ReputationSystem": "0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9",
    },
}


class ContractManager:
    """
    Manages contract instances for SHAKTI-CHAIN.

    Provides access to all deployed contracts and their methods.
    """

    def __init__(self, provider: Optional[Web3Provider] = None):
        """
        Initialize contract manager.

        Args:
            provider: Web3Provider instance. Uses singleton if None.
        """
        self.provider = provider or get_web3_provider()
        self._contracts: Dict[str, Contract] = {}
        self._addresses = self._load_addresses()

    def _load_addresses(self) -> Dict[str, str]:
        """Load contract addresses from environment or defaults."""
        # Try to load from environment variable (JSON string)
        env_addresses = os.getenv("CONTRACT_ADDRESSES")
        if env_addresses:
            try:
                return json.loads(env_addresses)
            except json.JSONDecodeError:
                logger.warning("Invalid CONTRACT_ADDRESSES JSON, using defaults")

        # Use defaults for the current network
        return DEFAULT_ADDRESSES.get(self.provider.network, {})

    def _get_contract(self, name: str, abi: list) -> Optional[Contract]:
        """
        Get or create a contract instance.

        Args:
            name: Contract name.
            abi: Contract ABI.

        Returns:
            Contract instance or None if not deployed.
        """
        if name in self._contracts:
            return self._contracts[name]

        address = self._addresses.get(name)
        if not address or address == "0x0000000000000000000000000000000000000000":
            logger.warning(f"Contract {name} not deployed on {self.provider.network.value}")
            return None

        try:
            checksum_address = Web3.to_checksum_address(address)
            contract = self.provider.web3.eth.contract(
                address=checksum_address,
                abi=abi,
            )
            self._contracts[name] = contract
            logger.info(f"Contract {name} loaded at {address}")
            return contract
        except Exception as e:
            logger.error(f"Failed to load contract {name}: {e}")
            return None

    @property
    def shakti_token(self) -> Optional[Contract]:
        """Get ShaktiToken contract instance."""
        return self._get_contract("ShaktiToken", SHAKTI_TOKEN_ABI)

    @property
    def energy_auction(self) -> Optional[Contract]:
        """Get EnergyAuction contract instance."""
        return self._get_contract("EnergyAuction", ENERGY_AUCTION_ABI)

    @property
    def staking_pool(self) -> Optional[Contract]:
        """Get StakingPool contract instance."""
        return self._get_contract("StakingPool", STAKING_POOL_ABI)

    @property
    def reputation_system(self) -> Optional[Contract]:
        """Get ReputationSystem contract instance."""
        return self._get_contract("ReputationSystem", REPUTATION_SYSTEM_ABI)

    def get_contract_address(self, name: str) -> Optional[str]:
        """
        Get contract address by name.

        Args:
            name: Contract name.

        Returns:
            Contract address or None.
        """
        return self._addresses.get(name)

    def is_deployed(self, name: str) -> bool:
        """
        Check if a contract is deployed.

        Args:
            name: Contract name.

        Returns:
            True if deployed, False otherwise.
        """
        address = self._addresses.get(name)
        return address is not None and address != "0x0000000000000000000000000000000000000000"

    def get_all_addresses(self) -> Dict[str, str]:
        """Get all contract addresses."""
        return self._addresses.copy()


# Singleton instance
_contract_manager: Optional[ContractManager] = None


def get_contract_manager(provider: Optional[Web3Provider] = None) -> ContractManager:
    """
    Get or create the contract manager singleton.

    Args:
        provider: Web3Provider instance.

    Returns:
        ContractManager instance.
    """
    global _contract_manager

    if _contract_manager is None:
        _contract_manager = ContractManager(provider)

    return _contract_manager
