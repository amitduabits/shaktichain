import { http, createConfig } from 'wagmi';
import { polygon, polygonAmoy, hardhat } from 'wagmi/chains';
import { getDefaultConfig } from '@rainbow-me/rainbowkit';

// Environment-based configuration
const WALLET_CONNECT_PROJECT_ID = import.meta.env.VITE_WALLET_CONNECT_PROJECT_ID || 'demo-project-id';
const POLYGON_RPC_URL = import.meta.env.VITE_POLYGON_RPC_URL || 'https://polygon-rpc.com';
const POLYGON_AMOY_RPC_URL = import.meta.env.VITE_POLYGON_AMOY_RPC_URL || 'https://rpc-amoy.polygon.technology';

// Define supported chains based on environment
const isDevelopment = import.meta.env.DEV;
const isTestnet = import.meta.env.VITE_USE_TESTNET === 'true';

// Custom chain configs with optimized RPC
const polygonWithCustomRPC = {
  ...polygon,
  rpcUrls: {
    ...polygon.rpcUrls,
    default: { http: [POLYGON_RPC_URL] },
    public: { http: [POLYGON_RPC_URL] },
  },
};

const polygonAmoyWithCustomRPC = {
  ...polygonAmoy,
  rpcUrls: {
    ...polygonAmoy.rpcUrls,
    default: { http: [POLYGON_AMOY_RPC_URL] },
    public: { http: [POLYGON_AMOY_RPC_URL] },
  },
};

// Select chains based on environment
const getChains = () => {
  if (isDevelopment) {
    // Use Polygon Amoy testnet for development (no local Hardhat node needed)
    return [polygonAmoyWithCustomRPC, polygonWithCustomRPC, hardhat] as const;
  }
  if (isTestnet) {
    return [polygonAmoyWithCustomRPC] as const;
  }
  return [polygonWithCustomRPC] as const;
};

const chains = getChains();

// RainbowKit configuration
export const config = getDefaultConfig({
  appName: 'SHAKTI-CHAIN V2G Marketplace',
  projectId: WALLET_CONNECT_PROJECT_ID,
  chains,
  transports: {
    [polygon.id]: http(POLYGON_RPC_URL),
    [polygonAmoy.id]: http(POLYGON_AMOY_RPC_URL),
    [hardhat.id]: http('http://127.0.0.1:8545'),
  },
  ssr: false,
});

// Export chain IDs for easy reference
export const CHAIN_IDS = {
  POLYGON: polygon.id,
  POLYGON_AMOY: polygonAmoy.id,
  HARDHAT: hardhat.id,
} as const;

// Get the default chain based on environment
export const getDefaultChain = () => {
  if (isDevelopment) return polygonAmoy; // Use Polygon Amoy testnet for development
  if (isTestnet) return polygonAmoy;
  return polygon;
};

// Type exports
export type SupportedChainId = typeof CHAIN_IDS[keyof typeof CHAIN_IDS];
