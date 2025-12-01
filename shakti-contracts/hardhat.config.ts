import { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-ethers";
import "@nomicfoundation/hardhat-chai-matchers";
import "@nomicfoundation/hardhat-verify";
import "@openzeppelin/hardhat-upgrades";
import "@typechain/hardhat";
import "hardhat-gas-reporter";
import "solidity-coverage";
import * as dotenv from "dotenv";

dotenv.config();

const PRIVATE_KEY = process.env.PRIVATE_KEY || "0x0000000000000000000000000000000000000000000000000000000000000001";
const ETHERSCAN_API_KEY = process.env.ETHERSCAN_API_KEY || "";  // Etherscan V2 API (works for Polygon)
const POLYGONSCAN_API_KEY = process.env.POLYGONSCAN_API_KEY || ETHERSCAN_API_KEY;  // Fallback to Etherscan
const COINMARKETCAP_API_KEY = process.env.COINMARKETCAP_API_KEY || "";
const ALCHEMY_API_KEY = process.env.ALCHEMY_API_KEY || "";
const INFURA_API_KEY = process.env.INFURA_API_KEY || "";

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      viaIR: true,
      evmVersion: "cancun",
    },
  },
  networks: {
    hardhat: {
      chainId: 31337,
      allowUnlimitedContractSize: false,
    },
    localhost: {
      url: "http://127.0.0.1:8545",
      chainId: 31337,
    },
    // Polygon Mumbai Testnet (deprecated, use Amoy)
    mumbai: {
      url: process.env.POLYGON_MUMBAI_RPC_URL ||
        (ALCHEMY_API_KEY ? `https://polygon-mumbai.g.alchemy.com/v2/${ALCHEMY_API_KEY}` : "https://rpc-mumbai.maticvigil.com"),
      chainId: 80001,
      accounts: [PRIVATE_KEY],
      gasPrice: "auto",
    },
    // Polygon Amoy Testnet (new testnet replacing Mumbai)
    amoy: {
      url: process.env.POLYGON_AMOY_RPC_URL && !process.env.POLYGON_AMOY_RPC_URL.includes("your_key")
        ? process.env.POLYGON_AMOY_RPC_URL
        : (ALCHEMY_API_KEY && ALCHEMY_API_KEY.length > 25
            ? `https://polygon-amoy.g.alchemy.com/v2/${ALCHEMY_API_KEY}`
            : "https://polygon-amoy-bor-rpc.publicnode.com"),
      chainId: 80002,
      accounts: [PRIVATE_KEY],
      gasPrice: "auto",
    },
    // Polygon Mainnet
    polygon: {
      url: process.env.POLYGON_MAINNET_RPC_URL ||
        (ALCHEMY_API_KEY ? `https://polygon-mainnet.g.alchemy.com/v2/${ALCHEMY_API_KEY}` : "https://polygon-rpc.com"),
      chainId: 137,
      accounts: [PRIVATE_KEY],
      gasPrice: "auto",
    },
    // Alias for backward compatibility
    polygonMumbai: {
      url: process.env.POLYGON_MUMBAI_RPC_URL || "https://rpc-mumbai.maticvigil.com",
      chainId: 80001,
      accounts: [PRIVATE_KEY],
      gasPrice: "auto",
    },
    polygonMainnet: {
      url: process.env.POLYGON_MAINNET_RPC_URL || "https://polygon-rpc.com",
      chainId: 137,
      accounts: [PRIVATE_KEY],
      gasPrice: "auto",
    },
  },
  etherscan: {
    apiKey: {
      // Etherscan V2 API - use ETHERSCAN_API_KEY for all networks
      // Get your API key at: https://etherscan.io/myapikey
      polygon: ETHERSCAN_API_KEY || POLYGONSCAN_API_KEY,
      polygonAmoy: ETHERSCAN_API_KEY || POLYGONSCAN_API_KEY,
      // Legacy keys (if you still have old Polygonscan keys)
      polygonMumbai: POLYGONSCAN_API_KEY,
    },
    customChains: [
      {
        network: "polygonAmoy",
        chainId: 80002,
        urls: {
          // Etherscan V2 API endpoints for Polygon Amoy
          apiURL: "https://api-amoy.polygonscan.com/api",
          browserURL: "https://amoy.polygonscan.com",
        },
      },
      {
        network: "polygon",
        chainId: 137,
        urls: {
          apiURL: "https://api.polygonscan.com/api",
          browserURL: "https://polygonscan.com",
        },
      },
    ],
  },
  gasReporter: {
    enabled: process.env.REPORT_GAS === "true",
    currency: "USD",
    coinmarketcap: COINMARKETCAP_API_KEY,
    token: "MATIC",
    gasPriceApi: "https://api.polygonscan.com/api?module=proxy&action=eth_gasPrice",
    outputFile: "gas-report.txt",
    noColors: true,
  },
  typechain: {
    outDir: "typechain-types",
    target: "ethers-v6",
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
  mocha: {
    timeout: 60000,
  },
};

export default config;
