import axios from 'axios';

// Create axios instance with default config
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging and auth
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response) {
      // Server responded with error status
      const message = error.response.data?.detail || error.response.data?.message || 'Server error';
      return Promise.reject(new Error(message));
    } else if (error.request) {
      // Request made but no response
      return Promise.reject(new Error('Network error - please check your connection'));
    } else {
      // Error in request setup
      return Promise.reject(error);
    }
  }
);

/**
 * Check the health status of the backend API
 * @returns {Promise<Object>} Health status object
 */
export async function getHealth() {
  return api.get('/health');
}

/**
 * Run a V2G marketplace simulation
 * @param {Object} params - Simulation parameters
 * @param {number} params.numProsumers - Number of prosumers in simulation
 * @param {number} params.numEvs - Number of EVs in simulation
 * @param {number} params.duration - Duration of simulation in hours
 * @param {number} params.gridCapacity - Grid capacity in kW
 * @returns {Promise<Object>} Job information with job_id
 */
export async function runSimulation(params) {
  return api.post('/simulation/run', {
    num_prosumers: params.numProsumers,
    num_evs: params.numEvs,
    duration_hours: params.duration,
    grid_capacity_kw: params.gridCapacity,
  });
}

/**
 * Get results of a simulation job
 * @param {string} jobId - The job ID returned from runSimulation
 * @returns {Promise<Object>} Simulation results
 */
export async function getResults(jobId) {
  return api.get(`/simulation/results/${jobId}`);
}

/**
 * Get the current energy price
 * @returns {Promise<Object>} Current price information
 */
export async function getCurrentPrice() {
  return api.get('/market/price');
}

/**
 * Get price history for a time range
 * @param {string} startTime - ISO timestamp for start of range
 * @param {string} endTime - ISO timestamp for end of range
 * @returns {Promise<Array>} Array of price data points
 */
export async function getPriceHistory(startTime, endTime) {
  return api.get('/market/price/history', {
    params: { start: startTime, end: endTime },
  });
}

/**
 * Get list of active prosumers
 * @returns {Promise<Array>} Array of prosumer objects
 */
export async function getProsumers() {
  return api.get('/prosumers');
}

/**
 * Get prosumer details by ID
 * @param {string} prosumerId - Prosumer ID
 * @returns {Promise<Object>} Prosumer details
 */
export async function getProsumerById(prosumerId) {
  return api.get(`/prosumers/${prosumerId}`);
}

export default api;
