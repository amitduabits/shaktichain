/**
 * SHAKTI-CHAIN Monitoring Setup Script
 *
 * Generates configuration for monitoring services:
 * - Tenderly alerts
 * - Discord webhooks
 * - Dune Analytics queries
 *
 * Usage: npx hardhat run scripts/monitoring/setup-monitoring.ts --network polygon
 */

import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";
import { loadDeployment } from "../utils/deployment-helpers";

interface AlertConfig {
  name: string;
  description: string;
  severity: "critical" | "high" | "medium" | "low";
  contract: string;
  event?: string;
  condition?: string;
  threshold?: string;
  channels: string[];
}

interface MonitoringConfig {
  network: string;
  chainId: number;
  contracts: Record<string, string>;
  alerts: AlertConfig[];
  webhooks: {
    discord: string;
    pagerduty: string;
    slack: string;
  };
}

const ALERT_DEFINITIONS: AlertConfig[] = [
  // Critical Alerts
  {
    name: "Contract Paused",
    description: "A contract has been paused",
    severity: "critical",
    contract: "ALL",
    event: "Paused(address)",
    channels: ["pagerduty", "discord", "sms"],
  },
  {
    name: "Large Token Transfer",
    description: "Large SHAKTI token transfer detected",
    severity: "high",
    contract: "ShaktiToken",
    event: "Transfer(address,address,uint256)",
    condition: "amount > 1000000e18",
    threshold: "1,000,000 SHAKTI",
    channels: ["pagerduty", "discord"],
  },
  {
    name: "Large Trade",
    description: "Large energy trade executed",
    severity: "medium",
    contract: "EnergyAuction",
    event: "OrderMatched",
    condition: "value > 1000e18",
    threshold: "1,000 SHAKTI",
    channels: ["discord"],
  },

  // High Alerts
  {
    name: "Failed Settlement",
    description: "Escrow settlement failed",
    severity: "high",
    contract: "EnergyEscrow",
    event: "SettlementFailed",
    channels: ["pagerduty", "discord"],
  },
  {
    name: "Oracle Stale",
    description: "Price oracle data is stale",
    severity: "high",
    contract: "PriceOracle",
    condition: "lastUpdate > 3600",
    threshold: "1 hour",
    channels: ["pagerduty", "discord"],
  },
  {
    name: "Low Treasury Balance",
    description: "Treasury balance below threshold",
    severity: "high",
    contract: "Treasury",
    condition: "balance < 10000e18",
    threshold: "10,000 SHAKTI",
    channels: ["pagerduty", "discord"],
  },
  {
    name: "Delivery Failed",
    description: "Energy delivery verification failed",
    severity: "high",
    contract: "EnergyVerification",
    event: "DeliveryFailed",
    channels: ["discord"],
  },

  // Medium Alerts
  {
    name: "New Prosumer Registered",
    description: "New prosumer registered on the platform",
    severity: "low",
    contract: "EnergyRegistry",
    event: "ProsumerRegistered",
    channels: ["discord"],
  },
  {
    name: "Governance Proposal Created",
    description: "New governance proposal submitted",
    severity: "medium",
    contract: "ShaktiGovernor",
    event: "ProposalCreated",
    channels: ["discord"],
  },
  {
    name: "Large Stake",
    description: "Large staking deposit",
    severity: "medium",
    contract: "StakingPool",
    event: "Staked",
    condition: "amount > 100000e18",
    threshold: "100,000 SHAKTI",
    channels: ["discord"],
  },
  {
    name: "User Slashed",
    description: "User slashed for violation",
    severity: "medium",
    contract: "EnergyVerification",
    event: "SlashApplied",
    channels: ["discord"],
  },

  // Low Alerts
  {
    name: "Auction Round Started",
    description: "New auction round started",
    severity: "low",
    contract: "EnergyAuction",
    event: "AuctionRoundStarted",
    channels: ["discord"],
  },
  {
    name: "Reputation Updated",
    description: "Significant reputation change",
    severity: "low",
    contract: "ReputationSystem",
    event: "ReputationUpdated",
    condition: "change > 50",
    channels: ["discord"],
  },
];

async function loadAllDeployments(): Promise<Record<string, string>> {
  const contracts: Record<string, string> = {};
  const contractNames = [
    "ShaktiToken",
    "StakingPool",
    "EnergyRegistry",
    "PriceOracle",
    "DynamicPricing",
    "EnergyAuction",
    "EnergyEscrow",
    "Treasury",
    "ReputationSystem",
    "EnergyVerification",
    "TimelockController",
    "ShaktiGovernor",
  ];

  for (const name of contractNames) {
    const deployment = await loadDeployment(name);
    if (deployment) {
      contracts[name] = deployment.address;
    }
  }

  return contracts;
}

function generateTenderlyConfig(config: MonitoringConfig): object {
  const alertRules = config.alerts.map((alert) => ({
    name: alert.name,
    description: alert.description,
    type: alert.event ? "event" : "state_change",
    network: config.chainId,
    addresses:
      alert.contract === "ALL"
        ? Object.values(config.contracts)
        : [config.contracts[alert.contract]],
    event_signature: alert.event,
    condition: alert.condition,
    severity: alert.severity,
    destinations: alert.channels.map((channel) => ({
      type: channel === "pagerduty" ? "pagerduty" : "webhook",
      url: config.webhooks[channel as keyof typeof config.webhooks],
    })),
  }));

  return {
    version: "1.0.0",
    project_slug: "shakti-chain",
    alerts: alertRules,
    contracts: Object.entries(config.contracts).map(([name, address]) => ({
      name,
      address,
      network: config.chainId,
    })),
  };
}

function generateDiscordWebhookPayload(alert: AlertConfig): object {
  const colorMap = {
    critical: 0xff0000, // Red
    high: 0xff6600, // Orange
    medium: 0xffcc00, // Yellow
    low: 0x00cc00, // Green
  };

  return {
    embeds: [
      {
        title: `SHAKTI-CHAIN Alert: ${alert.name}`,
        description: alert.description,
        color: colorMap[alert.severity],
        fields: [
          { name: "Severity", value: alert.severity.toUpperCase(), inline: true },
          { name: "Contract", value: alert.contract, inline: true },
          { name: "Event", value: alert.event || "State Change", inline: true },
          ...(alert.threshold
            ? [{ name: "Threshold", value: alert.threshold, inline: true }]
            : []),
        ],
        timestamp: new Date().toISOString(),
        footer: { text: "SHAKTI-CHAIN Monitoring" },
      },
    ],
  };
}

function generateDuneQueries(contracts: Record<string, string>): string[] {
  const chainId = network.config.chainId || 137;

  return [
    // Total Value Locked
    `-- SHAKTI-CHAIN TVL
SELECT
  date_trunc('day', block_time) AS date,
  SUM(value) / 1e18 AS tvl_shakti
FROM polygon.transactions
WHERE to = '${contracts.StakingPool}'
  AND success = true
GROUP BY 1
ORDER BY 1 DESC`,

    // Daily Active Users
    `-- Daily Active Users
SELECT
  date_trunc('day', block_time) AS date,
  COUNT(DISTINCT "from") AS unique_users
FROM polygon.transactions
WHERE to IN (${Object.values(contracts)
      .map((a) => `'${a}'`)
      .join(", ")})
  AND success = true
GROUP BY 1
ORDER BY 1 DESC`,

    // Trade Volume
    `-- Daily Trade Volume
SELECT
  date_trunc('day', block_time) AS date,
  COUNT(*) AS trade_count,
  SUM(CAST(data AS NUMERIC)) / 1e18 AS volume_kwh
FROM polygon.logs
WHERE contract_address = '${contracts.EnergyAuction}'
  AND topic0 = '0x...' -- OrderMatched event signature
GROUP BY 1
ORDER BY 1 DESC`,

    // Token Distribution
    `-- Token Holder Distribution
SELECT
  CASE
    WHEN balance >= 1000000e18 THEN 'Whale (>1M)'
    WHEN balance >= 100000e18 THEN 'Large (100K-1M)'
    WHEN balance >= 10000e18 THEN 'Medium (10K-100K)'
    WHEN balance >= 1000e18 THEN 'Small (1K-10K)'
    ELSE 'Micro (<1K)'
  END AS tier,
  COUNT(*) AS holders,
  SUM(balance) / 1e18 AS total_balance
FROM (
  SELECT address, balance
  FROM erc20_polygon.balances
  WHERE token_address = '${contracts.ShaktiToken}'
    AND balance > 0
) balances
GROUP BY 1
ORDER BY total_balance DESC`,

    // Staking Statistics
    `-- Staking Pool Statistics
SELECT
  date_trunc('day', block_time) AS date,
  SUM(CASE WHEN topic0 = '0x...' THEN value ELSE 0 END) / 1e18 AS staked,
  SUM(CASE WHEN topic0 = '0x...' THEN value ELSE 0 END) / 1e18 AS unstaked
FROM polygon.logs
WHERE contract_address = '${contracts.StakingPool}'
GROUP BY 1
ORDER BY 1 DESC`,
  ];
}

function generateGrafanaConfig(contracts: Record<string, string>): object {
  return {
    dashboard: {
      title: "SHAKTI-CHAIN Monitoring",
      panels: [
        {
          title: "Total Value Locked",
          type: "stat",
          query: `sum(shakti_staking_pool_tvl{network="${network.name}"})`,
        },
        {
          title: "Active Prosumers",
          type: "stat",
          query: `shakti_registry_prosumer_count{network="${network.name}"}`,
        },
        {
          title: "24h Trade Volume",
          type: "stat",
          query: `sum(increase(shakti_auction_volume_total{network="${network.name}"}[24h]))`,
        },
        {
          title: "Contract Pause Status",
          type: "table",
          query: `shakti_contract_paused{network="${network.name}"}`,
        },
        {
          title: "Gas Usage",
          type: "graph",
          query: `rate(shakti_gas_used_total{network="${network.name}"}[5m])`,
        },
        {
          title: "Error Rate",
          type: "graph",
          query: `rate(shakti_transaction_errors_total{network="${network.name}"}[5m])`,
        },
      ],
    },
  };
}

async function main() {
  console.log("╔════════════════════════════════════════════════════════════╗");
  console.log("║          SHAKTI-CHAIN Monitoring Setup                     ║");
  console.log("╚════════════════════════════════════════════════════════════╝\n");

  console.log("Network:", network.name);
  console.log("Chain ID:", network.config.chainId);
  console.log("");

  // Load deployments
  console.log("Loading deployed contracts...");
  const contracts = await loadAllDeployments();

  if (Object.keys(contracts).length === 0) {
    console.log("No contracts found. Deploy contracts first.");
    return;
  }

  console.log(`Found ${Object.keys(contracts).length} contracts\n`);

  // Create config
  const config: MonitoringConfig = {
    network: network.name,
    chainId: network.config.chainId || 0,
    contracts,
    alerts: ALERT_DEFINITIONS,
    webhooks: {
      discord: process.env.DISCORD_WEBHOOK_URL || "YOUR_DISCORD_WEBHOOK_URL",
      pagerduty: process.env.PAGERDUTY_URL || "YOUR_PAGERDUTY_URL",
      slack: process.env.SLACK_WEBHOOK_URL || "YOUR_SLACK_WEBHOOK_URL",
    },
  };

  // Create output directory
  const outputDir = path.join(__dirname, "../../monitoring-config");
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Generate Tenderly config
  console.log("Generating Tenderly configuration...");
  const tenderlyConfig = generateTenderlyConfig(config);
  fs.writeFileSync(
    path.join(outputDir, "tenderly-alerts.json"),
    JSON.stringify(tenderlyConfig, null, 2)
  );
  console.log("  ✓ tenderly-alerts.json");

  // Generate Discord webhook templates
  console.log("\nGenerating Discord webhook templates...");
  const discordTemplates = config.alerts.map((alert) => ({
    alert: alert.name,
    payload: generateDiscordWebhookPayload(alert),
  }));
  fs.writeFileSync(
    path.join(outputDir, "discord-templates.json"),
    JSON.stringify(discordTemplates, null, 2)
  );
  console.log("  ✓ discord-templates.json");

  // Generate Dune Analytics queries
  console.log("\nGenerating Dune Analytics queries...");
  const duneQueries = generateDuneQueries(contracts);
  fs.writeFileSync(
    path.join(outputDir, "dune-queries.sql"),
    duneQueries.join("\n\n---\n\n")
  );
  console.log("  ✓ dune-queries.sql");

  // Generate Grafana config
  console.log("\nGenerating Grafana dashboard config...");
  const grafanaConfig = generateGrafanaConfig(contracts);
  fs.writeFileSync(
    path.join(outputDir, "grafana-dashboard.json"),
    JSON.stringify(grafanaConfig, null, 2)
  );
  console.log("  ✓ grafana-dashboard.json");

  // Generate contract addresses file
  console.log("\nGenerating contract addresses...");
  fs.writeFileSync(
    path.join(outputDir, "contract-addresses.json"),
    JSON.stringify(
      {
        network: network.name,
        chainId: network.config.chainId,
        contracts,
        generated: new Date().toISOString(),
      },
      null,
      2
    )
  );
  console.log("  ✓ contract-addresses.json");

  // Print summary
  console.log(`
╔════════════════════════════════════════════════════════════╗
║                  Setup Complete!                            ║
╚════════════════════════════════════════════════════════════╝

Files generated in: ${outputDir}

Next steps:

1. Tenderly Setup:
   - Go to https://dashboard.tenderly.co
   - Create project "shakti-chain"
   - Import contracts from contract-addresses.json
   - Configure alerts from tenderly-alerts.json

2. Discord Setup:
   - Create webhook in your Discord server
   - Update DISCORD_WEBHOOK_URL in .env
   - Test with: curl -X POST <webhook_url> -H "Content-Type: application/json" -d @discord-templates.json

3. PagerDuty Setup:
   - Create service "SHAKTI-CHAIN"
   - Add Events API v2 integration
   - Update PAGERDUTY_URL in .env

4. Dune Analytics:
   - Go to https://dune.com
   - Create new queries from dune-queries.sql
   - Build dashboard with visualizations

5. Grafana (Optional):
   - Import grafana-dashboard.json
   - Configure Prometheus/data source

Alert Summary:
  Critical: ${config.alerts.filter((a) => a.severity === "critical").length}
  High:     ${config.alerts.filter((a) => a.severity === "high").length}
  Medium:   ${config.alerts.filter((a) => a.severity === "medium").length}
  Low:      ${config.alerts.filter((a) => a.severity === "low").length}
`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
