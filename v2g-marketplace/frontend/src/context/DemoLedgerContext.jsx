import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from './AuthContext';
import {
  DEMO_LEDGER_SCHEMA_VERSION,
  createInitialDemoLedger,
  isValidDemoLedgerShape,
  normalizeDemoLedger,
  accrueDemoRewards,
  placeDemoOrder,
  stakeDemoTokens,
  unstakeDemoTokens,
  claimDemoRewards,
  resetDemoLedger,
} from '../demo/ledger';

const DemoLedgerContext = createContext(null);

const STORAGE_KEY_PREFIX = `shakti-demo-ledger-v${DEMO_LEDGER_SCHEMA_VERSION}`;
const ACCRUAL_INTERVAL_MS = 1000;

function getStorageKey(userId) {
  if (!userId) {
    return null;
  }
  return `${STORAGE_KEY_PREFIX}:${userId}`;
}

function loadPersistedLedger(storageKey) {
  const fallback = createInitialDemoLedger();
  if (!storageKey) {
    return fallback;
  }

  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) {
      return fallback;
    }

    const parsed = JSON.parse(raw);
    if (!isValidDemoLedgerShape(parsed)) {
      localStorage.removeItem(storageKey);
      return fallback;
    }

    return accrueDemoRewards(normalizeDemoLedger(parsed));
  } catch (_error) {
    localStorage.removeItem(storageKey);
    return fallback;
  }
}

function operationResult(result, fallbackMessage) {
  if (!result || !result.ok) {
    return {
      success: false,
      code: result?.code ?? 'DEMO_OPERATION_FAILED',
      error: result?.error ?? fallbackMessage,
    };
  }

  return {
    success: true,
    ...result,
  };
}

export function DemoLedgerProvider({ children }) {
  const { user } = useAuth();
  const storageKey = useMemo(() => getStorageKey(user?.id), [user?.id]);

  const [ledger, setLedger] = useState(() => createInitialDemoLedger());
  const ledgerRef = useRef(ledger);

  const setLedgerState = useCallback((nextLedger) => {
    const normalized = normalizeDemoLedger(nextLedger);
    ledgerRef.current = normalized;
    setLedger(normalized);
  }, []);

  useEffect(() => {
    ledgerRef.current = ledger;
  }, [ledger]);

  useEffect(() => {
    const timer = setTimeout(() => {
      const nextLedger = loadPersistedLedger(storageKey);
      setLedgerState(nextLedger);
    }, 0);

    return () => clearTimeout(timer);
  }, [storageKey, setLedgerState]);

  useEffect(() => {
    if (!storageKey) {
      return;
    }

    try {
      localStorage.setItem(storageKey, JSON.stringify(ledger));
    } catch (_error) {
      // Ignore quota/storage issues for demo mode.
    }
  }, [ledger, storageKey]);

  const accrueRewards = useCallback(() => {
    const nextLedger = accrueDemoRewards(ledgerRef.current);
    setLedgerState(nextLedger);
    return nextLedger;
  }, [setLedgerState]);

  useEffect(() => {
    if (!user?.id) {
      return undefined;
    }

    const timer = setInterval(() => {
      accrueRewards();
    }, ACCRUAL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [accrueRewards, user?.id]);

  const placeOrder = useCallback(
    (side, quantity, price) => {
      const result = placeDemoOrder(ledgerRef.current, { side, quantity, price });
      if (result?.ledger) {
        setLedgerState(result.ledger);
      }
      return operationResult(result, 'Failed to place demo order.');
    },
    [setLedgerState]
  );

  const stake = useCallback(
    (amount) => {
      const result = stakeDemoTokens(ledgerRef.current, amount);
      if (result?.ledger) {
        setLedgerState(result.ledger);
      }
      return operationResult(result, 'Failed to stake demo tokens.');
    },
    [setLedgerState]
  );

  const unstake = useCallback(
    (amount) => {
      const result = unstakeDemoTokens(ledgerRef.current, amount);
      if (result?.ledger) {
        setLedgerState(result.ledger);
      }
      return operationResult(result, 'Failed to unstake demo tokens.');
    },
    [setLedgerState]
  );

  const claimRewards = useCallback(() => {
    const result = claimDemoRewards(ledgerRef.current);
    if (result?.ledger) {
      setLedgerState(result.ledger);
    }
    return operationResult(result, 'Failed to claim rewards.');
  }, [setLedgerState]);

  const resetDemoState = useCallback(() => {
    const nextLedger = resetDemoLedger();
    setLedgerState(nextLedger);
    return { success: true };
  }, [setLedgerState]);

  const value = useMemo(
    () => ({
      ledger,
      placeOrder,
      stake,
      unstake,
      claimRewards,
      resetDemoState,
      accrueRewards,
    }),
    [accrueRewards, claimRewards, ledger, placeOrder, resetDemoState, stake, unstake]
  );

  return <DemoLedgerContext.Provider value={value}>{children}</DemoLedgerContext.Provider>;
}

export function useDemoLedger() {
  const context = useContext(DemoLedgerContext);
  if (!context) {
    throw new Error('useDemoLedger must be used within a DemoLedgerProvider');
  }
  return context;
}

export default DemoLedgerContext;
