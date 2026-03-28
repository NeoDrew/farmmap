import { useMapStore } from '../stores';
import { useViewportStats, usePipelineStatus } from '../hooks/useMapData';

function formatGBP(value: number | null): string {
  if (value == null) return '—';
  if (Math.abs(value) >= 1_000_000) return `£${(value / 1_000_000).toFixed(1)}m`;
  if (Math.abs(value) >= 1_000) return `£${(value / 1_000).toFixed(0)}k`;
  return `£${value.toLocaleString('en-GB')}`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return 'Never';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function ViewportStats() {
  const bbox = useMapStore((s) => s.bbox);
  const { data: stats, isLoading: statsLoading } = useViewportStats(bbox);
  const { data: pipeline } = usePipelineStatus();

  const coveragePct =
    stats && stats.total_companies > 0
      ? ((stats.companies_with_accounts / stats.total_companies) * 100).toFixed(0)
      : null;

  const pipelineOk =
    pipeline?.last_run_status === 'success' || pipeline?.last_run_status === 'ok';

  return (
    <div className="flex items-center gap-3 px-4 py-2 bg-gray-900/95 backdrop-blur-sm text-white text-sm flex-shrink-0 flex-wrap">
      {/* Logo / title */}
      <div className="flex items-center gap-2 mr-2">
        <div className="w-2 h-2 rounded-full bg-green-400" />
        <span className="font-semibold text-gray-100 text-xs tracking-wider uppercase">FarmMap</span>
      </div>

      <div className="h-4 w-px bg-gray-700" />

      {statsLoading ? (
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 border border-gray-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-xs text-gray-400">Loading viewport...</span>
        </div>
      ) : stats ? (
        <>
          <StatItem label="Companies" value={stats.total_companies.toLocaleString('en-GB')} />
          <div className="h-4 w-px bg-gray-700" />
          <StatItem
            label="With Accounts"
            value={stats.companies_with_accounts.toLocaleString('en-GB')}
          />
          <div className="h-4 w-px bg-gray-700" />
          <StatItem
            label="Coverage"
            value={coveragePct != null ? `${coveragePct}%` : '—'}
            highlight={coveragePct != null && Number(coveragePct) >= 60}
          />
          <div className="h-4 w-px bg-gray-700" />
          <StatItem label="Median Net Assets" value={formatGBP(stats.median_net_assets)} />
          <div className="h-4 w-px bg-gray-700" />
          <StatItem label="Median Turnover" value={formatGBP(stats.median_turnover)} />
        </>
      ) : (
        <span className="text-xs text-gray-500">Pan or zoom the map to load stats</span>
      )}

      <div className="ml-auto flex items-center gap-2">
        {pipeline ? (
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
              pipelineOk
                ? 'bg-green-900/60 text-green-300 border border-green-800'
                : pipeline.last_run_status
                ? 'bg-red-900/60 text-red-300 border border-red-800'
                : 'bg-gray-700 text-gray-400 border border-gray-600'
            }`}
          >
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                pipelineOk ? 'bg-green-400' : pipeline.last_run_status ? 'bg-red-400' : 'bg-gray-500'
              }`}
            />
            Pipeline: {pipeline.last_run_status ?? 'unknown'}
            {pipeline.last_run_at && (
              <span className="text-xs opacity-70 ml-1">
                {formatDate(pipeline.last_run_at)}
              </span>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function StatItem({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-xs text-gray-400">{label}</span>
      <span className={`text-xs font-semibold ${highlight ? 'text-green-400' : 'text-gray-100'}`}>
        {value}
      </span>
    </div>
  );
}
