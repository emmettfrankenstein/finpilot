import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import type { AllocationSlice } from '../api/types';
import { humanize, money, percent } from '../lib/format';

const COLORS: Record<string, string> = {
  EQUITY: '#2f6fd0',
  ETF: '#1aa189',
  MUTUAL_FUND: '#8a5cd6',
  BOND: '#e0962b',
  REIT: '#d1527a',
  GSEC: '#5b7083',
};

/** Donut chart plus a data table that doubles as the legend and the accessible alternative. */
export function AllocationChart({ data }: { data: AllocationSlice[] }) {
  const chartData = data.map((d) => ({ name: humanize(d.asset_class), key: d.asset_class, value: Number(d.market_value), weight: d.weight_pct }));
  return (
    <div className="allocation">
      <div className="allocation-chart" aria-hidden="true">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={chartData} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95} paddingAngle={1} isAnimationActive={false}>
              {chartData.map((d) => (
                <Cell key={d.key} fill={COLORS[d.key] ?? '#999'} />
              ))}
            </Pie>
            <Tooltip formatter={(value, _name, item) => [`${money(String(value))} (${percent(item.payload.weight)})`, item.payload.name]} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <table className="table compact">
        <caption className="visually-hidden">Asset allocation by market value</caption>
        <thead>
          <tr>
            <th scope="col">Asset class</th>
            <th scope="col" className="num">Value</th>
            <th scope="col" className="num">Weight</th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.asset_class}>
              <th scope="row">
                <span className="swatch" style={{ background: COLORS[d.asset_class] ?? '#999' }} aria-hidden="true" />
                {humanize(d.asset_class)}
              </th>
              <td className="num">{money(d.market_value)}</td>
              <td className="num">{percent(d.weight_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
