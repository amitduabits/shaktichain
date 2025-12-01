"""
Blockchain API Routes.

Provides REST and WebSocket endpoints for blockchain interactions.
"""

import asyncio
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from services.blockchain import (
    BlockchainService,
    get_blockchain_service,
    NetworkType,
)
from services.blockchain.transactions import TransactionStatus
from api.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/blockchain", tags=["blockchain"])


# === Pydantic Models ===

class BalanceResponse(BaseModel):
    """Token balance response."""
    address: str
    balance: str
    balance_wei: str


class AuctionStatusResponse(BaseModel):
    """Auction status response."""
    round_id: int
    start_time: int
    end_time: int
    clearing_price: str
    total_bid_volume: str
    total_ask_volume: str
    state: str
    is_open: bool
    time_remaining: int


class SubmitOrderRequest(BaseModel):
    """Submit order request."""
    quantity: str = Field(..., description="Quantity in ether units")
    price: str = Field(..., description="Price in ether units")


class TransactionResponse(BaseModel):
    """Transaction response."""
    tx_hash: str
    status: str
    block_number: Optional[int] = None
    gas_used: Optional[int] = None
    error: Optional[str] = None
    explorer_url: Optional[str] = None


class StakeRequest(BaseModel):
    """Stake/unstake request."""
    amount: str = Field(..., description="Amount in ether units")


class StakeInfoResponse(BaseModel):
    """Stake info response."""
    address: str
    amount: str
    shares: int
    staked_at: int
    lock_end_time: int
    pending_rewards: str
    is_locked: bool


class ReputationResponse(BaseModel):
    """Reputation response."""
    address: str
    reputation: int
    tier: str
    total_trades: int
    successful_trades: int
    is_kyc_verified: bool


class TradeResponse(BaseModel):
    """Trade record response."""
    round_id: int
    trade_id: int
    buyer: str
    seller: str
    quantity: str
    price: str
    block_number: int
    transaction_hash: str
    timestamp: Optional[int] = None


class ConnectionInfo(BaseModel):
    """Connection info response."""
    connected: bool
    network: str
    chain_id: int
    block_number: Optional[int] = None
    account: Optional[str] = None


class SyncStateResponse(BaseModel):
    """Sync state response."""
    last_synced_block: int
    last_sync_time: float
    total_events_synced: int
    is_syncing: bool
    error: Optional[str] = None


# === Helper Functions ===

def get_service() -> BlockchainService:
    """Get blockchain service instance."""
    return get_blockchain_service()


def parse_ether(value: str) -> int:
    """Parse ether string to wei."""
    from web3 import Web3
    return Web3.to_wei(float(value), "ether")


def format_ether(value: int) -> str:
    """Format wei to ether string."""
    from web3 import Web3
    return str(Web3.from_wei(value, "ether"))


# === Connection Endpoints ===

@router.get("/status", response_model=ConnectionInfo)
async def get_connection_status():
    """Get blockchain connection status."""
    service = get_service()
    info = service.get_connection_info()
    return ConnectionInfo(**info)


@router.get("/sync/state", response_model=SyncStateResponse)
async def get_sync_state(current_user: dict = Depends(get_current_user)):
    """Get blockchain sync state."""
    service = get_service()
    state = service.get_sync_state()

    if state is None:
        raise HTTPException(status_code=503, detail="Sync service not configured")

    return SyncStateResponse(
        last_synced_block=state.last_synced_block,
        last_sync_time=state.last_sync_time,
        total_events_synced=state.total_events_synced,
        is_syncing=state.is_syncing,
        error=state.error,
    )


# === Token Endpoints ===

@router.get("/balance/{address}", response_model=BalanceResponse)
async def get_token_balance(address: str):
    """
    Get SHAKTI token balance for an address.

    Args:
        address: Ethereum address to check.
    """
    service = get_service()

    try:
        balance_wei = service.get_token_balance(address)
        balance = format_ether(balance_wei)

        return BalanceResponse(
            address=address,
            balance=balance,
            balance_wei=str(balance_wei),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get balance")


@router.post("/transfer", response_model=TransactionResponse)
async def transfer_tokens(
    to: str,
    amount: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Transfer SHAKTI tokens.

    Args:
        to: Recipient address.
        amount: Amount to transfer in ether units.
    """
    service = get_service()

    if not service.address:
        raise HTTPException(status_code=503, detail="No signing account configured")

    try:
        amount_wei = parse_ether(amount)
        result = service.transfer_tokens(to, amount_wei)

        return TransactionResponse(
            tx_hash=result.tx_hash,
            status=result.status.value,
            block_number=result.block_number,
            gas_used=result.gas_used,
            error=result.error,
            explorer_url=result.explorer_url,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error transferring tokens: {e}")
        raise HTTPException(status_code=500, detail="Failed to transfer tokens")


# === Auction Endpoints ===

@router.get("/auction/current")
async def get_current_round():
    """Get current auction round ID."""
    service = get_service()

    try:
        round_id = service.get_current_round()
        return {"round_id": round_id}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting current round: {e}")
        raise HTTPException(status_code=500, detail="Failed to get current round")


@router.get("/auction/{round_id}", response_model=AuctionStatusResponse)
async def get_auction_status(round_id: int):
    """
    Get auction round status.

    Args:
        round_id: Auction round ID.
    """
    service = get_service()

    try:
        status = service.get_auction_status(round_id)

        return AuctionStatusResponse(
            round_id=status.round_id,
            start_time=status.start_time,
            end_time=status.end_time,
            clearing_price=format_ether(status.clearing_price),
            total_bid_volume=format_ether(status.total_bid_volume),
            total_ask_volume=format_ether(status.total_ask_volume),
            state=status.state.name.lower(),
            is_open=status.is_open,
            time_remaining=status.time_remaining,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting auction status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get auction status")


@router.post("/bid", response_model=TransactionResponse)
async def submit_bid(
    request: SubmitOrderRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Submit a buy order (bid).

    Args:
        request: Order details with quantity and max price.
    """
    service = get_service()

    if not service.address:
        raise HTTPException(status_code=503, detail="No signing account configured")

    try:
        quantity = parse_ether(request.quantity)
        price = parse_ether(request.price)
        result = service.submit_bid(quantity, price)

        return TransactionResponse(
            tx_hash=result.tx_hash,
            status=result.status.value,
            block_number=result.block_number,
            gas_used=result.gas_used,
            error=result.error,
            explorer_url=result.explorer_url,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting bid: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit bid")


@router.post("/ask", response_model=TransactionResponse)
async def submit_ask(
    request: SubmitOrderRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Submit a sell order (ask).

    Args:
        request: Order details with quantity and min price.
    """
    service = get_service()

    if not service.address:
        raise HTTPException(status_code=503, detail="No signing account configured")

    try:
        quantity = parse_ether(request.quantity)
        price = parse_ether(request.price)
        result = service.submit_ask(quantity, price)

        return TransactionResponse(
            tx_hash=result.tx_hash,
            status=result.status.value,
            block_number=result.block_number,
            gas_used=result.gas_used,
            error=result.error,
            explorer_url=result.explorer_url,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error submitting ask: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit ask")


@router.delete("/order/{order_id}", response_model=TransactionResponse)
async def cancel_order(
    order_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Cancel an order."""
    service = get_service()

    if not service.address:
        raise HTTPException(status_code=503, detail="No signing account configured")

    try:
        result = service.cancel_order(order_id)

        return TransactionResponse(
            tx_hash=result.tx_hash,
            status=result.status.value,
            block_number=result.block_number,
            gas_used=result.gas_used,
            error=result.error,
            explorer_url=result.explorer_url,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel order")


@router.get("/order/{order_id}")
async def get_order(order_id: int):
    """Get order details."""
    service = get_service()

    try:
        order = service.get_order(order_id)
        return order

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting order: {e}")
        raise HTTPException(status_code=500, detail="Failed to get order")


@router.get("/orders/{address}")
async def get_user_orders(
    address: str,
    round_id: Optional[int] = Query(None, description="Round ID (uses current if not specified)"),
):
    """Get user's order IDs for a round."""
    service = get_service()

    try:
        if round_id is None:
            round_id = service.get_current_round()

        order_ids = service.get_user_orders(address, round_id)
        return {"address": address, "round_id": round_id, "order_ids": order_ids}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user orders: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user orders")


# === Staking Endpoints ===

@router.get("/staking/info/{address}", response_model=StakeInfoResponse)
async def get_stake_info(address: str):
    """Get user's staking info."""
    service = get_service()

    try:
        info = service.get_stake_info(address)

        return StakeInfoResponse(
            address=info.address,
            amount=info.amount_formatted,
            shares=info.shares,
            staked_at=info.staked_at,
            lock_end_time=info.lock_end_time,
            pending_rewards=info.pending_rewards_formatted,
            is_locked=info.is_locked,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting stake info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get stake info")


@router.get("/staking/stats")
async def get_staking_stats():
    """Get staking pool statistics."""
    service = get_service()

    try:
        stats = service.get_staking_stats()
        return stats

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting staking stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get staking stats")


@router.post("/staking/stake", response_model=TransactionResponse)
async def stake_tokens(
    request: StakeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Stake SHAKTI tokens."""
    service = get_service()

    if not service.address:
        raise HTTPException(status_code=503, detail="No signing account configured")

    try:
        amount = parse_ether(request.amount)
        result = service.stake(amount)

        return TransactionResponse(
            tx_hash=result.tx_hash,
            status=result.status.value,
            block_number=result.block_number,
            gas_used=result.gas_used,
            error=result.error,
            explorer_url=result.explorer_url,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error staking tokens: {e}")
        raise HTTPException(status_code=500, detail="Failed to stake tokens")


@router.post("/staking/unstake", response_model=TransactionResponse)
async def unstake_tokens(
    request: StakeRequest,
    current_user: dict = Depends(get_current_user),
):
    """Unstake SHAKTI tokens."""
    service = get_service()

    if not service.address:
        raise HTTPException(status_code=503, detail="No signing account configured")

    try:
        amount = parse_ether(request.amount)
        result = service.unstake(amount)

        return TransactionResponse(
            tx_hash=result.tx_hash,
            status=result.status.value,
            block_number=result.block_number,
            gas_used=result.gas_used,
            error=result.error,
            explorer_url=result.explorer_url,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error unstaking tokens: {e}")
        raise HTTPException(status_code=500, detail="Failed to unstake tokens")


@router.post("/staking/claim", response_model=TransactionResponse)
async def claim_rewards(current_user: dict = Depends(get_current_user)):
    """Claim staking rewards."""
    service = get_service()

    if not service.address:
        raise HTTPException(status_code=503, detail="No signing account configured")

    try:
        result = service.claim_rewards()

        return TransactionResponse(
            tx_hash=result.tx_hash,
            status=result.status.value,
            block_number=result.block_number,
            gas_used=result.gas_used,
            error=result.error,
            explorer_url=result.explorer_url,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error claiming rewards: {e}")
        raise HTTPException(status_code=500, detail="Failed to claim rewards")


# === Reputation Endpoints ===

@router.get("/reputation/{address}", response_model=ReputationResponse)
async def get_reputation(address: str):
    """Get user's reputation info."""
    service = get_service()

    try:
        rep = service.get_reputation(address)

        return ReputationResponse(
            address=rep.address,
            reputation=rep.reputation,
            tier=rep.tier_name,
            total_trades=rep.total_trades,
            successful_trades=rep.successful_trades,
            is_kyc_verified=rep.is_kyc_verified,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting reputation: {e}")
        raise HTTPException(status_code=500, detail="Failed to get reputation")


@router.get("/reputation/{address}/registered")
async def is_registered(address: str):
    """Check if user is registered."""
    service = get_service()

    try:
        registered = service.is_registered(address)
        return {"address": address, "is_registered": registered}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error checking registration: {e}")
        raise HTTPException(status_code=500, detail="Failed to check registration")


@router.post("/reputation/register", response_model=TransactionResponse)
async def register_user(current_user: dict = Depends(get_current_user)):
    """Register as a prosumer."""
    service = get_service()

    if not service.address:
        raise HTTPException(status_code=503, detail="No signing account configured")

    try:
        result = service.register_user()

        return TransactionResponse(
            tx_hash=result.tx_hash,
            status=result.status.value,
            block_number=result.block_number,
            gas_used=result.gas_used,
            error=result.error,
            explorer_url=result.explorer_url,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(status_code=500, detail="Failed to register user")


# === Trade History Endpoints ===

@router.get("/trades", response_model=List[TradeResponse])
async def get_trades(
    round_id: Optional[int] = Query(None, description="Filter by round ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
):
    """Get synced trades from database."""
    service = get_service()

    try:
        trades = service.get_synced_trades(round_id, limit)

        return [
            TradeResponse(
                round_id=t["round_id"],
                trade_id=t["trade_id"],
                buyer=t["buyer"],
                seller=t["seller"],
                quantity=t["quantity"],
                price=t["price"],
                block_number=t["block_number"],
                transaction_hash=t["transaction_hash"],
                timestamp=t.get("timestamp"),
            )
            for t in trades
        ]

    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        raise HTTPException(status_code=500, detail="Failed to get trades")


# === WebSocket for Events ===

@router.websocket("/events")
async def websocket_events(websocket: WebSocket):
    """
    WebSocket endpoint for real-time blockchain events.

    Streams new events as they are detected.
    """
    await websocket.accept()

    service = get_service()
    events_queue = asyncio.Queue()

    def event_callback(event):
        """Callback to queue events."""
        asyncio.create_task(events_queue.put(event.to_dict()))

    # Subscribe to events
    subscriptions = []
    try:
        # Subscribe to key events
        for contract, event in [
            ("EnergyAuction", "BidSubmitted"),
            ("EnergyAuction", "AskSubmitted"),
            ("EnergyAuction", "TradeExecuted"),
            ("EnergyAuction", "RoundCleared"),
            ("StakingPool", "Staked"),
            ("StakingPool", "Unstaked"),
        ]:
            sub_id = service.events.subscribe(contract, event, event_callback)
            subscriptions.append(sub_id)

        # Start event listener if not running
        if not service.events.is_running:
            service.events.start()

        # Stream events to client
        while True:
            try:
                event = await asyncio.wait_for(events_queue.get(), timeout=30)
                await websocket.send_json(event)
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Cleanup subscriptions
        for sub_id in subscriptions:
            service.events.unsubscribe(sub_id)
