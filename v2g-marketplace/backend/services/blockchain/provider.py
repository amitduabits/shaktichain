"""
Web3 Provider Module.

Manages Web3 connections to Polygon/Ethereum networks.
Supports multiple networks: Polygon Mainnet, Amoy Testnet, and local Hardhat.
"""

import os
import logging
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from eth_account import Account
from eth_account.signers.local import LocalAccount

logger = logging.getLogger(__name__)


class NetworkType(str, Enum):
    """Supported network types."""
    POLYGON = "polygon"
    POLYGON_AMOY = "polygon_amoy"
    HARDHAT = "hardhat"


@dataclass
class NetworkConfig:
    """Network configuration."""
    chain_id: int
    rpc_url: str
    name: str
    explorer_url: Optional[str] = None
    is_testnet: bool = False


# Default network configurations
NETWORK_CONFIGS = {
    NetworkType.POLYGON: NetworkConfig(
        chain_id=137,
        rpc_url="https://polygon-rpc.com",
        name="Polygon Mainnet",
        explorer_url="https://polygonscan.com",
        is_testnet=False,
    ),
    NetworkType.POLYGON_AMOY: NetworkConfig(
        chain_id=80002,
        rpc_url="https://rpc-amoy.polygon.technology",
        name="Polygon Amoy Testnet",
        explorer_url="https://amoy.polygonscan.com",
        is_testnet=True,
    ),
    NetworkType.HARDHAT: NetworkConfig(
        chain_id=31337,
        rpc_url="http://127.0.0.1:8545",
        name="Hardhat Local",
        explorer_url=None,
        is_testnet=True,
    ),
}


class Web3Provider:
    """
    Web3 connection provider.

    Manages Web3 instances and wallet accounts for blockchain interactions.
    """

    def __init__(
        self,
        rpc_url: Optional[str] = None,
        private_key: Optional[str] = None,
        network: NetworkType = NetworkType.HARDHAT,
    ):
        """
        Initialize Web3 provider.

        Args:
            rpc_url: RPC endpoint URL. If None, uses default for network.
            private_key: Private key for signing transactions. If None, read-only mode.
            network: Network type to connect to.
        """
        self.network = network
        self.config = NETWORK_CONFIGS[network]

        # Use provided RPC URL or default
        self.rpc_url = rpc_url or self._get_rpc_from_env() or self.config.rpc_url

        # Initialize Web3
        self._web3: Optional[Web3] = None
        self._account: Optional[LocalAccount] = None

        # Set up account if private key provided
        if private_key:
            self._setup_account(private_key)

    def _get_rpc_from_env(self) -> Optional[str]:
        """Get RPC URL from environment variables."""
        env_mapping = {
            NetworkType.POLYGON: "POLYGON_RPC_URL",
            NetworkType.POLYGON_AMOY: "POLYGON_AMOY_RPC_URL",
            NetworkType.HARDHAT: "HARDHAT_RPC_URL",
        }
        env_key = env_mapping.get(self.network)
        return os.getenv(env_key) if env_key else None

    def _setup_account(self, private_key: str) -> None:
        """Set up signing account from private key."""
        # Handle keys with or without 0x prefix
        if not private_key.startswith("0x"):
            private_key = f"0x{private_key}"

        try:
            self._account = Account.from_key(private_key)
            logger.info(f"Account initialized: {self._account.address}")
        except Exception as e:
            logger.error(f"Failed to initialize account: {e}")
            raise ValueError(f"Invalid private key: {e}")

    @property
    def web3(self) -> Web3:
        """Get or create Web3 instance."""
        if self._web3 is None:
            self._web3 = self._create_web3()
        return self._web3

    def _create_web3(self) -> Web3:
        """Create and configure Web3 instance."""
        # Create provider based on URL scheme
        if self.rpc_url.startswith("ws"):
            provider = Web3.WebsocketProvider(self.rpc_url)
        else:
            provider = Web3.HTTPProvider(self.rpc_url)

        w3 = Web3(provider)

        # Add POA middleware for Polygon networks
        if self.network in [NetworkType.POLYGON, NetworkType.POLYGON_AMOY]:
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        return w3

    @property
    def account(self) -> Optional[LocalAccount]:
        """Get the signing account."""
        return self._account

    @property
    def address(self) -> Optional[str]:
        """Get the account address."""
        return self._account.address if self._account else None

    @property
    def chain_id(self) -> int:
        """Get the chain ID."""
        return self.config.chain_id

    @property
    def is_connected(self) -> bool:
        """Check if connected to the network."""
        try:
            return self.web3.is_connected()
        except Exception:
            return False

    def get_balance(self, address: Optional[str] = None) -> int:
        """
        Get native token balance (MATIC/ETH).

        Args:
            address: Address to check. Uses account address if None.

        Returns:
            Balance in wei.
        """
        target = address or self.address
        if not target:
            raise ValueError("No address specified and no account configured")

        return self.web3.eth.get_balance(Web3.to_checksum_address(target))

    def get_balance_ether(self, address: Optional[str] = None) -> float:
        """
        Get native token balance in ether units.

        Args:
            address: Address to check. Uses account address if None.

        Returns:
            Balance in ether.
        """
        wei_balance = self.get_balance(address)
        return float(Web3.from_wei(wei_balance, "ether"))

    def get_block_number(self) -> int:
        """Get the current block number."""
        return self.web3.eth.block_number

    def get_gas_price(self) -> int:
        """Get current gas price in wei."""
        return self.web3.eth.gas_price

    def get_gas_price_gwei(self) -> float:
        """Get current gas price in gwei."""
        return float(Web3.from_wei(self.web3.eth.gas_price, "gwei"))

    def estimate_gas(self, transaction: dict) -> int:
        """
        Estimate gas for a transaction.

        Args:
            transaction: Transaction dictionary.

        Returns:
            Estimated gas units.
        """
        return self.web3.eth.estimate_gas(transaction)

    def get_transaction_receipt(self, tx_hash: str) -> Optional[dict]:
        """
        Get transaction receipt.

        Args:
            tx_hash: Transaction hash.

        Returns:
            Transaction receipt or None if pending.
        """
        try:
            return dict(self.web3.eth.get_transaction_receipt(tx_hash))
        except Exception:
            return None

    def wait_for_transaction(self, tx_hash: str, timeout: int = 120) -> dict:
        """
        Wait for transaction to be mined.

        Args:
            tx_hash: Transaction hash.
            timeout: Timeout in seconds.

        Returns:
            Transaction receipt.
        """
        return dict(self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout))

    def get_explorer_url(self, tx_hash: str) -> Optional[str]:
        """
        Get block explorer URL for a transaction.

        Args:
            tx_hash: Transaction hash.

        Returns:
            Explorer URL or None if not available.
        """
        if self.config.explorer_url:
            return f"{self.config.explorer_url}/tx/{tx_hash}"
        return None

    def sign_message(self, message: str) -> Optional[str]:
        """
        Sign a message with the account.

        Args:
            message: Message to sign.

        Returns:
            Signature hex string or None if no account.
        """
        if not self._account:
            return None

        from eth_account.messages import encode_defunct
        message_hash = encode_defunct(text=message)
        signed = self._account.sign_message(message_hash)
        return signed.signature.hex()

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        account_str = f", account={self.address}" if self.address else ""
        return f"Web3Provider(network={self.network.value}, status={status}{account_str})"


# Singleton instance
_provider_instance: Optional[Web3Provider] = None


def get_web3_provider(
    rpc_url: Optional[str] = None,
    private_key: Optional[str] = None,
    network: Optional[NetworkType] = None,
    force_new: bool = False,
) -> Web3Provider:
    """
    Get or create the Web3 provider singleton.

    Args:
        rpc_url: RPC endpoint URL.
        private_key: Private key for signing.
        network: Network type.
        force_new: Force creation of new instance.

    Returns:
        Web3Provider instance.
    """
    global _provider_instance

    if _provider_instance is None or force_new:
        # Determine network from environment if not specified
        if network is None:
            env_network = os.getenv("BLOCKCHAIN_NETWORK", "hardhat").lower()
            network = NetworkType(env_network)

        # Get private key from environment if not specified
        if private_key is None:
            private_key = os.getenv("PRIVATE_KEY")

        _provider_instance = Web3Provider(
            rpc_url=rpc_url,
            private_key=private_key,
            network=network,
        )

        logger.info(f"Web3 provider initialized: {_provider_instance}")

    return _provider_instance
