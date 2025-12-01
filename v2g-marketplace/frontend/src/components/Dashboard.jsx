import { useState, useEffect } from 'react';
import PriceChart from './PriceChart';
import SimulationPanel from './SimulationPanel';
import { getCurrentPrice } from '../services/api';
import { useAppMode } from '../providers/Web3Provider';
import { TokenBalance, StakingPanel, BidForm } from './web3';

function Dashboard() {
  const [currentPrice, setCurrentPrice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const { isLiveMode, isSimulationMode } = useAppMode();

  useEffect(() => {
    const fetchPrice = async () => {
      try {
        const data = await getCurrentPrice();
        setCurrentPrice(data);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch current price');
        setLoading(false);
      }
    };

    fetchPrice();
    const interval = setInterval(fetchPrice, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, []);

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
            Current Price: ₹{currentPrice?.price?.toFixed(2) || 'N/A'}/kWh
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

        {/* Web3 Components - shown alongside simulation */}
        <div className="dashboard-card">
          <h3>Your Balance</h3>
          <TokenBalance
            variant="detailed"
            showVotingPower
            showTotalSupply
            simulatedBalance="1,500.00"
          />
        </div>

        <div className="dashboard-card wide">
          <BidForm
            simulatedData={{
              currentRound: 42,
              timeRemaining: 300,
              isOpen: true
            }}
          />
        </div>

        <div className="dashboard-card wide">
          <StakingPanel
            simulatedData={{
              stakedAmount: '500.00',
              pendingRewards: '12.50',
              apr: 12.5,
              totalStaked: '5,000,000'
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
          <span className="stat-value">--</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total Energy Traded</span>
          <span className="stat-value">-- kWh</span>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
