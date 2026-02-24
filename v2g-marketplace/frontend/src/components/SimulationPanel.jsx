import { useState, useEffect, useCallback, useRef } from 'react';
import AgentMixSlider from './AgentMixSlider';
import {
  startSimulation,
  getSimulationStatus,
  downloadSimulationCsv,
} from '../services/api';

const DURATION_OPTIONS = [
  { value: 1, label: '1 Day' },
  { value: 7, label: '7 Days' },
  { value: 30, label: '30 Days' },
];

const REGION_OPTIONS = [
  { value: 'delhi', label: 'Delhi' },
  { value: 'mumbai', label: 'Mumbai' },
  { value: 'bangalore', label: 'Bangalore' },
  { value: 'chennai', label: 'Chennai' },
];

function SimulationPanel() {
  // Configuration state
  const [config, setConfig] = useState({
    numAgents: 200,
    duration: 7,
    agentMix: {
      residential: 50,
      commercial: 30,
      fleet: 20,
    },
    region: 'delhi',
  });

  // Simulation state
  const [status, setStatus] = useState('idle'); // idle, running, completed, error
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState({
    percent: 0,
    currentDay: 0,
    totalDays: 0,
    estimatedTimeRemaining: null,
  });
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);

  // Polling ref
  const pollIntervalRef = useRef(null);
  const startTimeRef = useRef(null);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  // Handle agent count slider change
  const handleAgentCountChange = (e) => {
    setConfig((prev) => ({
      ...prev,
      numAgents: parseInt(e.target.value, 10),
    }));
  };

  // Handle duration dropdown change
  const handleDurationChange = (e) => {
    setConfig((prev) => ({
      ...prev,
      duration: parseInt(e.target.value, 10),
    }));
  };

  // Handle agent mix change
  const handleAgentMixChange = (newMix) => {
    setConfig((prev) => ({
      ...prev,
      agentMix: newMix,
    }));
  };

  // Handle region dropdown change
  const handleRegionChange = (e) => {
    setConfig((prev) => ({
      ...prev,
      region: e.target.value,
    }));
  };

  // Format time remaining
  const formatTimeRemaining = (seconds) => {
    if (!seconds || seconds <= 0) return 'Calculating...';
    if (seconds < 60) return `${Math.round(seconds)}s remaining`;
    if (seconds < 3600) {
      const mins = Math.floor(seconds / 60);
      const secs = Math.round(seconds % 60);
      return `${mins}m ${secs}s remaining`;
    }
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${mins}m remaining`;
  };

  // Poll for simulation status
  const pollStatus = useCallback(async (id) => {
    try {
      const statusData = await getSimulationStatus(id);

      if (statusData.status === 'completed') {
        setStatus('completed');
        setProgress({
          percent: 100,
          currentDay: statusData.total_days,
          totalDays: statusData.total_days,
          estimatedTimeRemaining: 0,
        });
        setResults(statusData.results);
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        return 'completed';
      } else if (statusData.status === 'failed') {
        setStatus('error');
        setError(statusData.error || 'Simulation failed');
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
        }
        return 'failed';
      } else {
        // Still running
        const percent = statusData.progress || 0;
        const currentDay = statusData.current_day || 0;
        const totalDays = statusData.total_days || config.duration;

        // Estimate time remaining based on elapsed time and progress
        let estimatedTimeRemaining = null;
        if (startTimeRef.current && percent > 0) {
          const elapsed = (Date.now() - startTimeRef.current) / 1000;
          const totalEstimate = elapsed / (percent / 100);
          estimatedTimeRemaining = totalEstimate - elapsed;
        }

        setProgress({
          percent,
          currentDay,
          totalDays,
          estimatedTimeRemaining,
        });
        return statusData.status || 'running';
      }
    } catch (err) {
      console.error('Error polling status:', err);
      // Don't stop polling on transient errors
      return 'error';
    }
  }, [config.duration]);

  // Start simulation
  const handleRunSimulation = async () => {
    setStatus('running');
    setError(null);
    setResults(null);
    setProgress({
      percent: 0,
      currentDay: 0,
      totalDays: config.duration,
      estimatedTimeRemaining: null,
    });
    startTimeRef.current = Date.now();

    try {
      const response = await startSimulation({
        num_agents: config.numAgents,
        duration_days: config.duration,
        agent_mix: config.agentMix,
        region: config.region,
      });

      const id = response.job_id;
      setJobId(id);

      // Poll once immediately so UI updates with real backend state.
      const firstStatus = await pollStatus(id);

      // Continue polling every 2 seconds while the simulation is active.
      if (firstStatus !== 'completed' && firstStatus !== 'failed') {
        pollIntervalRef.current = setInterval(() => pollStatus(id), 2000);
      }
    } catch (err) {
      setStatus('error');
      setError(err.message || 'Failed to start simulation');
    }
  };

  // Run again (reset to configuration)
  const handleRunAgain = () => {
    setStatus('idle');
    setJobId(null);
    setProgress({
      percent: 0,
      currentDay: 0,
      totalDays: 0,
      estimatedTimeRemaining: null,
    });
    setResults(null);
    setError(null);
  };

  // Download CSV
  const handleDownloadCsv = async () => {
    if (!jobId) return;
    try {
      await downloadSimulationCsv(jobId);
    } catch (err) {
      console.error('Error downloading CSV:', err);
    }
  };

  // View full report (placeholder - could navigate to report page)
  const handleViewFullReport = () => {
    // Could navigate to a full report page
    console.log('View full report for job:', jobId);
    // For now, open in new tab if there's a report URL
    if (results?.reportUrl) {
      window.open(results.reportUrl, '_blank');
    }
  };

  const isRunning = status === 'running';
  const isCompleted = status === 'completed';
  const isError = status === 'error';

  return (
    <div className="simulation-panel">
      {/* Configuration Form */}
      {!isCompleted && (
        <div className="simulation-config">
          {/* Number of Agents Slider */}
          <div className="config-section">
            <div className="config-row">
              <label htmlFor="numAgents">Number of Agents</label>
              <span className="config-value">{config.numAgents}</span>
            </div>
            <input
              type="range"
              id="numAgents"
              min="50"
              max="1000"
              step="10"
              value={config.numAgents}
              onChange={handleAgentCountChange}
              disabled={isRunning}
              className="config-slider"
            />
            <div className="slider-labels">
              <span>50</span>
              <span>1000</span>
            </div>
          </div>

          {/* Duration Dropdown */}
          <div className="config-section">
            <label htmlFor="duration">Simulation Duration</label>
            <select
              id="duration"
              value={config.duration}
              onChange={handleDurationChange}
              disabled={isRunning}
              className="config-select"
            >
              {DURATION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Agent Mix */}
          <div className="config-section agent-mix-section">
            <AgentMixSlider
              values={config.agentMix}
              onChange={handleAgentMixChange}
              disabled={isRunning}
            />
          </div>

          {/* Region Dropdown */}
          <div className="config-section">
            <label htmlFor="region">Region</label>
            <select
              id="region"
              value={config.region}
              onChange={handleRegionChange}
              disabled={isRunning}
              className="config-select"
            >
              {REGION_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Run Button */}
          <button
            className="run-button"
            onClick={handleRunSimulation}
            disabled={isRunning}
          >
            {isRunning ? (
              <>
                <span className="spinner" />
                <span>Running...</span>
              </>
            ) : (
              'Run Simulation'
            )}
          </button>
        </div>
      )}

      {/* Progress Display */}
      {isRunning && (
        <div className="simulation-progress">
          <div className="progress-header">
            <span className="progress-title">Simulation Progress</span>
            <span className="progress-percent">{Math.round(progress.percent)}%</span>
          </div>

          <div className="progress-bar-container">
            <div
              className="progress-bar-fill"
              style={{ width: `${progress.percent}%` }}
            />
          </div>

          <div className="progress-details">
            <span className="progress-status">
              Simulating day {progress.currentDay} of {progress.totalDays}...
            </span>
            <span className="progress-eta">
              {formatTimeRemaining(progress.estimatedTimeRemaining)}
            </span>
          </div>
        </div>
      )}

      {/* Error Display */}
      {isError && (
        <div className="simulation-error">
          <div className="error-icon">!</div>
          <div className="error-content">
            <span className="error-title">Simulation Failed</span>
            <span className="error-message">{error}</span>
          </div>
          <button className="retry-button" onClick={handleRunAgain}>
            Try Again
          </button>
        </div>
      )}

      {/* Results Preview */}
      {isCompleted && results && (
        <div className="simulation-results">
          <h4>Simulation Complete</h4>

          <div className="results-summary">
            <div className="result-card">
              <span className="result-card-label">Total Energy Traded</span>
              <span className="result-card-value">
                {results.totalEnergyTraded?.toLocaleString() || '--'} kWh
              </span>
            </div>

            <div className="result-card">
              <span className="result-card-label">Average Price</span>
              <span className="result-card-value">
                INR {results.averagePrice?.toFixed(2) || '--'}/kWh
              </span>
            </div>

            <div className="result-card">
              <span className="result-card-label">Total Transactions</span>
              <span className="result-card-value">
                {results.totalTransactions?.toLocaleString() || '--'}
              </span>
            </div>

            <div className="result-card">
              <span className="result-card-label">Grid Savings</span>
              <span className="result-card-value highlight">
                INR {results.gridSavings?.toLocaleString() || '--'}
              </span>
            </div>

            <div className="result-card">
              <span className="result-card-label">Carbon Offset</span>
              <span className="result-card-value">
                {results.carbonOffset?.toFixed(1) || '--'} tons CO2
              </span>
            </div>

            <div className="result-card">
              <span className="result-card-label">Peak Reduction</span>
              <span className="result-card-value">
                {results.peakReduction?.toFixed(1) || '--'}%
              </span>
            </div>
          </div>

          <div className="results-actions">
            <button className="action-button primary" onClick={handleViewFullReport}>
              View Full Report
            </button>
            <button className="action-button secondary" onClick={handleDownloadCsv}>
              Download CSV
            </button>
            <button className="action-button outline" onClick={handleRunAgain}>
              Run Again
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default SimulationPanel;

