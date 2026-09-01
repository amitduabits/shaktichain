import { describe, it, expect } from 'vitest';
import {
  createInitialDemoLedger,
  stakeDemoTokens,
  unstakeDemoTokens,
  claimDemoRewards,
  placeDemoOrder,
  accrueDemoRewards,
  resetDemoLedger,
} from '../../demo/ledger';

describe('demo ledger engine', () => {
  it('stakes successfully and updates balances', () => {
    const ledger = createInitialDemoLedger(0);
    const result = stakeDemoTokens(ledger, 100, 0);

    expect(result.ok).toBe(true);
    expect(result.ledger.account.stakedAmount).toBeCloseTo(600, 6);
    expect(result.ledger.account.tokenBalance).toBeCloseTo(1150, 6);
  });

  it('rejects staking when balance is insufficient', () => {
    const ledger = createInitialDemoLedger(0);
    const result = stakeDemoTokens(ledger, 2000, 0);

    expect(result.ok).toBe(false);
    expect(result.code).toBe('INSUFFICIENT_BALANCE');
  });

  it('unstakes successfully and rejects unstaking above staked amount', () => {
    const ledger = createInitialDemoLedger(0);
    const success = unstakeDemoTokens(ledger, 100, 0);
    const failure = unstakeDemoTokens(ledger, 700, 0);

    expect(success.ok).toBe(true);
    expect(success.ledger.account.stakedAmount).toBeCloseTo(400, 6);
    expect(success.ledger.account.tokenBalance).toBeCloseTo(1350, 6);

    expect(failure.ok).toBe(false);
    expect(failure.code).toBe('INSUFFICIENT_STAKED');
  });

  it('claims rewards and moves pending rewards into token balance', () => {
    const ledger = createInitialDemoLedger(0);
    const result = claimDemoRewards(ledger, 0);

    expect(result.ok).toBe(true);
    expect(result.claimed).toBeCloseTo(12.5, 6);
    expect(result.ledger.account.pendingRewards).toBe(0);
    expect(result.ledger.account.tokenBalance).toBeCloseTo(1262.5, 6);
    expect(result.ledger.account.totalClaimedRewards).toBeCloseTo(12.5, 6);
  });

  it('executes buy and sell orders with 2% fee and 30/70 split accounting', () => {
    const seed = createInitialDemoLedger(0);
    const buy = placeDemoOrder(seed, { side: 'buy', quantity: 10, price: 5, nowMs: 0 });
    const sell = placeDemoOrder(seed, { side: 'sell', quantity: 20, price: 4, nowMs: 0 });

    expect(buy.ok).toBe(true);
    expect(buy.ledger.account.tokenBalance).toBeCloseTo(1199, 6); // 1250 - 50 - 1 fee
    expect(buy.ledger.account.energyInventory).toBeCloseTo(170, 6);
    expect(buy.ledger.market.feeBurned).toBeCloseTo(0.3, 6);
    expect(buy.ledger.market.feeToStakers).toBeCloseTo(0.7, 6);
    expect(buy.ledger.account.pendingRewards).toBeCloseTo(12.50007, 6);

    expect(sell.ok).toBe(true);
    expect(sell.ledger.account.tokenBalance).toBeCloseTo(1328.4, 6); // 1250 + (80 - 1.6)
    expect(sell.ledger.account.energyInventory).toBeCloseTo(140, 6);
    expect(sell.ledger.market.feeBurned).toBeCloseTo(0.48, 6);
    expect(sell.ledger.market.feeToStakers).toBeCloseTo(1.12, 6);
  });

  it('accrues rewards over elapsed time and rolls market rounds', () => {
    const ledger = createInitialDemoLedger(0);
    const withStake = {
      ...ledger,
      account: {
        ...ledger.account,
        stakedAmount: 1000,
        pendingRewards: 0,
      },
      staking: {
        ...ledger.staking,
        apr: 10,
      },
    };

    const result = accrueDemoRewards(withStake, 3600 * 1000);

    expect(result.account.pendingRewards).toBeCloseTo(0.011416, 6);
    expect(result.market.currentRound).toBe(46);
  });

  it('resetDemoLedger returns the seeded fixture', () => {
    const seed = createInitialDemoLedger(0);
    const bought = placeDemoOrder(seed, { side: 'buy', quantity: 10, price: 5, nowMs: 0 });
    expect(bought.ok).toBe(true);
    const reset = resetDemoLedger(0);
    expect(reset.account.tokenBalance).toBe(seed.account.tokenBalance);
    expect(reset.account.stakedAmount).toBe(seed.account.stakedAmount);
    expect(reset.market.totalTrades).toBe(0);
    expect(reset.market.currentRound).toBe(seed.market.currentRound);
  });
});
