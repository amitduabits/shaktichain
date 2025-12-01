"""
Transaction Manager Module.

Handles transaction building, signing, and submission for SHAKTI-CHAIN.
"""

import time
import logging
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from web3 import Web3
from web3.contract import Contract
from web3.exceptions import TransactionNotFound

from .provider import Web3Provider, get_web3_provider

logger = logging.getLogger(__name__)


class TransactionStatus(str, Enum):
    """Transaction status states."""
    PENDING = "pending"
    CONFIRMING = "confirming"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class TransactionResult:
    """Result of a transaction submission."""
    tx_hash: str
    status: TransactionStatus
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    error: Optional[str] = None
    receipt: Optional[Dict[str, Any]] = None
    explorer_url: Optional[str] = None


@dataclass
class PendingTransaction:
    """Tracks a pending transaction."""
    tx_hash: str
    description: str
    submitted_at: float
    nonce: int
    gas_price: int
    callback: Optional[Callable[[TransactionResult], None]] = None


class TransactionManager:
    """
    Manages transaction lifecycle for blockchain interactions.

    Handles:
    - Transaction building and gas estimation
    - Nonce management
    - Transaction signing and submission
    - Receipt waiting and confirmation tracking
    """

    def __init__(self, provider: Optional[Web3Provider] = None):
        """
        Initialize transaction manager.

        Args:
            provider: Web3Provider instance.
        """
        self.provider = provider or get_web3_provider()
        self._pending: Dict[str, PendingTransaction] = {}
        self._nonce_lock = False
        self._last_nonce: Optional[int] = None

    @property
    def web3(self) -> Web3:
        """Get Web3 instance."""
        return self.provider.web3

    def _get_nonce(self, address: str) -> int:
        """
        Get the next nonce for an address.

        Manages nonce to prevent conflicts with pending transactions.

        Args:
            address: Sender address.

        Returns:
            Next nonce to use.
        """
        pending_nonce = self.web3.eth.get_transaction_count(address, "pending")

        # Use the higher of pending nonce or tracked nonce
        if self._last_nonce is not None and self._last_nonce >= pending_nonce:
            nonce = self._last_nonce + 1
        else:
            nonce = pending_nonce

        self._last_nonce = nonce
        return nonce

    def build_transaction(
        self,
        contract: Contract,
        function_name: str,
        *args,
        value: int = 0,
        gas_limit: Optional[int] = None,
        gas_price: Optional[int] = None,
        max_fee_per_gas: Optional[int] = None,
        max_priority_fee_per_gas: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Build a transaction for a contract function call.

        Args:
            contract: Contract instance.
            function_name: Name of the function to call.
            *args: Function arguments.
            value: ETH/MATIC value to send (in wei).
            gas_limit: Gas limit override.
            gas_price: Gas price override (legacy).
            max_fee_per_gas: Max fee per gas (EIP-1559).
            max_priority_fee_per_gas: Max priority fee (EIP-1559).

        Returns:
            Transaction dictionary ready for signing.
        """
        if not self.provider.account:
            raise ValueError("No account configured for signing transactions")

        sender = self.provider.address
        nonce = self._get_nonce(sender)

        # Get contract function
        func = getattr(contract.functions, function_name)
        contract_func = func(*args)

        # Build base transaction
        tx = {
            "from": sender,
            "nonce": nonce,
            "chainId": self.provider.chain_id,
            "value": value,
        }

        # Estimate gas if not provided
        if gas_limit is None:
            try:
                gas_limit = contract_func.estimate_gas({"from": sender, "value": value})
                # Add 20% buffer
                gas_limit = int(gas_limit * 1.2)
            except Exception as e:
                logger.warning(f"Gas estimation failed: {e}, using default")
                gas_limit = 500000

        tx["gas"] = gas_limit

        # Set gas price (EIP-1559 or legacy)
        if max_fee_per_gas is not None:
            tx["maxFeePerGas"] = max_fee_per_gas
            tx["maxPriorityFeePerGas"] = max_priority_fee_per_gas or self.web3.eth.max_priority_fee
        else:
            tx["gasPrice"] = gas_price or self.web3.eth.gas_price

        # Build full transaction
        return contract_func.build_transaction(tx)

    def sign_and_send(
        self,
        transaction: Dict[str, Any],
        description: str = "Transaction",
        wait: bool = True,
        timeout: int = 120,
        callback: Optional[Callable[[TransactionResult], None]] = None,
    ) -> TransactionResult:
        """
        Sign and send a transaction.

        Args:
            transaction: Transaction dictionary.
            description: Human-readable description.
            wait: Whether to wait for confirmation.
            timeout: Timeout in seconds for waiting.
            callback: Callback function on completion.

        Returns:
            TransactionResult with status and receipt.
        """
        if not self.provider.account:
            raise ValueError("No account configured for signing transactions")

        try:
            # Sign transaction
            signed = self.provider.account.sign_transaction(transaction)
            tx_hash = signed.hash.hex()

            logger.info(f"Sending transaction: {description} (hash: {tx_hash})")

            # Send transaction
            self.web3.eth.send_raw_transaction(signed.raw_transaction)

            # Track pending transaction
            pending = PendingTransaction(
                tx_hash=tx_hash,
                description=description,
                submitted_at=time.time(),
                nonce=transaction["nonce"],
                gas_price=transaction.get("gasPrice", 0),
                callback=callback,
            )
            self._pending[tx_hash] = pending

            result = TransactionResult(
                tx_hash=tx_hash,
                status=TransactionStatus.PENDING,
                explorer_url=self.provider.get_explorer_url(tx_hash),
            )

            # Wait for confirmation if requested
            if wait:
                return self.wait_for_confirmation(tx_hash, timeout)

            return result

        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            return TransactionResult(
                tx_hash="",
                status=TransactionStatus.FAILED,
                error=str(e),
            )

    def wait_for_confirmation(
        self,
        tx_hash: str,
        timeout: int = 120,
    ) -> TransactionResult:
        """
        Wait for a transaction to be confirmed.

        Args:
            tx_hash: Transaction hash.
            timeout: Timeout in seconds.

        Returns:
            TransactionResult with final status.
        """
        try:
            receipt = self.web3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)

            status = TransactionStatus.CONFIRMED if receipt["status"] == 1 else TransactionStatus.FAILED
            error = None if status == TransactionStatus.CONFIRMED else "Transaction reverted"

            result = TransactionResult(
                tx_hash=tx_hash,
                status=status,
                block_number=receipt["blockNumber"],
                gas_used=receipt["gasUsed"],
                error=error,
                receipt=dict(receipt),
                explorer_url=self.provider.get_explorer_url(tx_hash),
            )

            # Execute callback if registered
            pending = self._pending.pop(tx_hash, None)
            if pending and pending.callback:
                pending.callback(result)

            logger.info(f"Transaction {status.value}: {tx_hash} (block: {receipt['blockNumber']})")
            return result

        except Exception as e:
            logger.error(f"Error waiting for transaction: {e}")
            return TransactionResult(
                tx_hash=tx_hash,
                status=TransactionStatus.FAILED,
                error=str(e),
            )

    def get_transaction_status(self, tx_hash: str) -> TransactionResult:
        """
        Get the status of a transaction.

        Args:
            tx_hash: Transaction hash.

        Returns:
            TransactionResult with current status.
        """
        try:
            receipt = self.web3.eth.get_transaction_receipt(tx_hash)

            if receipt is None:
                return TransactionResult(
                    tx_hash=tx_hash,
                    status=TransactionStatus.PENDING,
                    explorer_url=self.provider.get_explorer_url(tx_hash),
                )

            status = TransactionStatus.CONFIRMED if receipt["status"] == 1 else TransactionStatus.FAILED

            return TransactionResult(
                tx_hash=tx_hash,
                status=status,
                block_number=receipt["blockNumber"],
                gas_used=receipt["gasUsed"],
                receipt=dict(receipt),
                explorer_url=self.provider.get_explorer_url(tx_hash),
            )

        except TransactionNotFound:
            return TransactionResult(
                tx_hash=tx_hash,
                status=TransactionStatus.PENDING,
                explorer_url=self.provider.get_explorer_url(tx_hash),
            )
        except Exception as e:
            return TransactionResult(
                tx_hash=tx_hash,
                status=TransactionStatus.FAILED,
                error=str(e),
            )

    def get_pending_transactions(self) -> Dict[str, PendingTransaction]:
        """Get all pending transactions."""
        return self._pending.copy()

    def clear_stale_pending(self, max_age: int = 3600) -> int:
        """
        Clear stale pending transactions.

        Args:
            max_age: Maximum age in seconds.

        Returns:
            Number of transactions cleared.
        """
        current_time = time.time()
        stale = [
            tx_hash for tx_hash, pending in self._pending.items()
            if current_time - pending.submitted_at > max_age
        ]

        for tx_hash in stale:
            del self._pending[tx_hash]

        if stale:
            logger.info(f"Cleared {len(stale)} stale pending transactions")

        return len(stale)

    def execute_contract_call(
        self,
        contract: Contract,
        function_name: str,
        *args,
        value: int = 0,
        description: Optional[str] = None,
        wait: bool = True,
        **kwargs,
    ) -> TransactionResult:
        """
        Execute a contract function call.

        Convenience method that builds, signs, and sends a transaction.

        Args:
            contract: Contract instance.
            function_name: Function name.
            *args: Function arguments.
            value: ETH/MATIC value in wei.
            description: Transaction description.
            wait: Wait for confirmation.
            **kwargs: Additional transaction parameters.

        Returns:
            TransactionResult.
        """
        desc = description or f"{contract.address[:10]}...{function_name}()"

        tx = self.build_transaction(
            contract,
            function_name,
            *args,
            value=value,
            **kwargs,
        )

        return self.sign_and_send(tx, description=desc, wait=wait)

    def estimate_transaction_cost(
        self,
        contract: Contract,
        function_name: str,
        *args,
        value: int = 0,
    ) -> Dict[str, Any]:
        """
        Estimate the cost of a transaction.

        Args:
            contract: Contract instance.
            function_name: Function name.
            *args: Function arguments.
            value: ETH/MATIC value in wei.

        Returns:
            Dictionary with gas and cost estimates.
        """
        if not self.provider.address:
            raise ValueError("No account configured")

        func = getattr(contract.functions, function_name)
        contract_func = func(*args)

        try:
            gas_estimate = contract_func.estimate_gas({
                "from": self.provider.address,
                "value": value,
            })
        except Exception as e:
            logger.warning(f"Gas estimation failed: {e}")
            gas_estimate = 500000

        gas_price = self.web3.eth.gas_price
        cost_wei = gas_estimate * gas_price
        cost_ether = float(Web3.from_wei(cost_wei, "ether"))

        return {
            "gas_estimate": gas_estimate,
            "gas_price_wei": gas_price,
            "gas_price_gwei": float(Web3.from_wei(gas_price, "gwei")),
            "total_cost_wei": cost_wei,
            "total_cost_ether": cost_ether,
        }
