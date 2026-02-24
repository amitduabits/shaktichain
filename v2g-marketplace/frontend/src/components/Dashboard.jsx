import { useState, useEffect } from 'react';
import PriceChart from './PriceChart';
import SimulationPanel from './SimulationPanel';
import { getCurrentPrice } from '../services/api';
import { useOptionalAppMode } from '../providers/Web3Provider';
import { TokenBalance, StakingPanel, BidForm } from './web3';

function Dashboard() {
  const [currentPrice, setCurrentPrice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { isLiveMode, isSimulationMode } = useOptionalAppMode();

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

  const inferredPrice = currentPrice?.price ?? 0;
  const inferredRound = Math.max(1, Math.round(inferredPrice * 6));
  const inferredBalance = (Math.max(inferredPrice, 1) * 180).toFixed(2);
  const inferredStaked = (Math.max(inferredPrice, 1) * 60).toFixed(2);
  const inferredRewards = (Math.max(inferredPrice, 1) * 1.4).toFixed(2);
  const inferredApr = Math.max(3.5, Math.min(22.5, inferredPrice * 2.1));

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>Energy Market Overview</h2>
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
            simulatedBalance={inferredBalance}
          />
        </div>

        <div className="dashboard-card wide">
          <BidForm
            simulatedData={{
              currentRound: inferredRound,
              timeRemaining: Math.max(60, 900 - inferredRound * 10),
              isOpen: true,
            }}
          />
        </div>

        <div className="dashboard-card wide">
          <StakingPanel
            simulatedData={{
              stakedAmount: inferredStaked,
              pendingRewards: inferredRewards,
              apr: Number(inferredApr.toFixed(2)),
              totalStaked: (Math.max(inferredPrice, 1) * 700000).toFixed(0),
            }}
          />
        </div>
      </div>

      <div className="dashboard-stats">
        <div className="stat-card">
          <span className="stat-label">Market Status</span>
          <span className="stat-value active">Active</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Active Prosumers</span>
          <span className="stat-value">{isLiveMode ? 'Live mode' : 'Simulation mode'}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Energy Traded</span>
          <span className="stat-value">{isSimulationMode ? 'Computed in simulation' : 'On-chain feed'} </span>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
