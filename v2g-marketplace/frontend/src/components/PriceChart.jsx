import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { getPriceHistory } from '../services/api';

function PriceChart() {
  const [priceData, setPriceData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPriceHistory = async () => {
      try {
        const history = await getPriceHistory();

        if (history && history.length > 0) {
          // Transform API data to chart format
          const chartData = history.reverse().map((item) => {
            const date = new Date(item.time);
            return {
              time: date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
              price: item.price,
              // Calculate approximate demand (mock for now)
              demand: 50 + (item.price - 6) * 10,
            };
          });
          setPriceData(chartData);
        } else {
          // Fallback to sample data if no history
          const sampleData = generateSampleData();
          setPriceData(sampleData);
        }
        setLoading(false);
      } catch (err) {
        console.error('Error fetching price history:', err);
        // Fallback to sample data on error
        const sampleData = generateSampleData();
        setPriceData(sampleData);
        setError('Using sample data');
        setLoading(false);
      }
    };

    // Generate sample price data for demonstration/fallback
    const generateSampleData = () => {
      const data = [];
      const now = new Date();
      for (let i = 23; i >= 0; i--) {
        const time = new Date(now - i * 60 * 60 * 1000);
        const basePrice = 6.0; // Changed to INR base price
        const variation = Math.sin((24 - i) / 24 * Math.PI * 2) * 2.0;
        const noise = (Math.random() - 0.5) * 0.5;
        data.push({
          time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
          price: basePrice + variation + noise,
          demand: 50 + Math.sin((24 - i) / 24 * Math.PI * 2) * 30 + Math.random() * 10,
        });
      }
      return data;
    };

    fetchPriceHistory();
    // Refresh every 30 seconds
    const interval = setInterval(fetchPriceHistory, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatPrice = (value) => `₹${value.toFixed(2)}`;
  const formatDemand = (value) => `${value.toFixed(0)} kW`;

  return (
    <div className="price-chart">
      {loading ? (
        <div className="chart-placeholder">
          <p>Loading price history...</p>
        </div>
      ) : priceData.length === 0 ? (
        <div className="chart-placeholder">
          <p>No price data available</p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={priceData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="time"
              stroke="#9CA3AF"
              tick={{ fill: '#9CA3AF', fontSize: 12 }}
            />
            <YAxis
              yAxisId="left"
              stroke="#10B981"
              tick={{ fill: '#9CA3AF', fontSize: 12 }}
              tickFormatter={formatPrice}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              stroke="#3B82F6"
              tick={{ fill: '#9CA3AF', fontSize: 12 }}
              tickFormatter={formatDemand}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '8px'
              }}
              labelStyle={{ color: '#F3F4F6' }}
              formatter={(value, name) => {
                if (name === 'price') return [`₹${value.toFixed(2)}/kWh`, 'Price'];
                return [`${value.toFixed(1)} kW`, 'Demand'];
              }}
            />
            <Legend />
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="price"
              stroke="#10B981"
              strokeWidth={2}
              dot={false}
              name="Price (₹/kWh)"
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey="demand"
              stroke="#3B82F6"
              strokeWidth={2}
              dot={false}
              name="Demand (kW)"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default PriceChart;
