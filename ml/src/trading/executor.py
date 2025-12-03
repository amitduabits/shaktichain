"""BlockchainTradingExecutor for executing trades on SHAKTI-CHAIN smart contracts.

Provides:
- Trade execution via Web3
- Bid/ask submission to auction contracts
- Token approval management
- Transaction confirmation handling
- Dry-run mode for testing
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal

logger = logging.getLogger(__name__)

# Optional Web3 import
try:
    from web3 import Web3
    from web3.middleware import geth_poa_middleware
    from eth_account import Account
    HAS_WEB3 = True
except ImportError:
    HAS_WEB3 = False
    logger.warning("web3 not installed. Install with: pip install web3")


class ActionType(Enum):
    """Types of trading actions."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CANCEL = "cancel"


class TransactionStatus(Enum):
    """Status of a transaction."""
    PENDING = "pending"
    SUBMITTED = "submitted"
    CONFIRMING = "confirming"
    SUCCESS = "success"
    FAILED = "failed"
    REVERTED = "reverted"
    TIMEOUT = "timeout"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    INSUFFICIENT_ALLOWANCE = "insufficient_allowance"
    RISK_REJECTED = "risk_rejected"
    DRY_RUN = "dry_run"


@dataclass
class TradingAction:
    """A trading action to execute."""
    action_type: ActionType
    quantity: float  # Energy in kWh
    price: float  # Price per kWh in tokens
    auction_id: Optional[str] = None
    order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_value(self) -> float:
        """Calculate total trade value."""
        return self.quantity * self.price

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_type": self.action_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "total_value": self.total_value,
            "auction_id": self.auction_id,
            "order_id": self.order_id,
            "metadata": self.metadata,
        }


@dataclass
class TransactionResult:
    """Result of a transaction execution."""
    status: TransactionStatus
    tx_hash: Optional[str] = None
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    gas_price: Optional[int] = None
    effective_price: Optional[float] = None
    filled_quantity: Optional[float] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    execution_time_ms: float = 0.0

    @property
    def gas_cost_wei(self) -> Optional[int]:
        """Calculate gas cost in wei."""
        if self.gas_used and self.gas_price:
            return self.gas_used * self.gas_price
        return None

    @property
    def is_success(self) -> bool:
        """Check if transaction was successful."""
        return self.status == TransactionStatus.SUCCESS

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "tx_hash": self.tx_hash,
            "block_number": self.block_number,
            "gas_used": self.gas_used,
            "gas_price": self.gas_price,
            "gas_cost_wei": self.gas_cost_wei,
            "effective_price": self.effective_price,
            "filled_quantity": self.filled_quantity,
            "error_message": self.error_message,
            "timestamp": self.timestamp.isoformat(),
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class ExecutorConfig:
    """Configuration for trading executor."""
    # Network
    rpc_url: str = "http://localhost:8545"
    chain_id: int = 1337

    # Contracts
    auction_contract_address: Optional[str] = None
    token_contract_address: Optional[str] = None
    market_contract_address: Optional[str] = None

    # Gas
    gas_limit: int = 300000
    max_gas_price_gwei: float = 100.0
    gas_price_multiplier: float = 1.1

    # Execution
    confirmation_blocks: int = 1
    confirmation_timeout: float = 120.0
    dry_run: bool = False

    # Safety
    max_slippage_pct: float = 1.0
    require_price_check: bool = True


# Contract ABIs (simplified)
AUCTION_ABI = [
    {
        "inputs": [
            {"name": "quantity", "type": "uint256"},
            {"name": "pricePerUnit", "type": "uint256"}
        ],
        "name": "submitBid",
        "outputs": [{"name": "orderId", "type": "bytes32"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "quantity", "type": "uint256"},
            {"name": "pricePerUnit", "type": "uint256"}
        ],
        "name": "submitAsk",
        "outputs": [{"name": "orderId", "type": "bytes32"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "orderId", "type": "bytes32"}],
        "name": "cancelOrder",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getCurrentPrice",
        "outputs": [{"name": "price", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getAuctionState",
        "outputs": [
            {"name": "isOpen", "type": "bool"},
            {"name": "endTime", "type": "uint256"},
            {"name": "totalBids", "type": "uint256"},
            {"name": "totalAsks", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
]

TOKEN_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "decimals", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
]


class BlockchainTradingExecutor:
    """Execute trades on SHAKTI-CHAIN smart contracts."""

    def __init__(
        self,
        config: Optional[ExecutorConfig] = None,
        private_key: Optional[str] = None,
        risk_manager=None,
        transaction_monitor=None,
    ):
        """Initialize trading executor.

        Args:
            config: Executor configuration
            private_key: Private key for signing transactions
            risk_manager: Risk manager for safety checks
            transaction_monitor: Transaction monitor for tracking
        """
        self.config = config or ExecutorConfig()
        self.risk_manager = risk_manager
        self.transaction_monitor = transaction_monitor

        # Web3 setup
        self._w3 = None
        self._account = None
        self._auction_contract = None
        self._token_contract = None
        self._token_decimals = 18

        if HAS_WEB3 and private_key and not self.config.dry_run:
            self._setup_web3(private_key)

        # Statistics
        self._stats = {
            "transactions_submitted": 0,
            "transactions_success": 0,
            "transactions_failed": 0,
            "total_gas_used": 0,
            "total_value_traded": 0.0,
        }

    def _setup_web3(self, private_key: str):
        """Setup Web3 connection and contracts."""
        try:
            self._w3 = Web3(Web3.HTTPProvider(self.config.rpc_url))

            # Add PoA middleware if needed
            self._w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            # Setup account
            self._account = Account.from_key(private_key)
            logger.info(f"Trading account: {self._account.address}")

            # Setup contracts
            if self.config.auction_contract_address:
                self._auction_contract = self._w3.eth.contract(
                    address=Web3.to_checksum_address(self.config.auction_contract_address),
                    abi=AUCTION_ABI,
                )

            if self.config.token_contract_address:
                self._token_contract = self._w3.eth.contract(
                    address=Web3.to_checksum_address(self.config.token_contract_address),
                    abi=TOKEN_ABI,
                )
                # Get token decimals
                try:
                    self._token_decimals = self._token_contract.functions.decimals().call()
                except Exception:
                    self._token_decimals = 18

            logger.info("Web3 setup complete")

        except Exception as e:
            logger.error(f"Web3 setup failed: {e}")
            self._w3 = None

    async def execute_action(self, action: TradingAction) -> TransactionResult:
        """Execute a trading action.

        Args:
            action: Trading action to execute

        Returns:
            Transaction result
        """
        start_time = time.perf_counter()

        # Risk check
        if self.risk_manager:
            risk_check = await self.risk_manager.check_action(action)
            if not risk_check.approved:
                return TransactionResult(
                    status=TransactionStatus.RISK_REJECTED,
                    error_message=risk_check.reason,
                    execution_time_ms=(time.perf_counter() - start_time) * 1000,
                )

        # Dry run mode
        if self.config.dry_run:
            result = await self._execute_dry_run(action)
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000
            return result

        # Execute based on action type
        try:
            if action.action_type == ActionType.BUY:
                result = await self._submit_bid(action)
            elif action.action_type == ActionType.SELL:
                result = await self._submit_ask(action)
            elif action.action_type == ActionType.CANCEL:
                result = await self._cancel_order(action)
            else:
                result = TransactionResult(
                    status=TransactionStatus.SUCCESS,
                    filled_quantity=0,
                )

            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

            # Track transaction
            if self.transaction_monitor:
                await self.transaction_monitor.record(action, result)

            # Update stats
            self._update_stats(result, action)

            return result

        except Exception as e:
            logger.error(f"Execution error: {e}")
            return TransactionResult(
                status=TransactionStatus.FAILED,
                error_message=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

    async def _execute_dry_run(self, action: TradingAction) -> TransactionResult:
        """Execute action in dry-run mode (simulation only)."""
        logger.info(f"[DRY RUN] Would execute {action.action_type.value}: "
                   f"{action.quantity} @ {action.price}")

        # Simulate some processing time
        await asyncio.sleep(0.1)

        return TransactionResult(
            status=TransactionStatus.DRY_RUN,
            filled_quantity=action.quantity,
            effective_price=action.price,
            gas_used=150000,
            gas_price=self._get_gas_price() if self._w3 else 20_000_000_000,
        )

    async def _submit_bid(self, action: TradingAction) -> TransactionResult:
        """Submit a buy bid to the auction contract.

        Args:
            action: Buy action

        Returns:
            Transaction result
        """
        if not self._w3 or not self._auction_contract:
            return TransactionResult(
                status=TransactionStatus.FAILED,
                error_message="Web3 or auction contract not initialized",
            )

        # Calculate required amount
        quantity_wei = self._to_token_units(action.quantity)
        price_wei = self._to_token_units(action.price)
        required_amount = quantity_wei * price_wei // (10 ** self._token_decimals)

        # Check balance
        balance = await self._get_token_balance()
        if balance < required_amount:
            return TransactionResult(
                status=TransactionStatus.INSUFFICIENT_BALANCE,
                error_message=f"Balance {balance} < required {required_amount}",
            )

        # Ensure approval
        approval_result = await self._ensure_approval(required_amount)
        if not approval_result.is_success and approval_result.status != TransactionStatus.SUCCESS:
            return approval_result

        # Price check with slippage
        if self.config.require_price_check:
            current_price = await self._get_current_price()
            if current_price:
                max_price = current_price * (1 + self.config.max_slippage_pct / 100)
                if action.price > max_price:
                    return TransactionResult(
                        status=TransactionStatus.FAILED,
                        error_message=f"Price {action.price} exceeds max {max_price:.4f} (slippage protection)",
                    )

        # Build transaction
        try:
            tx = self._auction_contract.functions.submitBid(
                quantity_wei,
                price_wei,
            ).build_transaction({
                "from": self._account.address,
                "gas": self.config.gas_limit,
                "gasPrice": self._get_gas_price(),
                "nonce": self._w3.eth.get_transaction_count(self._account.address),
                "chainId": self.config.chain_id,
            })

            # Sign and send
            return await self._send_transaction(tx, action)

        except Exception as e:
            logger.error(f"Bid submission error: {e}")
            return TransactionResult(
                status=TransactionStatus.FAILED,
                error_message=str(e),
            )

    async def _submit_ask(self, action: TradingAction) -> TransactionResult:
        """Submit a sell ask to the auction contract.

        Args:
            action: Sell action

        Returns:
            Transaction result
        """
        if not self._w3 or not self._auction_contract:
            return TransactionResult(
                status=TransactionStatus.FAILED,
                error_message="Web3 or auction contract not initialized",
            )

        quantity_wei = self._to_token_units(action.quantity)
        price_wei = self._to_token_units(action.price)

        # Price check with slippage
        if self.config.require_price_check:
            current_price = await self._get_current_price()
            if current_price:
                min_price = current_price * (1 - self.config.max_slippage_pct / 100)
                if action.price < min_price:
                    return TransactionResult(
                        status=TransactionStatus.FAILED,
                        error_message=f"Price {action.price} below min {min_price:.4f} (slippage protection)",
                    )

        # Build transaction
        try:
            tx = self._auction_contract.functions.submitAsk(
                quantity_wei,
                price_wei,
            ).build_transaction({
                "from": self._account.address,
                "gas": self.config.gas_limit,
                "gasPrice": self._get_gas_price(),
                "nonce": self._w3.eth.get_transaction_count(self._account.address),
                "chainId": self.config.chain_id,
            })

            return await self._send_transaction(tx, action)

        except Exception as e:
            logger.error(f"Ask submission error: {e}")
            return TransactionResult(
                status=TransactionStatus.FAILED,
                error_message=str(e),
            )

    async def _cancel_order(self, action: TradingAction) -> TransactionResult:
        """Cancel an existing order.

        Args:
            action: Cancel action with order_id

        Returns:
            Transaction result
        """
        if not action.order_id:
            return TransactionResult(
                status=TransactionStatus.FAILED,
                error_message="No order_id provided for cancel",
            )

        if not self._w3 or not self._auction_contract:
            return TransactionResult(
                status=TransactionStatus.FAILED,
                error_message="Web3 or auction contract not initialized",
            )

        try:
            order_id_bytes = bytes.fromhex(action.order_id.replace("0x", ""))

            tx = self._auction_contract.functions.cancelOrder(
                order_id_bytes,
            ).build_transaction({
                "from": self._account.address,
                "gas": self.config.gas_limit // 2,
                "gasPrice": self._get_gas_price(),
                "nonce": self._w3.eth.get_transaction_count(self._account.address),
                "chainId": self.config.chain_id,
            })

            return await self._send_transaction(tx, action)

        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            return TransactionResult(
                status=TransactionStatus.FAILED,
                error_message=str(e),
            )

    async def _send_transaction(
        self,
        tx: Dict[str, Any],
        action: TradingAction,
    ) -> TransactionResult:
        """Sign, send, and wait for transaction confirmation.

        Args:
            tx: Transaction dictionary
            action: Original action

        Returns:
            Transaction result
        """
        self._stats["transactions_submitted"] += 1

        try:
            # Sign transaction
            signed_tx = self._account.sign_transaction(tx)

            # Send transaction
            tx_hash = self._w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            tx_hash_hex = tx_hash.hex()

            logger.info(f"Transaction submitted: {tx_hash_hex}")

            # Wait for confirmation
            try:
                receipt = self._w3.eth.wait_for_transaction_receipt(
                    tx_hash,
                    timeout=self.config.confirmation_timeout,
                )

                # Wait for additional confirmations
                if self.config.confirmation_blocks > 1:
                    target_block = receipt.blockNumber + self.config.confirmation_blocks - 1
                    while self._w3.eth.block_number < target_block:
                        await asyncio.sleep(1)

                if receipt.status == 1:
                    self._stats["transactions_success"] += 1
                    self._stats["total_gas_used"] += receipt.gasUsed

                    return TransactionResult(
                        status=TransactionStatus.SUCCESS,
                        tx_hash=tx_hash_hex,
                        block_number=receipt.blockNumber,
                        gas_used=receipt.gasUsed,
                        gas_price=tx.get("gasPrice"),
                        filled_quantity=action.quantity,
                        effective_price=action.price,
                    )
                else:
                    self._stats["transactions_failed"] += 1
                    return TransactionResult(
                        status=TransactionStatus.REVERTED,
                        tx_hash=tx_hash_hex,
                        block_number=receipt.blockNumber,
                        gas_used=receipt.gasUsed,
                        error_message="Transaction reverted",
                    )

            except Exception as e:
                if "timeout" in str(e).lower():
                    return TransactionResult(
                        status=TransactionStatus.TIMEOUT,
                        tx_hash=tx_hash_hex,
                        error_message=f"Confirmation timeout after {self.config.confirmation_timeout}s",
                    )
                raise

        except Exception as e:
            self._stats["transactions_failed"] += 1
            logger.error(f"Transaction error: {e}")
            return TransactionResult(
                status=TransactionStatus.FAILED,
                error_message=str(e),
            )

    async def _ensure_approval(self, amount: int) -> TransactionResult:
        """Ensure token approval for auction contract.

        Args:
            amount: Amount to approve

        Returns:
            Transaction result
        """
        if not self._token_contract or not self._auction_contract:
            return TransactionResult(status=TransactionStatus.SUCCESS)

        try:
            # Check current allowance
            allowance = self._token_contract.functions.allowance(
                self._account.address,
                self._auction_contract.address,
            ).call()

            if allowance >= amount:
                return TransactionResult(status=TransactionStatus.SUCCESS)

            # Approve max amount
            approval_amount = 2 ** 256 - 1  # Max uint256

            tx = self._token_contract.functions.approve(
                self._auction_contract.address,
                approval_amount,
            ).build_transaction({
                "from": self._account.address,
                "gas": 100000,
                "gasPrice": self._get_gas_price(),
                "nonce": self._w3.eth.get_transaction_count(self._account.address),
                "chainId": self.config.chain_id,
            })

            signed_tx = self._account.sign_transaction(tx)
            tx_hash = self._w3.eth.send_raw_transaction(signed_tx.rawTransaction)

            receipt = self._w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)

            if receipt.status == 1:
                logger.info("Token approval successful")
                return TransactionResult(
                    status=TransactionStatus.SUCCESS,
                    tx_hash=tx_hash.hex(),
                    gas_used=receipt.gasUsed,
                )
            else:
                return TransactionResult(
                    status=TransactionStatus.FAILED,
                    tx_hash=tx_hash.hex(),
                    error_message="Approval transaction reverted",
                )

        except Exception as e:
            logger.error(f"Approval error: {e}")
            return TransactionResult(
                status=TransactionStatus.INSUFFICIENT_ALLOWANCE,
                error_message=str(e),
            )

    async def _get_token_balance(self) -> int:
        """Get token balance for trading account."""
        if not self._token_contract:
            return 0

        try:
            return self._token_contract.functions.balanceOf(
                self._account.address
            ).call()
        except Exception as e:
            logger.error(f"Balance check error: {e}")
            return 0

    async def _get_current_price(self) -> Optional[float]:
        """Get current market price from auction contract."""
        if not self._auction_contract:
            return None

        try:
            price_wei = self._auction_contract.functions.getCurrentPrice().call()
            return self._from_token_units(price_wei)
        except Exception:
            return None

    def _get_gas_price(self) -> int:
        """Get gas price with multiplier."""
        if not self._w3:
            return 20_000_000_000  # 20 gwei default

        try:
            base_price = self._w3.eth.gas_price
            adjusted_price = int(base_price * self.config.gas_price_multiplier)
            max_price_wei = int(self.config.max_gas_price_gwei * 1e9)
            return min(adjusted_price, max_price_wei)
        except Exception:
            return 20_000_000_000

    def _to_token_units(self, amount: float) -> int:
        """Convert amount to token units (wei)."""
        return int(Decimal(str(amount)) * Decimal(10 ** self._token_decimals))

    def _from_token_units(self, amount: int) -> float:
        """Convert token units to float."""
        return float(Decimal(amount) / Decimal(10 ** self._token_decimals))

    def _update_stats(self, result: TransactionResult, action: TradingAction):
        """Update execution statistics."""
        if result.is_success:
            self._stats["total_value_traded"] += action.total_value

    async def get_auction_state(self) -> Optional[Dict[str, Any]]:
        """Get current auction state."""
        if not self._auction_contract:
            return None

        try:
            state = self._auction_contract.functions.getAuctionState().call()
            return {
                "is_open": state[0],
                "end_time": state[1],
                "total_bids": state[2],
                "total_asks": state[3],
            }
        except Exception as e:
            logger.error(f"Auction state error: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """Get executor statistics."""
        return {
            **self._stats,
            "dry_run": self.config.dry_run,
            "connected": self._w3 is not None and self._w3.is_connected() if self._w3 else False,
            "account": self._account.address if self._account else None,
        }
