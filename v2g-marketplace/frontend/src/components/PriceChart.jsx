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

function PriceChart() {
  const [priceData, setPriceData] = useState([]);

  useEffect(() => {
    // Generate sample price data for demonstration
    const generateSampleData = () => {
      const data = [];
      const now = new Date();
      for (let i = 23; i >= 0; i--) {
        const time = new Date(now - i * 60 * 60 * 1000);
        const basePrice = 0.12;
        const variation = Math.sin((24 - i) / 24 * Math.PI * 2) * 0.04;
        const noise = (Math.random() - 0.5) * 0.02;
        data.push({
          time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
          price: basePrice + variation + noise,
          demand: 50 + Math.sin((24 - i) / 24 * Math.PI * 2) * 30 + Math.random() * 10,
        });
      }
      return data;
    };

    setPriceData(generateSampleData());
  }, []);

  const formatPrice = (value) => `$${value.toFixed(3)}`;
  const formatDemand = (value) => `${value.toFixed(0)} kW`;

  return (
    <div className="price-chart">
      {priceData.length === 0 ? (
        <div className="chart-placeholder">
          <p>Loading chart data...</p>
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
                if (name === 'price') return [`$${value.toFixed(4)}/kWh`, 'Price'];
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
              name="Price ($/kWh)"
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
