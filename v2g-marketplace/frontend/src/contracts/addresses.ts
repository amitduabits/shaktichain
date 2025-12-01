import { CHAIN_IDS, type SupportedChainId } from '../config/wagmi';

// Contract addresses per network
export const CONTRACT_ADDRESSES = {
  [CHAIN_IDS.POLYGON]: {
    ShaktiToken: '0x0000000000000000000000000000000000000000' as const,
    EnergyAuction: '0x0000000000000000000000000000000000000000' as const,
    EnergyEscrow: '0x0000000000000000000000000000000000000000' as const,
    StakingPool: '0x0000000000000000000000000000000000000000' as const,
    ReputationSystem: '0x0000000000000000000000000000000000000000' as const,
    EnergyRegistry: '0x0000000000000000000000000000000000000000' as const,
    Treasury: '0x0000000000000000000000000000000000000000' as const,
    Governance: '0x0000000000000000000000000000000000000000' as const,
  },
  [CHAIN_IDS.POLYGON_AMOY]: {
    ShaktiToken: '0x0000000000000000000000000000000000000000' as const,
    EnergyAuction: '0x0000000000000000000000000000000000000000' as const,
    EnergyEscrow: '0x0000000000000000000000000000000000000000' as const,
    StakingPool: '0x0000000000000000000000000000000000000000' as const,
    ReputationSystem: '0x0000000000000000000000000000000000000000' as const,
    EnergyRegistry: '0x0000000000000000000000000000000000000000' as const,
    Treasury: '0x0000000000000000000000000000000000000000' as const,
    Governance: '0x0000000000000000000000000000000000000000' as const,
  },
  [CHAIN_IDS.HARDHAT]: {
    ShaktiToken: '0x5FbDB2315678afecb367f032d93F642f64180aa3' as const,
    EnergyAuction: '0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512' as const,
    EnergyEscrow: '0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0' as const,
    StakingPool: '0xCf7Ed3AccA5a467e9e704C703E8D87F634fB0Fc9' as const,
    ReputationSystem: '0xDc64a140Aa3E981100a9becA4E685f962f0cF6C9' as const,
    EnergyRegistry: '0x5FC8d32690cc91D4c39d9d3abcBD16989F875707' as const,
    Treasury: '0x0165878A594ca255338adfa4d48449f69242Eb8F' as const,
    Governance: '0xa513E6E4b8f2a923D98304ec87F64353C4D5C853' as const,
  },
} as const;

// Contract names type
export type ContractName = keyof typeof CONTRACT_ADDRESSES[typeof CHAIN_IDS.POLYGON];

// Get address for a specific contract on a specific chain
export function getContractAddress(
  contractName: ContractName,
  chainId: SupportedChainId
): `0x${string}` {
  const chainAddresses = CONTRACT_ADDRESSES[chainId];
  if (!chainAddresses) {
    throw new Error(`Chain ${chainId} is not supported`);
  }

  const address = chainAddresses[contractName];
  if (!address || address === '0x0000000000000000000000000000000000000000') {
    throw new Error(`Contract ${contractName} is not deployed on chain ${chainId}`);
  }

  return address;
}

// Check if a contract is deployed on a chain
export function isContractDeployed(
  contractName: ContractName,
  chainId: SupportedChainId
): boolean {
  try {
    const address = getContractAddress(contractName, chainId);
    return address !== '0x0000000000000000000000000000000000000000';
  } catch {
    return false;
  }
}

// Get all contracts for a chain
export function getChainContracts(chainId: SupportedChainId) {
  return CONTRACT_ADDRESSES[chainId] || null;
}
