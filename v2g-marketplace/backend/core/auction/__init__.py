"""
Auction mechanisms for V2G energy trading.

This package provides market clearing mechanisms for the V2G marketplace,
enabling efficient price discovery between energy buyers and sellers.

Available Classes:
    Bid: Represents a buy or sell order in the auction
    McAfeeAuction: McAfee double auction mechanism
    ClearingResult: Result of market clearing operation

Example:
    >>> from backend.core.auction import Bid, McAfeeAuction
    >>> auction = McAfeeAuction()
    >>> auction.add_bid(Bid("seller1", quantity=10.0, price=5.0, is_buy=False))
    >>> auction.add_bid(Bid("buyer1", quantity=10.0, price=8.0, is_buy=True))
    >>> result = auction.clear_market()
    >>> print(f"Cleared at {result.clearing_price} INR/kWh")
"""

from .mcafee import Bid, ClearingResult, McAfeeAuction

__all__ = ["Bid", "McAfeeAuction", "ClearingResult"]
