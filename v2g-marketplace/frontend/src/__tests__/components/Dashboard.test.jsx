/**
 * Tests for Dashboard component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import Dashboard from '../../components/Dashboard';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  getCurrentPrice: vi.fn(),
}));

// Mock child components to isolate Dashboard testing
vi.mock('../../components/PriceChart', () => ({
  default: () => <div data-testid="price-chart">Price Chart Mock</div>,
}));

vi.mock('../../components/SimulationPanel', () => ({
  default: () => <div data-testid="simulation-panel">Simulation Panel Mock</div>,
}));

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial Render', () => {
    it('renders dashboard with all sections', async () => {
      api.getCurrentPrice.mockResolvedValue({ price: 6.5 });

      render(<Dashboard />);

      // Check header
      expect(screen.getByText('Energy Market Overview')).toBeInTheDocument();

      // Check loading state initially
      expect(screen.getByText('Loading...')).toBeInTheDocument();

      // Wait for price to load
      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });
    });

    it('renders price chart component', async () => {
      api.getCurrentPrice.mockResolvedValue({ price: 6.5 });

      render(<Dashboard />);

      expect(screen.getByTestId('price-chart')).toBeInTheDocument();
    });

    it('renders simulation panel component', async () => {
      api.getCurrentPrice.mockResolvedValue({ price: 6.5 });

      render(<Dashboard />);

      expect(screen.getByTestId('simulation-panel')).toBeInTheDocument();
    });

    it('renders stats cards', async () => {
      api.getCurrentPrice.mockResolvedValue({ price: 6.5 });

      render(<Dashboard />);

      expect(screen.getByText('Market Status')).toBeInTheDocument();
      expect(screen.getByText('Active Prosumers')).toBeInTheDocument();
      expect(screen.getByText('Total Energy Traded')).toBeInTheDocument();
    });
  });

  describe('Price Display', () => {
    it('displays current price after loading', async () => {
      api.getCurrentPrice.mockResolvedValue({ price: 6.5432 });

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/Current Price:/)).toBeInTheDocument();
        expect(screen.getByText(/6.5432/)).toBeInTheDocument();
      });
    });

    it('displays error state when API fails', async () => {
      api.getCurrentPrice.mockRejectedValue(new Error('Network error'));

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText('Error')).toBeInTheDocument();
      });
    });

    it('displays N/A when price is null', async () => {
      api.getCurrentPrice.mockResolvedValue({ price: null });

      render(<Dashboard />);

      await waitFor(() => {
        expect(screen.getByText(/N\/A/)).toBeInTheDocument();
      });
    });
  });

  describe('Data Fetching', () => {
    it('fetches price on mount', async () => {
      api.getCurrentPrice.mockResolvedValue({ price: 6.5 });

      render(<Dashboard />);

      expect(api.getCurrentPrice).toHaveBeenCalledTimes(1);
    });

    it('sets up price refresh interval', async () => {
      vi.useFakeTimers();
      api.getCurrentPrice.mockResolvedValue({ price: 6.5 });

      render(<Dashboard />);

      // Initial fetch
      expect(api.getCurrentPrice).toHaveBeenCalledTimes(1);

      // Advance by 30 seconds (refresh interval)
      vi.advanceTimersByTime(30000);

      expect(api.getCurrentPrice).toHaveBeenCalledTimes(2);

      vi.useRealTimers();
    });

    it('cleans up interval on unmount', async () => {
      vi.useFakeTimers();
      api.getCurrentPrice.mockResolvedValue({ price: 6.5 });

      const { unmount } = render(<Dashboard />);

      expect(api.getCurrentPrice).toHaveBeenCalledTimes(1);

      unmount();

      // Advance time after unmount - should not call API
      vi.advanceTimersByTime(60000);

      // Should still be 1 (no additional calls after unmount)
      expect(api.getCurrentPrice).toHaveBeenCalledTimes(1);

      vi.useRealTimers();
    });
  });

  describe('Market Status', () => {
    it('shows Active market status', async () => {
      api.getCurrentPrice.mockResolvedValue({ price: 6.5 });

      render(<Dashboard />);

      expect(screen.getByText('Active')).toBeInTheDocument();
    });
  });
});
