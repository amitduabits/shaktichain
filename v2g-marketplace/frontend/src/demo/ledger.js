import { createRoleFixtures } from './fixtures';

export const DEMO_LEDGER_SCHEMA_VERSION = 1;
export const MAX_VEHICLES = 20;
export const MIN_VEHICLES = 1;

const YEAR_SECONDS = 365 * 24 * 60 * 60;
const DEFAULT_ROUND_DURATION_SECONDS = 15 * 60;
const MAX_RECENT_ORDERS = 30;
const MAX_RECENT_ACTIONS = 40;

function roundTo(value, places = 6) {
  const factor = 10 ** places;
  return Math.round((Number(value) + Number.EPSILON) * factor) / factor;
}

function toPositiveNumber(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }
  return parsed;
}

function nowSeconds(nowMs) {
  return Math.floor((nowMs ?? Date.now()) / 1000);
}

function touchMeta(ledger, currentSeconds) {
  return {
    ...ledger,
    meta: {
      ...ledger.meta,
      updatedAt: new Date(currentSeconds * 1000).toISOString(),
      lastAccrualAtSec: currentSeconds,
    },
  };
}

function appendAction(ledger, action) {
  return {
    ...ledger,
    recentActions: [action, ...(ledger.recentActions ?? [])].slice(0, MAX_RECENT_ACTIONS),
  };
}

function buildAction(type, details, currentSeconds) {
  return {
    id: `act-${currentSeconds}-${Math.floor(Math.random() * 100000)}`,
    type,
    createdAt: new Date(currentSeconds * 1000).toISOString(),
    ...details,
  };
}

export function createInitialDemoLedger(nowMs = Date.now()) {
  const currentSeconds = nowSeconds(nowMs);
  const roundDurationSec = DEFAULT_ROUND_DURATION_SECONDS;
  const roundStartedAtSec = currentSeconds - (currentSeconds % roundDurationSec);

  return {
    schemaVersion: DEMO_LEDGER_SCHEMA_VERSION,
    meta: {
      createdAt: new Date(currentSeconds * 1000).toISOString(),
      updatedAt: new Date(currentSeconds * 1000).toISOString(),
      lastAccrualAtSec: currentSeconds,
    },
    market: {
      currentRound: 42,
      roundDurationSec,
      roundStartedAtSec,
      isOpen: true,
      feeRate: 0.02,
      feeBurned: 0,
      feeToStakers: 0,
      totalVolumeKwh: 0,
      totalTrades: 0,
      nextOrderId: 1,
    },
    account: {
      tokenBalance: 1250,
      energyInventory: 160,
      stakedAmount: 500,
      pendingRewards: 12.5,
      totalClaimedRewards: 0,
      totalFeesPaid: 0,
    },
    staking: {
      apr: 12.5,
      totalStaked: 5000000,
    },
    recentOrders: [],
    recentActions: [],
    ...createRoleFixtures(),
  };
}

export function isValidDemoLedgerShape(ledger) {
  if (!ledger || typeof ledger !== 'object') return false;
  if (ledger.schemaVersion !== DEMO_LEDGER_SCHEMA_VERSION) return false;

  return Boolean(
    ledger.meta &&
      ledger.market &&
      ledger.account &&
      ledger.staking &&
      Array.isArray(ledger.recentOrders) &&
      Array.isArray(ledger.recentActions)
  );
}

export function normalizeDemoLedger(ledger, nowMs = Date.now()) {
  if (!isValidDemoLedgerShape(ledger)) {
    return createInitialDemoLedger(nowMs);
  }

  return {
    ...createInitialDemoLedger(nowMs),
    ...ledger,
    meta: {
      ...createInitialDemoLedger(nowMs).meta,
      ...ledger.meta,
    },
    market: {
      ...createInitialDemoLedger(nowMs).market,
      ...ledger.market,
    },
    account: {
      ...createInitialDemoLedger(nowMs).account,
      ...ledger.account,
    },
    staking: {
      ...createInitialDemoLedger(nowMs).staking,
      ...ledger.staking,
    },
    recentOrders: Array.isArray(ledger.recentOrders) ? ledger.recentOrders.slice(0, MAX_RECENT_ORDERS) : [],
    recentActions: Array.isArray(ledger.recentActions) ? ledger.recentActions.slice(0, MAX_RECENT_ACTIONS) : [],
    vehicles: Array.isArray(ledger.vehicles) && ledger.vehicles.length
      ? ledger.vehicles
      : createRoleFixtures().vehicles,
    sites: Array.isArray(ledger.sites) && ledger.sites.length
      ? ledger.sites
      : createRoleFixtures().sites,
    feeders: Array.isArray(ledger.feeders) && ledger.feeders.length
      ? ledger.feeders
      : createRoleFixtures().feeders,
    portfolio: ledger.portfolio && typeof ledger.portfolio === 'object'
      ? { ...createRoleFixtures().portfolio, ...ledger.portfolio }
      : createRoleFixtures().portfolio,
  };
}

export function getRoundTimeRemaining(ledger, nowMs = Date.now()) {
  const currentSeconds = nowSeconds(nowMs);
  const duration = ledger?.market?.roundDurationSec ?? DEFAULT_ROUND_DURATION_SECONDS;
  const started = ledger?.market?.roundStartedAtSec ?? currentSeconds;
  const elapsed = Math.max(0, currentSeconds - started);
  const remainder = elapsed % duration;
  const remaining = duration - remainder;
  return remaining === 0 ? duration : remaining;
}

export function accrueDemoRewards(ledger, nowMs = Date.now()) {
  const currentSeconds = nowSeconds(nowMs);
  const normalized = normalizeDemoLedger(ledger, nowMs);
  const delta = currentSeconds - (normalized.meta.lastAccrualAtSec ?? currentSeconds);

  let next = normalized;

  if (delta > 0) {
    const aprRatePerSecond = (next.staking.apr / 100) / YEAR_SECONDS;
    const accrued = next.account.stakedAmount * aprRatePerSecond * delta;

    next = {
      ...next,
      account: {
        ...next.account,
        pendingRewards: roundTo(next.account.pendingRewards + accrued),
      },
    };
  }

  const duration = next.market.roundDurationSec;
  const elapsedSinceRoundStart = Math.max(0, currentSeconds - next.market.roundStartedAtSec);
  const roundsPassed = Math.floor(elapsedSinceRoundStart / duration);

  if (roundsPassed > 0) {
    next = {
      ...next,
      market: {
        ...next.market,
        currentRound: next.market.currentRound + roundsPassed,
        roundStartedAtSec: next.market.roundStartedAtSec + roundsPassed * duration,
      },
    };
  }

  return touchMeta(next, currentSeconds);
}

function fail(code, error, ledger) {
  return { ok: false, code, error, ledger };
}

function success(ledger, payload = {}) {
  return { ok: true, ledger, ...payload };
}

export function placeDemoOrder(ledger, { side, quantity, price, nowMs = Date.now() }) {
  const nextSide = side === 'buy' || side === 'sell' ? side : null;
  if (!nextSide) {
    return fail('INVALID_SIDE', 'Order side must be buy or sell.', ledger);
  }

  const parsedQuantity = toPositiveNumber(quantity);
  if (!parsedQuantity) {
    return fail('INVALID_QUANTITY', 'Quantity must be greater than zero.', ledger);
  }

  const parsedPrice = toPositiveNumber(price);
  if (!parsedPrice) {
    return fail('INVALID_PRICE', 'Price must be greater than zero.', ledger);
  }

  let next = accrueDemoRewards(ledger, nowMs);

  const gross = parsedQuantity * parsedPrice;
  const fee = gross * next.market.feeRate;
  const burnFee = fee * 0.3;
  const stakerFee = fee * 0.7;

  let tokenDelta = 0;

  if (nextSide === 'buy') {
    const required = gross + fee;
    if (required > next.account.tokenBalance + 1e-9) {
      return fail('INSUFFICIENT_BALANCE', 'Not enough SHAKTI balance for this buy order.', next);
    }

    tokenDelta = -required;
    next = {
      ...next,
      account: {
        ...next.account,
        tokenBalance: roundTo(next.account.tokenBalance - required),
        energyInventory: roundTo(next.account.energyInventory + parsedQuantity),
        totalFeesPaid: roundTo(next.account.totalFeesPaid + fee),
      },
    };
  } else {
    if (parsedQuantity > next.account.energyInventory + 1e-9) {
      return fail('INSUFFICIENT_INVENTORY', 'Not enough energy inventory for this sell order.', next);
    }

    const proceeds = gross - fee;
    tokenDelta = proceeds;
    next = {
      ...next,
      account: {
        ...next.account,
        tokenBalance: roundTo(next.account.tokenBalance + proceeds),
        energyInventory: roundTo(next.account.energyInventory - parsedQuantity),
        totalFeesPaid: roundTo(next.account.totalFeesPaid + fee),
      },
    };
  }

  // Distribute staker-fee share to pending rewards based on user stake fraction.
  const stakeShare = next.staking.totalStaked > 0 ? next.account.stakedAmount / next.staking.totalStaked : 0;
  if (stakeShare > 0) {
    next = {
      ...next,
      account: {
        ...next.account,
        pendingRewards: roundTo(next.account.pendingRewards + stakerFee * stakeShare),
      },
    };
  }

  const order = {
    id: `demo-order-${next.market.currentRound}-${next.market.nextOrderId}`,
    round: next.market.currentRound,
    side: nextSide,
    status: 'filled',
    quantity: roundTo(parsedQuantity, 4),
    price: roundTo(parsedPrice, 4),
    gross: roundTo(gross, 4),
    fee: roundTo(fee, 4),
    burnFee: roundTo(burnFee, 4),
    stakerFee: roundTo(stakerFee, 4),
    tokenDelta: roundTo(tokenDelta, 4),
    createdAt: new Date(nowSeconds(nowMs) * 1000).toISOString(),
  };

  next = {
    ...next,
    market: {
      ...next.market,
      feeBurned: roundTo(next.market.feeBurned + burnFee),
      feeToStakers: roundTo(next.market.feeToStakers + stakerFee),
      totalVolumeKwh: roundTo(next.market.totalVolumeKwh + parsedQuantity, 4),
      totalTrades: next.market.totalTrades + 1,
      nextOrderId: next.market.nextOrderId + 1,
    },
    recentOrders: [order, ...next.recentOrders].slice(0, MAX_RECENT_ORDERS),
  };

  next = appendAction(
    next,
    buildAction(nextSide, {
      quantity: order.quantity,
      price: order.price,
      tokenDelta: order.tokenDelta,
      fee: order.fee,
      orderId: order.id,
    }, nowSeconds(nowMs))
  );

  return success(next, { order });
}

export function stakeDemoTokens(ledger, amount, nowMs = Date.now()) {
  const parsed = toPositiveNumber(amount);
  if (!parsed) {
    return fail('INVALID_STAKE_AMOUNT', 'Stake amount must be greater than zero.', ledger);
  }

  let next = accrueDemoRewards(ledger, nowMs);

  if (parsed > next.account.tokenBalance + 1e-9) {
    return fail('INSUFFICIENT_BALANCE', 'Not enough SHAKTI to stake this amount.', next);
  }

  next = {
    ...next,
    account: {
      ...next.account,
      tokenBalance: roundTo(next.account.tokenBalance - parsed),
      stakedAmount: roundTo(next.account.stakedAmount + parsed),
    },
    staking: {
      ...next.staking,
      totalStaked: roundTo(next.staking.totalStaked + parsed),
    },
  };

  next = appendAction(
    next,
    buildAction('stake', { amount: roundTo(parsed, 4) }, nowSeconds(nowMs))
  );

  return success(next);
}

export function unstakeDemoTokens(ledger, amount, nowMs = Date.now()) {
  const parsed = toPositiveNumber(amount);
  if (!parsed) {
    return fail('INVALID_UNSTAKE_AMOUNT', 'Unstake amount must be greater than zero.', ledger);
  }

  let next = accrueDemoRewards(ledger, nowMs);

  if (parsed > next.account.stakedAmount + 1e-9) {
    return fail('INSUFFICIENT_STAKED', 'Cannot unstake more than currently staked amount.', next);
  }

  next = {
    ...next,
    account: {
      ...next.account,
      tokenBalance: roundTo(next.account.tokenBalance + parsed),
      stakedAmount: roundTo(next.account.stakedAmount - parsed),
    },
    staking: {
      ...next.staking,
      totalStaked: roundTo(Math.max(0, next.staking.totalStaked - parsed)),
    },
  };

  next = appendAction(
    next,
    buildAction('unstake', { amount: roundTo(parsed, 4) }, nowSeconds(nowMs))
  );

  return success(next);
}

export function claimDemoRewards(ledger, nowMs = Date.now()) {
  let next = accrueDemoRewards(ledger, nowMs);
  const pending = next.account.pendingRewards;

  if (pending <= 1e-9) {
    return fail('NO_REWARDS', 'No staking rewards available to claim.', next);
  }

  next = {
    ...next,
    account: {
      ...next.account,
      tokenBalance: roundTo(next.account.tokenBalance + pending),
      pendingRewards: 0,
      totalClaimedRewards: roundTo(next.account.totalClaimedRewards + pending),
    },
  };

  next = appendAction(
    next,
    buildAction('claim', { amount: roundTo(pending, 4) }, nowSeconds(nowMs))
  );

  return success(next, { claimed: roundTo(pending, 4) });
}

export function addDemoVehicle(ledger, nowMs = Date.now()) {
  const next = normalizeDemoLedger(ledger, nowMs);
  if (next.vehicles.length >= MAX_VEHICLES) {
    return fail('VEHICLE_LIMIT', 'Maximum 20 vehicles.', next);
  }
  const vehicle = {
    id: `veh-${Date.now()}-${next.vehicles.length + 1}`,
    name: `Vehicle ${next.vehicles.length + 1}`,
    city: 'Delhi',
    capacityKwh: 60,
    soc: 0.5,
  };
  return success({
    ...next,
    vehicles: [...next.vehicles, vehicle],
  }, { vehicle });
}

export function removeDemoVehicle(ledger, vehicleId, nowMs = Date.now()) {
  const next = normalizeDemoLedger(ledger, nowMs);
  if (next.vehicles.length <= MIN_VEHICLES) {
    return fail('VEHICLE_MIN', 'Keep at least one vehicle.', next);
  }
  return success({
    ...next,
    vehicles: next.vehicles.filter((row) => row.id !== vehicleId),
  });
}

export function updateDemoVehicle(ledger, vehicleId, patch, nowMs = Date.now()) {
  const next = normalizeDemoLedger(ledger, nowMs);
  return success({
    ...next,
    vehicles: next.vehicles.map((row) => (row.id === vehicleId ? { ...row, ...patch } : row)),
  });
}

export function setDemoPortfolio(ledger, portfolio, nowMs = Date.now()) {
  const next = normalizeDemoLedger(ledger, nowMs);
  return success({
    ...next,
    portfolio: {
      residential: Number(portfolio.residential) || 0,
      commercial: Number(portfolio.commercial) || 0,
      fleet: Number(portfolio.fleet) || 0,
    },
  });
}

export function placeBulkDemoAsks(ledger, { quantity, price, count, nowMs = Date.now() }) {
  const n = Math.max(1, Number(count) || 1);
  const parsedQuantity = toPositiveNumber(quantity);
  const parsedPrice = toPositiveNumber(price);
  if (!parsedQuantity || !parsedPrice) {
    return fail('INVALID_ORDER', 'Quantity and price must be greater than zero.', ledger);
  }
  let next = accrueDemoRewards(ledger, nowMs);
  if (parsedQuantity * n > next.account.energyInventory + 1e-9) {
    return fail('INSUFFICIENT_INVENTORY', 'Not enough energy inventory for this bulk bid.', next);
  }
  for (let i = 0; i < n; i += 1) {
    const result = placeDemoOrder(next, {
      side: 'sell',
      quantity: parsedQuantity,
      price: parsedPrice,
      nowMs,
    });
    if (!result.ok) {
      return result;
    }
    next = result.ledger;
  }
  next = appendAction(
    next,
    buildAction(
      'bulk_ask',
      { vehicleCount: n, quantity: parsedQuantity, price: parsedPrice },
      nowSeconds(nowMs)
    )
  );
  return success(next, { vehicleCount: n });
}

export function resetDemoLedger(nowMs = Date.now()) {
  return createInitialDemoLedger(nowMs);
}
