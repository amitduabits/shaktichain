import { useState, useEffect } from 'react';
import PriceChart from './PriceChart';
import SimulationPanel from './SimulationPanel';
import { getCurrentPrice } from '../services/api';

function Dashboard() {
  const [currentPrice, setCurrentPrice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
            Current Price: ${currentPrice?.price?.toFixed(4) || 'N/A'}/kWh
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
