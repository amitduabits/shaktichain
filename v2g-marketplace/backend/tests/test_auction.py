"""
Unit tests for the McAfee Double Auction mechanism.

Tests cover:
1. Basic market clearing with overlapping bids
2. No-trade scenario when bids don't overlap
3. Incentive compatibility verification
"""

import sys
from pathlib import Path

import pytest

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.auction import Bid, ClearingResult, McAfeeAuction


class TestMcAfeeAuctionClearing:
    """Test basic market clearing functionality."""

    def test_five_buyers_five_sellers_should_clear(self) -> None:
        """
        Test that a market with 5 buyers and 5 sellers clears successfully.

        Setup:
        - 5 buyers with prices: 15, 13, 11, 9, 7 INR/kWh
        - 5 sellers with prices: 4, 6, 8, 10, 12 INR/kWh

        Expected:
        - Market should clear with some matched trades
        - Buyers with high bids matched to sellers with low asks
        """
        auction = McAfeeAuction()

        # Add 5 buyers (sorted by price desc: 15, 13, 11, 9, 7)
        buyer_prices = [15.0, 13.0, 11.0, 9.0, 7.0]
        for i, price in enumerate(buyer_prices):
            auction.add_bid(Bid(
                agent_id=f"buyer_{i}",
                quantity=10.0,
                price=price,
                is_buy=True,
            ))

        # Add 5 sellers (sorted by price asc: 4, 6, 8, 10, 12)
        seller_prices = [4.0, 6.0, 8.0, 10.0, 12.0]
        for i, price in enumerate(seller_prices):
            auction.add_bid(Bid(
                agent_id=f"seller_{i}",
                quantity=10.0,
                price=price,
                is_buy=False,
            ))

        result = auction.clear_market()

        # Verify market cleared
        assert result.clearing_price is not None, "Market should have cleared"
        assert len(result.matched_buyers) > 0, "Should have matched buyers"
        assert len(result.matched_sellers) > 0, "Should have matched sellers"
        assert len(result.matched_buyers) == len(result.matched_sellers), \
            "Number of matched buyers should equal matched sellers"

        # Verify clearing price is reasonable (between lowest sell and highest buy)
        assert result.clearing_price >= min(seller_prices), \
            "Clearing price should be >= lowest seller ask"
        assert result.clearing_price <= max(buyer_prices), \
            "Clearing price should be <= highest buyer bid"

        # Verify all matched buyers bid >= clearing price
        for buyer in result.matched_buyers:
            assert buyer.price >= result.clearing_price, \
                f"Matched buyer bid {buyer.price} should be >= clearing price {result.clearing_price}"

        # Verify all matched sellers ask <= clearing price
        for seller in result.matched_sellers:
            assert seller.price <= result.clearing_price, \
                f"Matched seller ask {seller.price} should be <= clearing price {result.clearing_price}"

        # With these prices, we expect:
        # buyer[0]=15 >= seller[0]=4  -> trade
        # buyer[1]=13 >= seller[1]=6  -> trade
        # buyer[2]=11 >= seller[2]=8  -> trade
        # buyer[3]=9  >= seller[3]=10? No, 9 < 10, so k=2
        # So we should have 3 trades (indices 0, 1, 2)
        assert len(result.matched_buyers) >= 3, \
            "Should have at least 3 matched pairs"


class TestMcAfeeAuctionNoOverlap:
    """Test scenarios where no trades should occur."""

    def test_no_overlap_returns_no_trades(self) -> None:
        """
        Test that when buyer bids are all below seller asks, no trades occur.

        Setup:
        - Buyers bid: 3, 4, 5 INR/kWh (too low)
        - Sellers ask: 10, 11, 12 INR/kWh (too high)

        Expected:
        - No clearing price
        - No matched buyers or sellers
        """
        auction = McAfeeAuction()

        # Buyers with low prices
        for i, price in enumerate([3.0, 4.0, 5.0]):
            auction.add_bid(Bid(
                agent_id=f"low_buyer_{i}",
                quantity=10.0,
                price=price,
                is_buy=True,
            ))

        # Sellers with high prices
        for i, price in enumerate([10.0, 11.0, 12.0]):
            auction.add_bid(Bid(
                agent_id=f"high_seller_{i}",
                quantity=10.0,
                price=price,
                is_buy=False,
            ))

        result = auction.clear_market()

        # Verify no trades occurred
        assert result.clearing_price is None, \
            "No clearing price when bids don't overlap"
        assert len(result.matched_buyers) == 0, \
            "Should have no matched buyers"
        assert len(result.matched_sellers) == 0, \
            "Should have no matched sellers"
        assert result.total_quantity == 0.0, \
            "Total traded quantity should be zero"


class TestMcAfeeIncentiveCompatibility:
    """Test incentive compatibility properties of McAfee auction."""

    def test_truthful_bid_wins_when_it_should(self) -> None:
        """
        Test that a truthful bidder wins when their true value exceeds clearing price.

        Incentive Compatibility means that bidding truthfully is always optimal.
        A buyer with true value V should:
        - Win and benefit if V > clearing_price
        - Not be worse off by bidding truthfully

        Setup:
        - Create a market where we know the approximate clearing price
        - Add a truthful buyer whose value is clearly above the clearing price
        - Verify the truthful buyer is matched

        Scenario:
        - Existing buyers: 20, 15 INR/kWh
        - Existing sellers: 5, 10 INR/kWh
        - Truthful buyer has value 18 INR/kWh and bids truthfully
        - Expected clearing around 10-15 INR/kWh
        - Truthful buyer at 18 should definitely be matched
        """
        auction = McAfeeAuction()

        # Existing market participants
        auction.add_bid(Bid("buyer_high", 10.0, 20.0, is_buy=True))
        auction.add_bid(Bid("buyer_mid", 10.0, 15.0, is_buy=True))
        auction.add_bid(Bid("seller_low", 10.0, 5.0, is_buy=False))
        auction.add_bid(Bid("seller_mid", 10.0, 10.0, is_buy=False))

        # Truthful buyer with value 18 INR/kWh
        truthful_buyer = Bid("truthful_buyer", 10.0, 18.0, is_buy=True)
        auction.add_bid(truthful_buyer)

        result = auction.clear_market()

        # Market should clear
        assert result.clearing_price is not None, "Market should clear"

        # Find if truthful buyer is in matched buyers
        matched_buyer_ids = [b.agent_id for b in result.matched_buyers]
        truthful_won = "truthful_buyer" in matched_buyer_ids

        # The truthful buyer bid 18, which is above the expected clearing
        # With buyers [20, 18, 15] and sellers [5, 10]:
        # - 20 >= 5 -> match
        # - 18 >= 10 -> match
        # - 15 >= ??? -> no more sellers
        # So truthful buyer at 18 should definitely match
        assert truthful_won, \
            "Truthful buyer with bid above clearing price should win"

        # Verify the truthful buyer benefits (pays less than their bid)
        if truthful_won:
            assert result.clearing_price <= truthful_buyer.price, \
                "Matched buyer should pay <= their bid (non-negative utility)"

    def test_truthful_seller_wins_when_it_should(self) -> None:
        """
        Test that a truthful seller wins when their cost is below clearing price.

        A seller with true cost C should:
        - Win and benefit if C < clearing_price
        - Not be worse off by bidding truthfully
        """
        auction = McAfeeAuction()

        # Existing market
        auction.add_bid(Bid("buyer_1", 10.0, 25.0, is_buy=True))
        auction.add_bid(Bid("buyer_2", 10.0, 20.0, is_buy=True))
        auction.add_bid(Bid("seller_high", 10.0, 15.0, is_buy=False))

        # Truthful seller with cost 8 INR/kWh
        truthful_seller = Bid("truthful_seller", 10.0, 8.0, is_buy=False)
        auction.add_bid(truthful_seller)

        result = auction.clear_market()

        # Market should clear
        assert result.clearing_price is not None, "Market should clear"

        # Find if truthful seller is in matched sellers
        matched_seller_ids = [s.agent_id for s in result.matched_sellers]
        truthful_won = "truthful_seller" in matched_seller_ids

        # With buyers [25, 20] and sellers [8, 15]:
        # - 25 >= 8 -> match
        # - 20 >= 15 -> match
        # Truthful seller at 8 should definitely match
        assert truthful_won, \
            "Truthful seller with ask below clearing price should win"

        # Verify the truthful seller benefits (receives more than their ask)
        if truthful_won:
            assert result.clearing_price >= truthful_seller.price, \
                "Matched seller should receive >= their ask (non-negative utility)"


class TestBidValidation:
    """Test bid validation and edge cases."""

    def test_negative_quantity_raises_error(self) -> None:
        """Test that negative quantity raises ValueError."""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            Bid("agent", quantity=-10.0, price=5.0, is_buy=True)

    def test_zero_quantity_raises_error(self) -> None:
        """Test that zero quantity raises ValueError."""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            Bid("agent", quantity=0.0, price=5.0, is_buy=True)

    def test_negative_price_raises_error(self) -> None:
        """Test that negative price raises ValueError."""
        with pytest.raises(ValueError, match="Price cannot be negative"):
            Bid("agent", quantity=10.0, price=-5.0, is_buy=True)

    def test_cannot_add_bid_after_clearing(self) -> None:
        """Test that adding bids after market clearing raises error."""
        auction = McAfeeAuction()
        auction.add_bid(Bid("buyer", 10.0, 10.0, is_buy=True))
        auction.add_bid(Bid("seller", 10.0, 5.0, is_buy=False))
        auction.clear_market()

        with pytest.raises(ValueError, match="Cannot add bids after market has cleared"):
            auction.add_bid(Bid("late_buyer", 10.0, 15.0, is_buy=True))


class TestAuctionReset:
    """Test auction reset functionality."""

    def test_reset_allows_new_bids(self) -> None:
        """Test that reset allows new trading round."""
        auction = McAfeeAuction()
        auction.add_bid(Bid("buyer", 10.0, 10.0, is_buy=True))
        auction.add_bid(Bid("seller", 10.0, 5.0, is_buy=False))
        auction.clear_market()

        # Reset and verify we can add bids again
        auction.reset()

        # Should not raise
        auction.add_bid(Bid("new_buyer", 10.0, 12.0, is_buy=True))
        auction.add_bid(Bid("new_seller", 10.0, 6.0, is_buy=False))

        result = auction.clear_market()
        assert result.clearing_price is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
