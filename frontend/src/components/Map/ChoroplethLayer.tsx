import { useChoropleth } from '../../hooks/useMapData';
import type { ChoroplethMetric } from '../../types';

// Color scale from light to dark green for choropleth
function getColor(value: number, min: number, max: number): string {
  if (max === min) return '#d1fae5';
  const t = (value - min) / (max - min);
  // Interpolate from light green to dark green
  const r = Math.round(209 + (6 - 209) * t);
  const g = Math.round(250 + (95 - 250) * t);
  const b = Math.round(229 + (70 - 229) * t);
  return `rgb(${r},${g},${b})`;
}

interface Props {
  metric: ChoroplethMetric;
}

// This component renders a legend overlay for the choropleth
// The actual choropleth district rendering would require district GeoJSON boundary data
// which is fetched from the backend. For now, this renders the color scale legend.
export default function ChoroplethLayer({ metric }: Props) {
  const { data } = useChoropleth(metric);

  if (!data) return null;

  const values = Object.values(data).map((d) => d.metric_value).filter((v) => v != null);
  const min = Math.min(...values);
  const max = Math.max(...values);

  const metricLabels: Record<ChoroplethMetric, string> = {
    net_assets: 'Net Assets',
    turnover: 'Turnover',
    total_assets: 'Total Assets',
    company_count: 'Company Count',
    coverage_pct: 'Coverage %',
  };

  const formatValue = (v: number) => {
    if (metric === 'coverage_pct') return `${v.toFixed(0)}%`;
    if (metric === 'company_count') return v.toLocaleString('en-GB');
    return `£${v.toLocaleString('en-GB', { notation: 'compact', maximumFractionDigits: 1 })}`;
  };

  return (
    <div className="leaflet-bottom leaflet-right" style={{ position: 'absolute', bottom: '24px', right: '10px', zIndex: 1000 }}>
      <div className="leaflet-control bg-white rounded-lg shadow-lg p-3 min-w-[140px]">
        <div className="text-xs font-semibold text-gray-700 mb-2">{metricLabels[metric]}</div>
        <div className="flex flex-col gap-1">
          {[1, 0.75, 0.5, 0.25, 0].map((t) => {
            const v = min + t * (max - min);
            const color = getColor(v, min, max);
            return (
              <div key={t} className="flex items-center gap-2">
                <div
                  className="w-4 h-3 rounded-sm border border-gray-200"
                  style={{ backgroundColor: color }}
                />
                <span className="text-xs text-gray-600">{formatValue(v)}</span>
              </div>
            );
          })}
        </div>
        <div className="text-xs text-gray-400 mt-2">{Object.keys(data).length} districts</div>
      </div>
    </div>
  );
}
