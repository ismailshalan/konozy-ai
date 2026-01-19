'use client';

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

interface SalesData {
  date: string;
  sales: number;
  orders: number;
}

// Mock data for last 7 days
const mockSalesData: SalesData[] = [
  { date: '2025-01-07', sales: 4500, orders: 12 },
  { date: '2025-01-08', sales: 5200, orders: 15 },
  { date: '2025-01-09', sales: 4800, orders: 14 },
  { date: '2025-01-10', sales: 6100, orders: 18 },
  { date: '2025-01-11', sales: 5500, orders: 16 },
  { date: '2025-01-12', sales: 6700, orders: 20 },
  { date: '2025-01-13', sales: 7200, orders: 22 },
];

export default function SalesChart() {
  // Format date for display
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const formattedData = mockSalesData.map(item => ({
    ...item,
    date: formatDate(item.date),
  }));

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
        Sales Overview (Last 7 Days)
      </h2>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart
          data={formattedData}
          margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
        >
          <defs>
            <linearGradient id="colorSales" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
          <XAxis
            dataKey="date"
            className="text-gray-600 dark:text-gray-400"
            tick={{ fill: 'currentColor' }}
          />
          <YAxis
            className="text-gray-600 dark:text-gray-400"
            tick={{ fill: 'currentColor' }}
            tickFormatter={(value) => `$${value.toLocaleString()}`}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: 'rgba(255, 255, 255, 0.95)',
              border: '1px solid #e5e7eb',
              borderRadius: '0.5rem',
            }}
            formatter={(value: number) => [`$${value.toLocaleString()}`, 'Sales']}
          />
          <Area
            type="monotone"
            dataKey="sales"
            stroke="#3b82f6"
            fillOpacity={1}
            fill="url(#colorSales)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
