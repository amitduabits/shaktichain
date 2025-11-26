import { useState } from 'react';
import { runSimulation, getResults } from '../services/api';

function SimulationPanel() {
  const [params, setParams] = useState({
    numProsumers: 10,
    numEvs: 5,
    duration: 24,
    gridCapacity: 1000,
  });
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle'); // idle, running, completed, error
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setParams((prev) => ({
      ...prev,
      [name]: parseFloat(value) || 0,
    }));
  };

  const handleRunSimulation = async () => {
    setStatus('running');
    setError(null);
    setResults(null);

    try {
      const response = await runSimulation(params);
      setJobId(response.job_id);

      // Poll for results
      const pollResults = async () => {
        try {
          const resultData = await getResults(response.job_id);
          if (resultData.status === 'completed') {
            setResults(resultData);
            setStatus('completed');
          } else if (resultData.status === 'failed') {
            setError(resultData.error || 'Simulation failed');
            setStatus('error');
          } else {
            // Still running, poll again
            setTimeout(pollResults, 2000);
          }
        } catch (err) {
          setError('Failed to fetch results');
          setStatus('error');
        }
      };

      setTimeout(pollResults, 2000);
    } catch (err) {
      setError(err.message || 'Failed to start simulation');
      setStatus('error');
    }
  };

  return (
    <div className="simulation-panel">
      <div className="simulation-form">
        <div className="form-group">
          <label htmlFor="numProsumers">Number of Prosumers</label>
          <input
            type="number"
            id="numProsumers"
            name="numProsumers"
            value={params.numProsumers}
            onChange={handleInputChange}
            min="1"
            max="100"
          />
        </div>

        <div className="form-group">
          <label htmlFor="numEvs">Number of EVs</label>
          <input
            type="number"
            id="numEvs"
            name="numEvs"
            value={params.numEvs}
            onChange={handleInputChange}
            min="0"
            max="50"
          />
        </div>

        <div className="form-group">
          <label htmlFor="duration">Duration (hours)</label>
          <input
            type="number"
            id="duration"
            name="duration"
            value={params.duration}
            onChange={handleInputChange}
            min="1"
            max="168"
          />
        </div>

        <div className="form-group">
          <label htmlFor="gridCapacity">Grid Capacity (kW)</label>
          <input
            type="number"
            id="gridCapacity"
            name="gridCapacity"
            value={params.gridCapacity}
            onChange={handleInputChange}
            min="100"
            max="10000"
          />
        </div>

        <button
          className="run-button"
          onClick={handleRunSimulation}
          disabled={status === 'running'}
        >
          {status === 'running' ? 'Running...' : 'Run Simulation'}
        </button>
      </div>

      {status === 'running' && (
        <div className="simulation-status running">
          <div className="spinner"></div>
          <p>Simulation in progress... Job ID: {jobId}</p>
        </div>
      )}

      {status === 'error' && (
        <div className="simulation-status error">
          <p>Error: {error}</p>
        </div>
      )}

      {status === 'completed' && results && (
        <div className="simulation-results">
          <h4>Simulation Results</h4>
          <div className="results-grid">
            <div className="result-item">
              <span className="result-label">Total Energy Traded</span>
              <span className="result-value">
                {results.total_energy_traded?.toFixed(2) || '--'} kWh
              </span>
            </div>
            <div className="result-item">
              <span className="result-label">Average Price</span>
              <span className="result-value">
                ${results.average_price?.toFixed(4) || '--'}/kWh
              </span>
            </div>
            <div className="result-item">
              <span className="result-label">Peak Demand</span>
              <span className="result-value">
                {results.peak_demand?.toFixed(2) || '--'} kW
              </span>
            </div>
            <div className="result-item">
              <span className="result-label">Grid Efficiency</span>
              <span className="result-value">
                {results.grid_efficiency?.toFixed(1) || '--'}%
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SimulationPanel;
