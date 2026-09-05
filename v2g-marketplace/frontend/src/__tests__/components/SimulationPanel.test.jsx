/**
 * Tests for SimulationPanel component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import SimulationPanel from '../../components/SimulationPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  startSimulation: vi.fn(),
  getSimulationStatus: vi.fn(),
  downloadSimulationCsv: vi.fn(),
  getHealth: vi.fn().mockResolvedValue({ status: 'healthy' }),
}));

// Mock AgentMixSlider
vi.mock('../../components/AgentMixSlider', () => ({
  default: ({ values, onChange, disabled }) => (
    <div data-testid="agent-mix-slider">
      <span>Residential: {values.residential}%</span>
      <span>Commercial: {values.commercial}%</span>
      <span>Fleet: {values.fleet}%</span>
      <button
        onClick={() => onChange({ residential: 60, commercial: 25, fleet: 15 })}
        disabled={disabled}
        data-testid="change-mix"
      >
        Change Mix
      </button>
    </div>
  ),
}));

describe('SimulationPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial Render', () => {
    it('renders configuration form', () => {
      render(<SimulationPanel />);

      expect(screen.getByText('Number of Agents')).toBeInTheDocument();
      expect(screen.getByText('Simulation Duration')).toBeInTheDocument();
      expect(screen.getByText('Region')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /run simulation/i })).toBeInTheDocument();
    });

    it('shows default number of agents (200)', () => {
      render(<SimulationPanel />);

      expect(screen.getByText('200')).toBeInTheDocument();
    });

    it('renders duration options', () => {
      render(<SimulationPanel />);

      const durationSelect = screen.getByLabelText('Simulation Duration');
      expect(durationSelect).toBeInTheDocument();

      // Check options exist
      expect(screen.getByText('1 Day')).toBeInTheDocument();
      expect(screen.getByText('7 Days')).toBeInTheDocument();
      expect(screen.getByText('30 Days')).toBeInTheDocument();
    });

    it('renders region options', () => {
      render(<SimulationPanel />);

      const regionSelect = screen.getByLabelText('Region');
      expect(regionSelect).toBeInTheDocument();

      expect(screen.getByText('Delhi')).toBeInTheDocument();
      expect(screen.getByText('Mumbai')).toBeInTheDocument();
      expect(screen.getByText('Bangalore')).toBeInTheDocument();
      expect(screen.getByText('Chennai')).toBeInTheDocument();
      expect(screen.getByText('Kolkata')).toBeInTheDocument();
    });

    it('renders agent mix slider', () => {
      render(<SimulationPanel />);

      expect(screen.getByTestId('agent-mix-slider')).toBeInTheDocument();
    });
  });

  describe('Form Validation and Interaction', () => {
    it('updates agent count when slider changes', async () => {
      render(<SimulationPanel />);

      const slider = screen.getByLabelText('Number of Agents');

      // Change slider value
      fireEvent.change(slider, { target: { value: '500' } });

      expect(screen.getByText('500')).toBeInTheDocument();
    });

    it('validates agent count range (50-1000)', () => {
      render(<SimulationPanel />);

      const slider = screen.getByLabelText('Number of Agents');

      // Check min/max attributes
      expect(slider).toHaveAttribute('min', '50');
      expect(slider).toHaveAttribute('max', '1000');
    });

    it('updates duration when dropdown changes', async () => {
      const user = userEvent.setup();
      render(<SimulationPanel />);

      const durationSelect = screen.getByLabelText('Simulation Duration');

      await user.selectOptions(durationSelect, '30');

      expect(durationSelect).toHaveValue('30');
    });

    it('updates region when dropdown changes', async () => {
      const user = userEvent.setup();
      render(<SimulationPanel />);

      const regionSelect = screen.getByLabelText('Region');

      await user.selectOptions(regionSelect, 'mumbai');

      expect(regionSelect).toHaveValue('mumbai');
    });

    it('updates agent mix when changed', async () => {
      const user = userEvent.setup();
      render(<SimulationPanel />);

      const changeMixButton = screen.getByTestId('change-mix');
      await user.click(changeMixButton);

      expect(screen.getByText('Residential: 60%')).toBeInTheDocument();
      expect(screen.getByText('Commercial: 25%')).toBeInTheDocument();
      expect(screen.getByText('Fleet: 15%')).toBeInTheDocument();
    });
  });

  describe('Simulation Execution', () => {
    it('starts simulation when Run button clicked', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockResolvedValue({ job_id: 'test-job-123' });
      api.getSimulationStatus.mockResolvedValue({
        status: 'running',
        progress: 50,
        current_day: 3,
        total_days: 7,
      });

      render(<SimulationPanel />);

      const runButton = screen.getByRole('button', { name: /run simulation/i });
      await user.click(runButton);

      expect(api.startSimulation).toHaveBeenCalledWith({
        num_agents: 200,
        duration_days: 7,
        agent_mix: { residential: 50, commercial: 30, fleet: 20 },
        region: 'delhi',
      });
    });

    it('shows running state during simulation', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockResolvedValue({ job_id: 'test-job-123' });
      api.getSimulationStatus.mockResolvedValue({
        status: 'running',
        progress: 50,
        current_day: 3,
        total_days: 7,
      });

      render(<SimulationPanel />);

      const runButton = screen.getByRole('button', { name: /run simulation/i });
      await user.click(runButton);

      await waitFor(() => {
        expect(screen.getByText(/Running.../)).toBeInTheDocument();
      });
    });

    it('disables form controls during simulation', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockResolvedValue({ job_id: 'test-job-123' });
      api.getSimulationStatus.mockResolvedValue({
        status: 'running',
        progress: 50,
        current_day: 3,
        total_days: 7,
      });

      render(<SimulationPanel />);

      const runButton = screen.getByRole('button', { name: /run simulation/i });
      await user.click(runButton);

      await waitFor(() => {
        expect(screen.getByLabelText('Number of Agents')).toBeDisabled();
        expect(screen.getByLabelText('Simulation Duration')).toBeDisabled();
        expect(screen.getByLabelText('Region')).toBeDisabled();
      });
    });
  });

  describe('Progress Display', () => {
    it('shows progress bar during simulation', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockResolvedValue({ job_id: 'test-job-123' });
      api.getSimulationStatus.mockResolvedValue({
        status: 'running',
        progress: 50,
        current_day: 3,
        total_days: 7,
      });

      render(<SimulationPanel />);

      await user.click(screen.getByRole('button', { name: /run simulation/i }));

      await waitFor(() => {
        expect(screen.getByText('Simulation Progress')).toBeInTheDocument();
        expect(screen.getByText('50%')).toBeInTheDocument();
      });
    });

    it('shows current day progress', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockResolvedValue({ job_id: 'test-job-123' });
      api.getSimulationStatus.mockResolvedValue({
        status: 'running',
        progress: 50,
        current_day: 3,
        total_days: 7,
      });

      render(<SimulationPanel />);

      await user.click(screen.getByRole('button', { name: /run simulation/i }));

      await waitFor(() => {
        expect(screen.getByText(/Simulating day 3 of 7/)).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('shows error state when simulation fails to start', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockRejectedValue(new Error('Failed to start'));

      render(<SimulationPanel />);

      await user.click(screen.getByRole('button', { name: /run simulation/i }));

      await waitFor(() => {
        expect(screen.getByText('Simulation Failed')).toBeInTheDocument();
        expect(screen.getByText(/Failed to start/)).toBeInTheDocument();
      });
    });

    it('shows try again button on error', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockRejectedValue(new Error('Network error'));

      render(<SimulationPanel />);

      await user.click(screen.getByRole('button', { name: /run simulation/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      });
    });

    it('resets to idle state when try again clicked', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockRejectedValueOnce(new Error('Network error'));

      render(<SimulationPanel />);

      await user.click(screen.getByRole('button', { name: /run simulation/i }));

      await waitFor(() => {
        expect(screen.getByText('Simulation Failed')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /try again/i }));

      // Should be back to idle state
      expect(screen.getByRole('button', { name: /run simulation/i })).toBeInTheDocument();
      expect(screen.queryByText('Simulation Failed')).not.toBeInTheDocument();
    });
  });

  describe('Results Display', () => {
    it('shows results when simulation completes', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockResolvedValue({ job_id: 'test-job-123' });
      api.getSimulationStatus
        .mockResolvedValueOnce({
          status: 'running',
          progress: 100,
          current_day: 7,
          total_days: 7,
        })
        .mockResolvedValue({
          status: 'completed',
          total_days: 7,
          results: {
            totalEnergyTraded: 50000,
            averagePrice: 6.5,
            totalTransactions: 1200,
            gridSavings: 25000,
            carbonOffset: 12.5,
            peakReduction: 15.3,
          },
        });

      render(<SimulationPanel />);

      await user.click(screen.getByRole('button', { name: /run simulation/i }));

      await waitFor(
        () => {
          expect(screen.getByText('Simulation Complete')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });

    it('shows action buttons after completion', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockResolvedValue({ job_id: 'test-job-123' });
      api.getSimulationStatus.mockResolvedValue({
        status: 'completed',
        total_days: 7,
        results: {
          totalEnergyTraded: 50000,
          averagePrice: 6.5,
          totalTransactions: 1200,
          gridSavings: 25000,
          carbonOffset: 12.5,
          peakReduction: 15.3,
        },
      });

      render(<SimulationPanel />);

      await user.click(screen.getByRole('button', { name: /run simulation/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /view full report/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /download csv/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /run again/i })).toBeInTheDocument();
      });
    });

    it('calls download API when Download CSV clicked', async () => {
      const user = userEvent.setup();
      api.startSimulation.mockResolvedValue({ job_id: 'test-job-123' });
      api.getSimulationStatus.mockResolvedValue({
        status: 'completed',
        total_days: 7,
        results: {
          totalEnergyTraded: 50000,
          averagePrice: 6.5,
        },
      });
      api.downloadSimulationCsv.mockResolvedValue();

      render(<SimulationPanel />);

      await user.click(screen.getByRole('button', { name: /run simulation/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /download csv/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /download csv/i }));

      expect(api.downloadSimulationCsv).toHaveBeenCalledWith('test-job-123');
    });
  });
});
