/**
 * Tests for useApi and usePolling hooks
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useApi, usePolling } from '../../hooks/useApi';

describe('useApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial State', () => {
    it('returns initial state correctly', () => {
      const mockApi = vi.fn();
      const { result } = renderHook(() => useApi(mockApi));

      expect(result.current.data).toBeNull();
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
      expect(typeof result.current.execute).toBe('function');
      expect(typeof result.current.reset).toBe('function');
    });

    it('does not call API function on mount', () => {
      const mockApi = vi.fn();
      renderHook(() => useApi(mockApi));

      expect(mockApi).not.toHaveBeenCalled();
    });
  });

  describe('Execute Function', () => {
    it('sets loading to true when executing', async () => {
      const mockApi = vi.fn(() => new Promise(() => {})); // Never resolves
      const { result } = renderHook(() => useApi(mockApi));

      act(() => {
        result.current.execute();
      });

      expect(result.current.loading).toBe(true);
    });

    it('sets data on successful execution', async () => {
      const mockData = { id: 1, name: 'test' };
      const mockApi = vi.fn().mockResolvedValue(mockData);
      const { result } = renderHook(() => useApi(mockApi));

      await act(async () => {
        await result.current.execute();
      });

      expect(result.current.data).toEqual(mockData);
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('passes arguments to API function', async () => {
      const mockApi = vi.fn().mockResolvedValue({ success: true });
      const { result } = renderHook(() => useApi(mockApi));

      await act(async () => {
        await result.current.execute('arg1', 'arg2', { key: 'value' });
      });

      expect(mockApi).toHaveBeenCalledWith('arg1', 'arg2', { key: 'value' });
    });

    it('returns the result from API function', async () => {
      const mockData = { id: 1 };
      const mockApi = vi.fn().mockResolvedValue(mockData);
      const { result } = renderHook(() => useApi(mockApi));

      let returnValue;
      await act(async () => {
        returnValue = await result.current.execute();
      });

      expect(returnValue).toEqual(mockData);
    });

    it('sets error on failed execution', async () => {
      const mockError = new Error('API Error');
      const mockApi = vi.fn().mockRejectedValue(mockError);
      const { result } = renderHook(() => useApi(mockApi));

      await act(async () => {
        try {
          await result.current.execute();
        } catch (_error) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('API Error');
      expect(result.current.loading).toBe(false);
      expect(result.current.data).toBeNull();
    });

    it('extracts error message from Axios response', async () => {
      const mockError = {
        response: {
          data: {
            message: 'Unauthorized',
          },
        },
      };
      const mockApi = vi.fn().mockRejectedValue(mockError);
      const { result } = renderHook(() => useApi(mockApi));

      await act(async () => {
        try {
          await result.current.execute();
        } catch (_error) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('Unauthorized');
    });

    it('clears previous error on new execution', async () => {
      const mockApi = vi
        .fn()
        .mockRejectedValueOnce(new Error('First error'))
        .mockResolvedValueOnce({ success: true });

      const { result } = renderHook(() => useApi(mockApi));

      // First call - error
      await act(async () => {
        try {
          await result.current.execute();
        } catch (_error) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('First error');

      // Second call - success
      await act(async () => {
        await result.current.execute();
      });

      expect(result.current.error).toBeNull();
    });

    it('throws error for caller to handle', async () => {
      const mockError = new Error('API Error');
      const mockApi = vi.fn().mockRejectedValue(mockError);
      const { result } = renderHook(() => useApi(mockApi));

      await expect(
        act(async () => {
          await result.current.execute();
        })
      ).rejects.toThrow('API Error');
    });
  });

  describe('Reset Function', () => {
    it('resets all state to initial values', async () => {
      const mockApi = vi.fn().mockResolvedValue({ data: 'test' });
      const { result } = renderHook(() => useApi(mockApi));

      // Execute first
      await act(async () => {
        await result.current.execute();
      });

      expect(result.current.data).not.toBeNull();

      // Reset
      act(() => {
        result.current.reset();
      });

      expect(result.current.data).toBeNull();
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
    });

    it('resets error state', async () => {
      const mockApi = vi.fn().mockRejectedValue(new Error('Error'));
      const { result } = renderHook(() => useApi(mockApi));

      await act(async () => {
        try {
          await result.current.execute();
        } catch (_error) {
          // Expected to throw
        }
      });

      expect(result.current.error).not.toBeNull();

      act(() => {
        result.current.reset();
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('Hook Stability', () => {
    it('maintains stable execute reference', () => {
      const mockApi = vi.fn().mockResolvedValue({});
      const { result, rerender } = renderHook(() => useApi(mockApi));

      const firstExecute = result.current.execute;
      rerender();
      const secondExecute = result.current.execute;

      expect(firstExecute).toBe(secondExecute);
    });

    it('maintains stable reset reference', () => {
      const mockApi = vi.fn().mockResolvedValue({});
      const { result, rerender } = renderHook(() => useApi(mockApi));

      const firstReset = result.current.reset;
      rerender();
      const secondReset = result.current.reset;

      expect(firstReset).toBe(secondReset);
    });
  });
});

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Initial State', () => {
    it('returns initial state correctly', () => {
      const mockApi = vi.fn();
      const { result } = renderHook(() => usePolling(mockApi));

      expect(result.current.data).toBeNull();
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBeNull();
      expect(result.current.isPolling).toBe(false);
      expect(typeof result.current.startPolling).toBe('function');
      expect(typeof result.current.stopPolling).toBe('function');
    });

    it('does not start polling automatically', () => {
      const mockApi = vi.fn().mockResolvedValue({});
      renderHook(() => usePolling(mockApi));

      expect(mockApi).not.toHaveBeenCalled();
    });
  });

  describe('Start Polling', () => {
    it('makes initial fetch when starting polling', async () => {
      const mockApi = vi.fn().mockResolvedValue({ status: 'ok' });
      const { result } = renderHook(() => usePolling(mockApi, 1000));

      await act(async () => {
        await result.current.startPolling();
      });

      expect(mockApi).toHaveBeenCalledTimes(1);
    });

    it('sets isPolling to true', async () => {
      const mockApi = vi.fn().mockResolvedValue({ status: 'ok' });
      const { result } = renderHook(() => usePolling(mockApi, 1000));

      await act(async () => {
        await result.current.startPolling();
      });

      expect(result.current.isPolling).toBe(true);
    });

    it('passes arguments to API function', async () => {
      const mockApi = vi.fn().mockResolvedValue({});
      const { result } = renderHook(() => usePolling(mockApi, 1000));

      await act(async () => {
        await result.current.startPolling('arg1', 123);
      });

      expect(mockApi).toHaveBeenCalledWith('arg1', 123);
    });

    it('updates data on successful poll', async () => {
      const mockData = { count: 1 };
      const mockApi = vi.fn().mockResolvedValue(mockData);
      const { result } = renderHook(() => usePolling(mockApi, 1000));

      await act(async () => {
        await result.current.startPolling();
      });

      expect(result.current.data).toEqual(mockData);
    });
  });

  describe('Polling Interval', () => {
    it('polls at specified interval', async () => {
      const mockApi = vi.fn().mockResolvedValue({ tick: 1 });
      const { result } = renderHook(() => usePolling(mockApi, 1000));

      await act(async () => {
        await result.current.startPolling();
      });

      expect(mockApi).toHaveBeenCalledTimes(1);

      // Advance by interval
      await act(async () => {
        vi.advanceTimersByTime(1000);
      });

      expect(mockApi).toHaveBeenCalledTimes(2);

      // Advance again
      await act(async () => {
        vi.advanceTimersByTime(1000);
      });

      expect(mockApi).toHaveBeenCalledTimes(3);
    });

    it('uses default interval of 5000ms', async () => {
      const mockApi = vi.fn().mockResolvedValue({});
      const { result } = renderHook(() => usePolling(mockApi));

      await act(async () => {
        await result.current.startPolling();
      });

      expect(mockApi).toHaveBeenCalledTimes(1);

      await act(async () => {
        vi.advanceTimersByTime(4999);
      });

      expect(mockApi).toHaveBeenCalledTimes(1);

      await act(async () => {
        vi.advanceTimersByTime(1);
      });

      expect(mockApi).toHaveBeenCalledTimes(2);
    });
  });

  describe('Stop Polling', () => {
    it('stops polling when stopPolling called', async () => {
      const mockApi = vi.fn().mockResolvedValue({});
      const { result } = renderHook(() => usePolling(mockApi, 1000));

      await act(async () => {
        await result.current.startPolling();
      });

      expect(mockApi).toHaveBeenCalledTimes(1);

      act(() => {
        result.current.stopPolling();
      });

      await act(async () => {
        vi.advanceTimersByTime(5000);
      });

      // Should not have been called again
      expect(mockApi).toHaveBeenCalledTimes(1);
    });

    it('sets isPolling to false when stopped', async () => {
      const mockApi = vi.fn().mockResolvedValue({});
      const { result } = renderHook(() => usePolling(mockApi, 1000));

      await act(async () => {
        await result.current.startPolling();
      });

      expect(result.current.isPolling).toBe(true);

      act(() => {
        result.current.stopPolling();
      });

      expect(result.current.isPolling).toBe(false);
    });

    it('is safe to call stopPolling when not polling', () => {
      const mockApi = vi.fn();
      const { result } = renderHook(() => usePolling(mockApi, 1000));

      // Should not throw
      act(() => {
        result.current.stopPolling();
      });

      expect(result.current.isPolling).toBe(false);
    });
  });

  describe('Error Handling', () => {
    it('sets error on failed poll', async () => {
      const mockApi = vi.fn().mockRejectedValue(new Error('Poll failed'));
      const { result } = renderHook(() => usePolling(mockApi, 1000));

      await act(async () => {
        try {
          await result.current.startPolling();
        } catch (_error) {
          // Expected
        }
      });

      expect(result.current.error).toBe('Poll failed');
    });

    it('clears error on successful poll', async () => {
      const mockApi = vi
        .fn()
        .mockRejectedValueOnce(new Error('First error'))
        .mockResolvedValueOnce({ success: true });

      const { result } = renderHook(() => usePolling(mockApi, 1000));

      await act(async () => {
        try {
          await result.current.startPolling();
        } catch (_error) {
          // Expected to throw
        }
      });

      expect(result.current.error).toBe('First error');

      // Advance to next poll
      await act(async () => {
        vi.advanceTimersByTime(1000);
      });

      expect(result.current.error).toBeNull();
    });
  });
});
