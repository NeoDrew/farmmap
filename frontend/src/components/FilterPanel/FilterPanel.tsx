import { useState } from 'react';
import { useFilterStore } from '../../stores';
import type { ChoroplethMetric } from '../../types';

const METRIC_OPTIONS: { value: ChoroplethMetric; label: string }[] = [
  { value: 'net_assets', label: 'Net Assets' },
  { value: 'turnover', label: 'Turnover' },
  { value: 'total_assets', label: 'Total Assets' },
  { value: 'company_count', label: 'Company Count' },
  { value: 'coverage_pct', label: 'Coverage %' },
];

const SIC_PRESETS = [
  { code: '01', label: 'Crops & Farming' },
  { code: '0111', label: 'Cereal crops' },
  { code: '0112', label: 'Leguminous crops' },
  { code: '0113', label: 'Rice' },
  { code: '0119', label: 'Other crops' },
  { code: '0121', label: 'Grapes' },
  { code: '0122', label: 'Tropical fruits' },
  { code: '0124', label: 'Apples & pears' },
  { code: '0125', label: 'Other tree fruits' },
  { code: '0130', label: 'Plant propagation' },
  { code: '0141', label: 'Dairy cattle' },
  { code: '0142', label: 'Other cattle' },
  { code: '0143', label: 'Horses' },
  { code: '0145', label: 'Sheep & goats' },
  { code: '0146', label: 'Pigs' },
  { code: '0147', label: 'Poultry' },
  { code: '0150', label: 'Mixed farming' },
];

export default function FilterPanel() {
  const { hasAccounts, sicFilter, metric, setHasAccounts, setSicFilter, setMetric } =
    useFilterStore();
  const [collapsed, setCollapsed] = useState(false);

  const toggleSic = (code: string) => {
    if (sicFilter.includes(code)) {
      setSicFilter(sicFilter.filter((c) => c !== code));
    } else {
      setSicFilter([...sicFilter, code]);
    }
  };

  return (
    <div className="bg-gray-900 text-white rounded-xl shadow-2xl overflow-hidden w-64 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-800 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-400" />
          <span className="text-sm font-semibold tracking-wide">FarmMap Filters</span>
        </div>
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="text-gray-400 hover:text-white transition-colors"
          aria-label={collapsed ? 'Expand filters' : 'Collapse filters'}
        >
          <svg
            className={`w-4 h-4 transition-transform ${collapsed ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
        </button>
      </div>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto max-h-[calc(100vh-200px)]">
          {/* Accounts filter */}
          <div className="px-4 py-3 border-b border-gray-700">
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Accounts Filed
            </div>
            <div className="flex gap-2">
              {[
                { value: null, label: 'All' },
                { value: true, label: 'Yes' },
                { value: false, label: 'No' },
              ].map(({ value, label }) => (
                <button
                  key={label}
                  onClick={() => setHasAccounts(value)}
                  className={`flex-1 py-1.5 text-xs rounded-md font-medium transition-colors ${
                    hasAccounts === value
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Choropleth metric */}
          <div className="px-4 py-3 border-b border-gray-700">
            <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
              Map Metric
            </div>
            <div className="flex flex-col gap-1">
              {METRIC_OPTIONS.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => setMetric(value)}
                  className={`text-left px-3 py-1.5 text-sm rounded-md transition-colors ${
                    metric === value
                      ? 'bg-green-700 text-green-100 font-medium'
                      : 'text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* SIC code filter */}
          <div className="px-4 py-3">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
                SIC Codes
              </div>
              {sicFilter.length > 0 && (
                <button
                  onClick={() => setSicFilter([])}
                  className="text-xs text-red-400 hover:text-red-300 transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
            <div className="flex flex-col gap-1 max-h-64 overflow-y-auto pr-1">
              {SIC_PRESETS.map(({ code, label }) => (
                <label
                  key={code}
                  className="flex items-center gap-2 cursor-pointer group"
                >
                  <input
                    type="checkbox"
                    checked={sicFilter.includes(code)}
                    onChange={() => toggleSic(code)}
                    className="w-3.5 h-3.5 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-0 focus:ring-offset-0"
                  />
                  <span
                    className={`text-xs transition-colors ${
                      sicFilter.includes(code)
                        ? 'text-blue-300 font-medium'
                        : 'text-gray-400 group-hover:text-gray-200'
                    }`}
                  >
                    <span className="font-mono">{code}</span> {label}
                  </span>
                </label>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
