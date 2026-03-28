import { useFilterStore } from '../../stores';
import { useChoropleth } from '../../hooks/useMapData';
import type { ChoroplethMetric } from '../../types';

function getColor(value: number, min: number, max: number): string {
  if (max === min) return '#d1fae5';
  const t = (value - min) / (max - min);
  const r = Math.round(209 + (6 - 209) * t);
  const g = Math.round(250 + (95 - 250) * t);
  const b = Math.round(229 + (70 - 229) * t);
  return `rgb(${r},${g},${b})`;
}

const metricLabels: Record<ChoroplethMetric, string> = {
  net_assets: 'Net Assets',
  turnover: 'Turnover',
  total_assets: 'Total Assets',
  company_count: 'Company Count',
  coverage_pct: 'Coverage %',
};

export default function ChoroplethInfo() {
  const metric = useFilterStore((s) => s.metric);
  const { data, isLoading } = useChoropleth(metric);

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow-lg p-3 min-w-[140px]">
        <div className="text-xs font-semibold text-gray-700 mb-2">{metricLabels[metric]}</div>
        <div className="w-4 h-4 border-2 border-green-600 border-t-transparent rounded-full animate-spin mx-auto" />
      </div>
    );
  }

  if (!data) return null;

  const values = Object.values(data).map((d) => d.metric_value).filter((v) => v != null);
  if (values.length === 0) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);

  const formatValue = (v: number) => {
    if (metric === 'coverage_pct') return `${v.toFixed(0)}%`;
    if (metric === 'company_count') return v.toLocaleString('en-GB');
    return `£${v.toLocaleString('en-GB', { notation: 'compact', maximumFractionDigits: 1 })}`;
  };

  const steps = [1, 0.75, 0.5, 0.25, 0];

  return (
    <div className="bg-white rounded-lg shadow-lg p-3 min-w-[150px]">
      <div className="text-xs font-semibold text-gray-700 mb-2">{metricLabels[metric]}</div>
      <div className="flex flex-col gap-1">
        {steps.map((t) => {
          const v = min + t * (max - min);
          const color = getColor(v, min, max);
          return (
            <div key={t} className="flex items-center gap-2">
              <div
                className="w-4 h-3 rounded-sm border border-gray-200 flex-shrink-0"
                style={{ backgroundColor: color }}
              />
              <span className="text-xs text-gray-600">{formatValue(v)}</span>
            </div>
          );
        })}
      </div>
      <div className="border-t border-gray-100 mt-2 pt-2">
        <div className="text-xs text-gray-400">{Object.keys(data).length} districts</div>
      </div>
      <div className="border-t border-gray-100 mt-2 pt-2 space-y-1">
        <div className="text-xs font-medium text-gray-600">Markers</div>
        {[
          { color: '#22c55e', label: 'Accounts OK' },
          { color: '#f59e0b', label: 'Partial' },
          { color: '#9ca3af', label: 'No data' },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: color }}
            />
            <span className="text-xs text-gray-600">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
