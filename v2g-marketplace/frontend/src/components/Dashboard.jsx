import { useState, useEffect } from 'react';
import PriceChart from './PriceChart';
import SimulationPanel from './SimulationPanel';
import { getCurrentPrice } from '../services/api';
import { useOptionalAppMode } from '../providers/Web3Provider';
import { useDemoLedger } from '../context/DemoLedgerContext';
import { getRoundTimeRemaining } from '../demo/ledger';
import { TokenBalance, StakingPanel, BidForm, DemoActivityPanel, AuctionRoundViewer } from './web3';

function Dashboard() {
  const [currentPrice, setCurrentPrice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { isLiveMode, isSimulationMode } = useOptionalAppMode();
  const { ledger } = useDemoLedger();

  useEffect(() => {
    const fetchPrice = async () => {
      try {
        const data = await getCurrentPrice();
        setCurrentPrice(data);
        setLoading(false);
      } catch (_error) {
        setError('Failed to fetch current price');
        setLoading(false);
      }
    };

    fetchPrice();
    const interval = setInterval(fetchPrice, 30000);

    return () => clearInterval(interval);
  }, []);

  const demoRound = ledger?.market?.currentRound ?? 1;
  const demoRoundRemaining = getRoundTimeRemaining(ledger);
  const demoStakedAmount = String(ledger?.account?.stakedAmount ?? 0);
  const demoPendingRewards = String(ledger?.account?.pendingRewards ?? 0);
  const demoApr = Number(ledger?.staking?.apr ?? 0);
  const demoTotalStaked = String(ledger?.staking?.totalStaked ?? 0);
  const totalTrades = Number(ledger?.market?.totalTrades ?? 0);
  const totalVolume = Number(ledger?.market?.totalVolumeKwh ?? 0);

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>Energy Market Overview</h2>
        <p data-testid="sim-disclaimer" className="sim-disclaimer">
          Simulation. Not connected to a live DISCOM.
        </p>
        {loading ? (
          <span className="price-badge loading">Loading...</span>
        ) : error ? (
          <span className="price-badge error">Error</span>
        ) : (
          <span className="price-badge">
            Current Price: INR {currentPrice?.price ?? 'N/A'}/kWh
          </span>
        )}
      </div>

      <div className="dashboard-grid">
        <div className="dashboard-card">
          <h3>Price History</h3>
          <PriceChart />
        </div>

        <div className="dashboard-card">
          <h3>Run Simulation</h3>
          <SimulationPanel />
        </div>

        <div className="dashboard-card">
          <h3>Your Balance</h3>
          <TokenBalance
            variant="detailed"
            showVotingPower
            showTotalSupply
          />
        </div>

        <div className="dashboard-card wide">
          <BidForm
            simulatedData={{
              currentRound: demoRound,
              timeRemaining: demoRoundRemaining,
              isOpen: true,
            }}
          />
        </div>

        <div className="dashboard-card wide">
          <StakingPanel
            simulatedData={{
              stakedAmount: demoStakedAmount,
              pendingRewards: demoPendingRewards,
              apr: demoApr,
              totalStaked: demoTotalStaked,
            }}
          />
        </div>

        {isSimulationMode && (
          <div className="dashboard-card wide">
            <DemoActivityPanel />
          </div>
        )}

        {isSimulationMode && (
          <div className="dashboard-card wide">
            <AuctionRoundViewer />
          </div>
        )}
      </div>

      <div className="dashboard-stats">
        <div className="stat-card">
          <span className="stat-label">Market Status</span>
          <span className="stat-value active">Active</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Active Prosumers</span>
          <span className="stat-value">{isLiveMode ? 'Live mode' : 'Demo simulation'}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Energy Traded</span>
          <span className="stat-value">
            {isSimulationMode ? `${totalVolume.toFixed(2)} kWh` : 'On-chain feed'}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Filled Demo Trades</span>
          <span className="stat-value">{isSimulationMode ? totalTrades : 'N/A'}</span>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
