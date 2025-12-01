/**
 * SHAKTI-CHAIN Deployment Helpers
 *
 * Utility functions for deployment scripts.
 */

import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";

const DEPLOYMENTS_DIR = path.join(__dirname, "..", "..", "deployments");

export interface DeploymentInfo {
  address: string;
  constructorArgs: any[];
  txHash?: string;
  deployer: string;
  network: string;
  chainId?: number;
  timestamp: string;
  verified?: boolean;
}

/**
 * Get the deployer signer
 */
export async function getDeployer() {
  const [deployer] = await ethers.getSigners();
  return deployer;
}

/**
 * Estimate gas with a 20% buffer
 */
export async function estimateGasWithBuffer(tx: any): Promise<bigint> {
  const estimatedGas = await ethers.provider.estimateGas(tx);
  const buffer = estimatedGas * BigInt(20) / BigInt(100);
  return estimatedGas + buffer;
}

/**
 * Get the deployments directory for the current network
 */
function getDeploymentsPath(): string {
  const networkDir = path.join(DEPLOYMENTS_DIR, network.name);
  if (!fs.existsSync(networkDir)) {
    fs.mkdirSync(networkDir, { recursive: true });
  }
  return networkDir;
}

/**
 * Save deployment info to file
 */
export async function saveDeployment(
  contractName: string,
  deployment: DeploymentInfo
): Promise<void> {
  const deploymentsPath = getDeploymentsPath();
  const filePath = path.join(deploymentsPath, `${contractName}.json`);

  fs.writeFileSync(filePath, JSON.stringify(deployment, null, 2));
  console.log(`Deployment saved to: ${filePath}`);

  // Also update the combined deployments file
  await updateCombinedDeployments(contractName, deployment);
}

/**
 * Load deployment info from file
 */
export async function loadDeployment(
  contractName: string
): Promise<DeploymentInfo | null> {
  const deploymentsPath = getDeploymentsPath();
  const filePath = path.join(deploymentsPath, `${contractName}.json`);

  if (!fs.existsSync(filePath)) {
    return null;
  }

  const data = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(data) as DeploymentInfo;
}

/**
 * Load all deployments for current network
 */
export async function loadAllDeployments(): Promise<Record<string, DeploymentInfo>> {
  const deploymentsPath = getDeploymentsPath();
  const combinedPath = path.join(deploymentsPath, "deployments.json");

  if (!fs.existsSync(combinedPath)) {
    return {};
  }

  const data = fs.readFileSync(combinedPath, "utf-8");
  return JSON.parse(data);
}

/**
 * Update combined deployments file
 */
async function updateCombinedDeployments(
  contractName: string,
  deployment: DeploymentInfo
): Promise<void> {
  const deploymentsPath = getDeploymentsPath();
  const combinedPath = path.join(deploymentsPath, "deployments.json");

  let deployments: Record<string, DeploymentInfo> = {};
  if (fs.existsSync(combinedPath)) {
    const data = fs.readFileSync(combinedPath, "utf-8");
    deployments = JSON.parse(data);
  }

  deployments[contractName] = deployment;
  fs.writeFileSync(combinedPath, JSON.stringify(deployments, null, 2));
}

/**
 * Wait for a number of confirmations
 */
export async function waitForConfirmations(
  txHash: string,
  confirmations: number = 5
): Promise<void> {
  console.log(`Waiting for ${confirmations} confirmations...`);
  const receipt = await ethers.provider.waitForTransaction(txHash, confirmations);
  console.log(`Transaction confirmed in block ${receipt?.blockNumber}`);
}

/**
 * Check if a contract is already deployed
 */
export async function isDeployed(contractName: string): Promise<boolean> {
  const deployment = await loadDeployment(contractName);
  if (!deployment) return false;

  // Verify the contract exists at the address
  const code = await ethers.provider.getCode(deployment.address);
  return code !== "0x";
}

/**
 * Get network configuration
 */
export function getNetworkConfig() {
  return {
    name: network.name,
    chainId: network.config.chainId,
    isTestnet: ["mumbai", "amoy", "sepolia", "goerli", "hardhat", "localhost"].includes(network.name),
    isMainnet: ["polygon", "mainnet", "matic"].includes(network.name),
  };
}

/**
 * Format address for display
 */
export function formatAddress(address: string): string {
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
}

/**
 * Sleep for a specified duration
 */
export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Verify contract deployment prerequisites
 */
export async function verifyPrerequisites(
  required: string[]
): Promise<Record<string, DeploymentInfo>> {
  const deployments: Record<string, DeploymentInfo> = {};

  for (const contractName of required) {
    const deployment = await loadDeployment(contractName);
    if (!deployment) {
      throw new Error(`${contractName} not deployed. Deploy it first.`);
    }
    deployments[contractName] = deployment;
  }

  return deployments;
}

/**
 * Print deployment summary
 */
export function printDeploymentSummary(deployments: Record<string, DeploymentInfo>): void {
  console.log("\n========================================");
  console.log("  Deployment Summary");
  console.log("========================================\n");

  for (const [name, info] of Object.entries(deployments)) {
    console.log(`${name}:`);
    console.log(`  Address: ${info.address}`);
    console.log(`  Verified: ${info.verified ? "✅" : "❌"}`);
    console.log("");
  }
}
