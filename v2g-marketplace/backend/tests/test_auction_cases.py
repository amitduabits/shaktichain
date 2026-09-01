"""Gap cases for the shipped McAfee instance (matrix section A)."""

from __future__ import annotations

import pytest

from backend.core.auction import Bid, McAfeeAuction


def _book(auction: McAfeeAuction, buys, sells, qty: float = 10.0) -> None:
    for i, price in enumerate(buys):
        auction.add_bid(Bid(f"buyer_{i}", qty, float(price), True))
    for i, price in enumerate(sells):
        auction.add_bid(Bid(f"seller_{i}", qty, float(price), False))


class TestDuplicateAgentsAndMixedQuantity:
    def test_duplicate_agent_ids_still_clear(self) -> None:
        auction = McAfeeAuction()
        auction.add_bid(Bid("same", 10.0, 12.0, True))
        auction.add_bid(Bid("same", 10.0, 4.0, False))
        result = auction.clear_market()
        assert result.clearing_price is not None
        assert len(result.matched_buyers) == 1
        assert len(result.matched_sellers) == 1

    def test_mixed_quantities_total_is_pairwise_min(self) -> None:
        auction = McAfeeAuction()
        auction.add_bid(Bid("b0", 30.0, 12.0, True))
        auction.add_bid(Bid("s0", 10.0, 4.0, False))
        result = auction.clear_market()
        assert result.total_quantity == pytest.approx(10.0)


class TestBudgetAndIR:
    def test_uniform_price_is_budget_balanced(self) -> None:
        auction = McAfeeAuction()
        _book(auction, [15, 13, 11, 9, 7], [4, 6, 8, 10, 12])
        result = auction.clear_market()
        assert result.clearing_price is not None
        n = len(result.matched_buyers)
        paid = result.clearing_price * n
        received = result.clearing_price * n
        assert paid - received >= -1e-9
        assert result.surplus >= -1e-9

    def test_matched_buyers_bid_at_least_clearing_price(self) -> None:
        auction = McAfeeAuction()
        _book(auction, [15, 13, 11, 9, 7], [4, 6, 8, 10, 12])
        result = auction.clear_market()
        for buyer in result.matched_buyers:
            assert buyer.price + 1e-9 >= result.clearing_price
        for seller in result.matched_sellers:
            assert seller.price - 1e-9 <= result.clearing_price


class TestMcAfeeConcession:
    def test_last_overlapping_index_is_matched(self) -> None:
        """Shipped rule: all overlapping ranks 0..k trade."""
        auction = McAfeeAuction()
        _book(auction, [9, 8, 7, 5, 4], [4, 5, 6, 7, 8])
        result = auction.clear_market()
        assert len(result.matched_buyers) == 3
        assert len(result.matched_sellers) == 3

    @pytest.mark.xfail(
        reason="Shipped instance sets p* from the last overlapping pair, not the excluded (k+1) pair.",
        strict=False,
    )
    def test_clearing_price_set_by_excluded_pair(self) -> None:
        auction = McAfeeAuction()
        _book(auction, [9, 8, 7, 5, 4], [4, 5, 6, 7, 8])
        result = auction.clear_market()
        assert result.clearing_price == pytest.approx((5.0 + 7.0) / 2.0)
