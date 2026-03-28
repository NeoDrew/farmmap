import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { useMapStore, useUIStore } from '../../stores';
import { useCompanyDetail } from '../../hooks/useMapData';
import type { Account } from '../../types';

function formatGBP(value: number | null): string {
  if (value == null) return '—';
  return `£${Math.abs(value).toLocaleString('en-GB')}${value < 0 ? ' (loss)' : ''}`;
}

function formatGBPCompact(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';
  if (abs >= 1_000_000) return `${sign}£${(abs / 1_000_000).toFixed(1)}m`;
  if (abs >= 1_000) return `${sign}£${(abs / 1_000).toFixed(0)}k`;
  return `${sign}£${abs.toLocaleString('en-GB')}`;
}

function ParseStatusBadge({ status }: { status: string | null }) {
  const classes: Record<string, string> = {
    ok: 'bg-green-100 text-green-800 border-green-200',
    partial: 'bg-amber-100 text-amber-800 border-amber-200',
    failed: 'bg-red-100 text-red-800 border-red-200',
  };
  const key = status ?? 'failed';
  const cls = classes[key] ?? 'bg-gray-100 text-gray-600 border-gray-200';
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium border ${cls}`}>
      {status ?? 'none'}
    </span>
  );
}

function FinancialTimeline({ accounts }: { accounts: Account[] }) {
  const sorted = [...accounts].sort((a, b) => a.period_end.localeCompare(b.period_end));

  const chartData = sorted.map((a) => ({
    period: a.period_end.slice(0, 7),
    'Net Assets': a.net_assets,
    Turnover: a.turnover,
    'Total Assets': a.total_assets,
  }));

  const hasAnyData = sorted.some(
    (a) => a.net_assets != null || a.turnover != null || a.total_assets != null
  );

  if (!hasAnyData) {
    return (
      <div className="text-center py-6 text-gray-400 text-sm">
        No financial data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
        <XAxis
          dataKey="period"
          tick={{ fontSize: 10, fill: '#9ca3af' }}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v) => formatGBPCompact(v)}
          tick={{ fontSize: 10, fill: '#9ca3af' }}
          tickLine={false}
          axisLine={false}
          width={60}
        />
        <Tooltip
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(value: any) => [typeof value === 'number' ? formatGBP(value) : String(value ?? '')]}
          contentStyle={{
            backgroundColor: '#1f2937',
            border: '1px solid #374151',
            borderRadius: '6px',
            fontSize: '12px',
            color: '#f3f4f6',
          }}
          labelStyle={{ color: '#d1d5db' }}
        />
        <Legend wrapperStyle={{ fontSize: '11px', color: '#9ca3af' }} />
        <Bar dataKey="Net Assets" fill="#3b82f6" radius={[2, 2, 0, 0]} maxBarSize={20} />
        <Bar dataKey="Turnover" fill="#10b981" radius={[2, 2, 0, 0]} maxBarSize={20} />
        <Bar dataKey="Total Assets" fill="#8b5cf6" radius={[2, 2, 0, 0]} maxBarSize={20} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function AccountsTable({ accounts }: { accounts: Account[] }) {
  const sorted = [...accounts].sort((a, b) => b.period_end.localeCompare(a.period_end));

  if (sorted.length === 0) {
    return (
      <div className="text-center py-4 text-gray-400 text-sm">No accounts data available</div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left py-2 pr-3 text-gray-400 font-medium">Period</th>
            <th className="text-right py-2 pr-3 text-gray-400 font-medium">Net Assets</th>
            <th className="text-right py-2 pr-3 text-gray-400 font-medium">Turnover</th>
            <th className="text-right py-2 text-gray-400 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((a) => (
            <tr key={a.id} className="border-b border-gray-800 hover:bg-gray-800/50">
              <td className="py-2 pr-3 text-gray-300 font-mono">{a.period_end.slice(0, 10)}</td>
              <td className="py-2 pr-3 text-right text-gray-300">
                {formatGBP(a.net_assets)}
              </td>
              <td className="py-2 pr-3 text-right text-gray-300">
                {formatGBP(a.turnover)}
              </td>
              <td className="py-2 text-right">
                <ParseStatusBadge status={a.parse_status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function CompanyPanel() {
  const selectedCompany = useMapStore((s) => s.selectedCompany);
  const selectCompany = useMapStore((s) => s.selectCompany);
  const panelOpen = useUIStore((s) => s.panelOpen);
  const closePanel = useUIStore((s) => s.closePanel);

  const { data: company, isLoading, error } = useCompanyDetail(selectedCompany);

  const handleClose = () => {
    closePanel();
    selectCompany(null);
  };

  const addressLines = company?.registered_address
    ? Object.values(company.registered_address).filter(Boolean)
    : [];

  return (
    <div
      className={`fixed top-0 right-0 h-full w-96 bg-gray-900 shadow-2xl z-[1001] flex flex-col transition-transform duration-300 ease-in-out ${
        panelOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between px-5 py-4 bg-gray-800 border-b border-gray-700 flex-shrink-0">
        <div className="flex-1 min-w-0 mr-3">
          {isLoading ? (
            <div className="space-y-2">
              <div className="h-4 bg-gray-700 rounded animate-pulse w-3/4" />
              <div className="h-3 bg-gray-700 rounded animate-pulse w-1/2" />
            </div>
          ) : company ? (
            <>
              <h2 className="text-sm font-semibold text-white leading-tight truncate">
                {company.company_name}
              </h2>
              <div className="text-xs text-gray-400 mt-0.5">{company.company_number}</div>
            </>
          ) : (
            <div className="text-sm text-gray-400">No company selected</div>
          )}
        </div>
        <button
          onClick={handleClose}
          className="flex-shrink-0 text-gray-400 hover:text-white transition-colors p-1"
          aria-label="Close panel"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center h-32">
            <div className="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : error ? (
          <div className="px-5 py-4 text-red-400 text-sm">
            Failed to load company data. Please try again.
          </div>
        ) : company ? (
          <div className="flex flex-col gap-0">
            {/* Company info */}
            <div className="px-5 py-4 border-b border-gray-700">
              <div className="space-y-2">
                {company.status && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">Status</span>
                    <span className="text-xs font-medium text-gray-200 capitalize">{company.status}</span>
                  </div>
                )}
                {addressLines.length > 0 && (
                  <div>
                    <span className="text-xs text-gray-400 block mb-1">Address</span>
                    <div className="text-xs text-gray-300 leading-relaxed">
                      {addressLines.join(', ')}
                    </div>
                  </div>
                )}
                {company.postcode && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">Postcode</span>
                    <span className="text-xs font-mono text-gray-200">{company.postcode}</span>
                  </div>
                )}
                {company.sic_codes && company.sic_codes.length > 0 && (
                  <div>
                    <span className="text-xs text-gray-400 block mb-1">SIC Codes</span>
                    <div className="flex flex-wrap gap-1">
                      {company.sic_codes.map((code) => (
                        <span
                          key={code}
                          className="inline-flex items-center px-1.5 py-0.5 rounded bg-gray-700 text-gray-300 text-xs font-mono"
                        >
                          {code}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {company.last_accounts_date && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">Last Accounts</span>
                    <span className="text-xs text-gray-200">{company.last_accounts_date.slice(0, 10)}</span>
                  </div>
                )}
                {company.next_accounts_due && (
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">Next Due</span>
                    <span className="text-xs text-gray-200">{company.next_accounts_due.slice(0, 10)}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Latest financials */}
            <div className="px-5 py-4 border-b border-gray-700">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Latest Financials
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Net Assets', value: company.net_assets },
                  { label: 'Turnover', value: company.turnover },
                  { label: 'Total Assets', value: company.total_assets },
                ].map(({ label, value }) => (
                  <div key={label} className="bg-gray-800 rounded-lg p-2.5">
                    <div className="text-xs text-gray-400 mb-1">{label}</div>
                    <div className="text-xs font-semibold text-white truncate">
                      {value != null ? formatGBPCompact(value) : '—'}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Financial timeline chart */}
            {company.accounts.length > 0 && (
              <div className="px-5 py-4 border-b border-gray-700">
                <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                  Financial History
                </div>
                <FinancialTimeline accounts={company.accounts} />
              </div>
            )}

            {/* Accounts table */}
            <div className="px-5 py-4 border-b border-gray-700">
              <div className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                Filed Accounts ({company.accounts.length})
              </div>
              <AccountsTable accounts={company.accounts} />
            </div>

            {/* External link */}
            <div className="px-5 py-4">
              <a
                href={`https://find-and-update.company-information.service.gov.uk/company/${company.company_number}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-center gap-2 w-full py-2.5 px-4 bg-blue-700 hover:bg-blue-600 text-white text-sm font-medium rounded-lg transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
                View on Companies House
              </a>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
