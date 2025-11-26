import { useState, useCallback } from 'react';

/**
 * Custom hook for making API calls with loading and error states
 * @param {Function} apiFunction - The API function to call
 * @returns {Object} - { data, loading, error, execute }
 */
export function useApi(apiFunction) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const execute = useCallback(async (...args) => {
    setLoading(true);
    setError(null);

    try {
      const result = await apiFunction(...args);
      setData(result);
      return result;
    } catch (err) {
      const errorMessage = err.response?.data?.message || err.message || 'An error occurred';
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [apiFunction]);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
    setLoading(false);
  }, []);

  return { data, loading, error, execute, reset };
}

/**
 * Custom hook for polling API endpoints
 * @param {Function} apiFunction - The API function to poll
 * @param {number} interval - Polling interval in milliseconds
 * @returns {Object} - { data, loading, error, startPolling, stopPolling }
 */
export function usePolling(apiFunction, interval = 5000) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [intervalId, setIntervalId] = useState(null);

  const poll = useCallback(async (...args) => {
    try {
      const result = await apiFunction(...args);
      setData(result);
      setError(null);
      return result;
    } catch (err) {
      const errorMessage = err.response?.data?.message || err.message || 'An error occurred';
      setError(errorMessage);
      throw err;
    }
  }, [apiFunction]);

  const startPolling = useCallback(async (...args) => {
    setLoading(true);

    // Initial fetch
    await poll(...args);

    // Set up interval
    const id = setInterval(() => poll(...args), interval);
    setIntervalId(id);
    setLoading(false);
  }, [poll, interval]);

  const stopPolling = useCallback(() => {
    if (intervalId) {
      clearInterval(intervalId);
      setIntervalId(null);
    }
  }, [intervalId]);

  return { data, loading, error, startPolling, stopPolling, isPolling: !!intervalId };
}

export default useApi;
