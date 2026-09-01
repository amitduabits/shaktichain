import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { WagmiProvider } from 'wagmi';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { RainbowKitProvider, darkTheme, lightTheme } from '@rainbow-me/rainbowkit';
import { config, getDefaultChain } from '../config/wagmi';

import '@rainbow-me/rainbowkit/styles.css';

function parseEnvBoolean(value: unknown, defaultValue = false): boolean {
  if (typeof value !== 'string') {
    return defaultValue;
  }
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return defaultValue;
  }
  return ['1', 'true', 'yes', 'on'].includes(normalized);
}

const DEMO_ONLY_ENV = parseEnvBoolean(import.meta.env.VITE_DEMO_ONLY, import.meta.env.DEV);
const LIVE_MODE_ENV = parseEnvBoolean(import.meta.env.VITE_ENABLE_LIVE_MODE, !DEMO_ONLY_ENV);
const DEMO_ONLY_MODE = DEMO_ONLY_ENV || !LIVE_MODE_ENV;

// Query client for TanStack Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      gcTime: 1000 * 60 * 5, // 5 minutes (formerly cacheTime)
      retry: 3,
      refetchOnWindowFocus: false,
    },
  },
});

// Mode context for switching between simulation and live blockchain
type AppMode = 'simulation' | 'live';

interface ModeContextType {
  mode: AppMode;
  setMode: (mode: AppMode) => void;
  isLiveMode: boolean;
  isSimulationMode: boolean;
  demoOnly: boolean;
  canUseLiveMode: boolean;
  toggleMode: () => void;
}

const ModeContext = createContext<ModeContextType | undefined>(undefined);

export function useAppMode() {
  const context = useContext(ModeContext);
  if (!context) {
    throw new Error('useAppMode must be used within a Web3Provider');
  }
  return context;
}

export function useOptionalAppMode(): ModeContextType {
  const context = useContext(ModeContext);
  return context ?? {
    mode: 'simulation',
    setMode: () => {},
    isLiveMode: false,
    isSimulationMode: true,
    demoOnly: true,
    canUseLiveMode: false,
    toggleMode: () => {},
  };
}

// Transaction status context for global transaction tracking
export type TransactionStatus = 'idle' | 'pending' | 'confirming' | 'confirmed' | 'failed';

interface Transaction {
  hash: string;
  status: TransactionStatus;
  description: string;
  timestamp: number;
  error?: string;
}

interface TransactionContextType {
  transactions: Transaction[];
  addTransaction: (hash: string, description: string) => void;
  updateTransaction: (hash: string, status: TransactionStatus, error?: string) => void;
  clearTransactions: () => void;
  latestTransaction: Transaction | null;
}

const TransactionContext = createContext<TransactionContextType | undefined>(undefined);

export function useTransactions() {
  const context = useContext(TransactionContext);
  if (!context) {
    throw new Error('useTransactions must be used within a Web3Provider');
  }
  return context;
}

// Props
interface Web3ProviderProps {
  children: ReactNode;
  defaultMode?: AppMode;
  theme?: 'light' | 'dark';
}

export function Web3Provider({
  children,
  defaultMode = 'simulation',
  theme = 'dark'
}: Web3ProviderProps) {
  const resolvedDefaultMode: AppMode = DEMO_ONLY_MODE ? 'simulation' : defaultMode;

  // Mode state
  const [mode, setModeState] = useState<AppMode>(() => {
    if (typeof window === 'undefined') {
      return resolvedDefaultMode;
    }

    try {
      const persistedMode = localStorage.getItem('shakti-app-mode');
      if (persistedMode === 'simulation' || persistedMode === 'live') {
        if (DEMO_ONLY_MODE && persistedMode === 'live') {
          return 'simulation';
        }
        return persistedMode;
      }
    } catch (_error) {
      // Ignore localStorage errors and use defaults.
    }

    return resolvedDefaultMode;
  });
  const [web3Error, setWeb3Error] = useState<string | null>(null);

  useEffect(() => {
    if (DEMO_ONLY_MODE && mode !== 'simulation') {
      setModeState('simulation');
    }
  }, [mode]);

  const setMode = useCallback((newMode: AppMode) => {
    const safeMode = DEMO_ONLY_MODE && newMode === 'live' ? 'simulation' : newMode;
    setModeState(safeMode);
    // Persist preference
    if (typeof window !== 'undefined') {
      localStorage.setItem('shakti-app-mode', safeMode);
    }
  }, []);

  const toggleMode = useCallback(() => {
    if (DEMO_ONLY_MODE) {
      return;
    }
    setMode(mode === 'simulation' ? 'live' : 'simulation');
  }, [mode, setMode]);

  const modeValue: ModeContextType = {
    mode,
    setMode,
    isLiveMode: mode === 'live',
    isSimulationMode: mode === 'simulation',
    demoOnly: DEMO_ONLY_MODE,
    canUseLiveMode: !DEMO_ONLY_MODE,
    toggleMode,
  };

  // Transaction state
  const [transactions, setTransactions] = useState<Transaction[]>([]);

  const addTransaction = useCallback((hash: string, description: string) => {
    const newTx: Transaction = {
      hash,
      status: 'pending',
      description,
      timestamp: Date.now(),
    };
    setTransactions(prev => [newTx, ...prev].slice(0, 10)); // Keep last 10
  }, []);

  const updateTransaction = useCallback((hash: string, status: TransactionStatus, error?: string) => {
    setTransactions(prev =>
      prev.map(tx =>
        tx.hash === hash ? { ...tx, status, error } : tx
      )
    );
  }, []);

  const clearTransactions = useCallback(() => {
    setTransactions([]);
  }, []);

  const latestTransaction = transactions.length > 0 ? transactions[0] : null;

  const transactionValue: TransactionContextType = {
    transactions,
    addTransaction,
    updateTransaction,
    clearTransactions,
    latestTransaction,
  };

  // RainbowKit theme
  const rainbowTheme = theme === 'dark'
    ? darkTheme({
        accentColor: '#10b981', // Emerald green for SHAKTI branding
        accentColorForeground: 'white',
        borderRadius: 'medium',
        fontStack: 'system',
      })
    : lightTheme({
        accentColor: '#10b981',
        accentColorForeground: 'white',
        borderRadius: 'medium',
        fontStack: 'system',
      });

  // Wrap in error boundary to prevent WalletConnect errors from breaking the app
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider
          theme={rainbowTheme}
          initialChain={getDefaultChain()}
          showRecentTransactions={true}
        >
          <ModeContext.Provider value={modeValue}>
            <TransactionContext.Provider value={transactionValue}>
              {web3Error ? (
                <div style={{ padding: '20px', color: '#ff6b6b' }}>
                  <h3>Web3 Connection Warning</h3>
                  <p>{web3Error}</p>
                  <p>The app will continue to work with backend API.</p>
                  <div style={{ marginTop: '20px' }}>{children}</div>
                </div>
              ) : (
                children
              )}
            </TransactionContext.Provider>
          </ModeContext.Provider>
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}

export default Web3Provider;
