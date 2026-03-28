export interface CompanySummary {
  company_number: string;
  company_name: string;
  lat: number | null;
  lng: number | null;
  sic_codes: string[] | null;
  postcode: string | null;
  last_accounts_date: string | null;
  geocode_quality: string | null;
  net_assets: number | null;
  total_assets: number | null;
  turnover: number | null;
  parse_status: string | null;
}

export interface Account {
  id: number;
  period_end: string;
  parse_source: string | null;
  parse_status: string | null;
  turnover: number | null;
  total_assets: number | null;
  net_assets: number | null;
  total_liabilities: number | null;
  employees: number | null;
  raw_filing_url: string | null;
}

export interface CompanyDetail extends CompanySummary {
  status: string | null;
  registered_address: Record<string, string> | null;
  next_accounts_due: string | null;
  accounts: Account[];
}

export interface ViewportStats {
  total_companies: number;
  companies_with_accounts: number;
  accounts_ok: number;
  accounts_partial: number;
  accounts_failed: number;
  median_net_assets: number | null;
  median_turnover: number | null;
  median_total_assets: number | null;
}

export interface PipelineStatus {
  last_run_at: string | null;
  last_run_status: string | null;
  total_companies: number;
  companies_with_accounts: number;
  parse_ok: number;
  parse_partial: number;
  parse_failed: number;
  coverage_pct: number;
}

export type BBox = [number, number, number, number]; // [west, south, east, north]

export type ChoroplethMetric =
  | 'net_assets'
  | 'turnover'
  | 'total_assets'
  | 'company_count'
  | 'coverage_pct';

export interface ChoroplethDistrict {
  metric_value: number;
  company_count: number;
  accounts_count: number;
  coverage_pct: number;
}

export type ChoroplethData = Record<string, ChoroplethDistrict>;
