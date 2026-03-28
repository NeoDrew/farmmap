import { useQuery } from '@tanstack/react-query';
import type { BBox, ChoroplethData, ChoroplethMetric, CompanyDetail, PipelineStatus, ViewportStats } from '../types';

// In production on Render, VITE_API_URL is set to the backend service URL.
// In local dev, the Vite proxy forwards /api → localhost:8000.
const BASE = (import.meta.env.VITE_API_URL ?? '') + '/api';

function bboxParams(bbox: BBox) {
  const [west, south, east, north] = bbox;
  return new URLSearchParams({ west: String(west), south: String(south), east: String(east), north: String(north) });
}

export function useMapPoints(bbox: BBox | null, filters: { hasAccounts: boolean | null; sicFilter: string[] }) {
  return useQuery({
    queryKey: ['map-points', bbox, filters],
    queryFn: async () => {
      if (!bbox) return null;
      const params = bboxParams(bbox);
      if (filters.hasAccounts !== null) {
        params.set('has_accounts', String(filters.hasAccounts));
      }
      if (filters.sicFilter.length > 0) {
        params.set('sic', filters.sicFilter.join(','));
      }
      const res = await fetch(`${BASE}/map/points?${params}`);
      if (!res.ok) throw new Error('Failed to fetch map points');
      return res.json() as Promise<GeoJSON.FeatureCollection>;
    },
    enabled: bbox !== null,
    staleTime: 30_000,
  });
}

export function useChoropleth(metric: ChoroplethMetric) {
  return useQuery({
    queryKey: ['choropleth', metric],
    queryFn: async () => {
      const params = new URLSearchParams({ metric });
      const res = await fetch(`${BASE}/map/choropleth?${params}`);
      if (!res.ok) throw new Error('Failed to fetch choropleth');
      return res.json() as Promise<ChoroplethData>;
    },
    staleTime: 60_000,
  });
}

export function useCompanyDetail(companyNumber: string | null) {
  return useQuery({
    queryKey: ['company', companyNumber],
    queryFn: async () => {
      const res = await fetch(`${BASE}/companies/${companyNumber}`);
      if (!res.ok) throw new Error('Failed to fetch company detail');
      return res.json() as Promise<CompanyDetail>;
    },
    enabled: companyNumber !== null,
    staleTime: 120_000,
  });
}

export function useViewportStats(bbox: BBox | null) {
  return useQuery({
    queryKey: ['viewport-stats', bbox],
    queryFn: async () => {
      if (!bbox) return null;
      const params = bboxParams(bbox);
      const res = await fetch(`${BASE}/stats/summary?${params}`);
      if (!res.ok) throw new Error('Failed to fetch viewport stats');
      return res.json() as Promise<ViewportStats>;
    },
    enabled: bbox !== null,
    staleTime: 30_000,
  });
}

export function usePipelineStatus() {
  return useQuery({
    queryKey: ['pipeline-status'],
    queryFn: async () => {
      const res = await fetch(`${BASE}/pipeline/status`);
      if (!res.ok) throw new Error('Failed to fetch pipeline status');
      return res.json() as Promise<PipelineStatus>;
    },
    staleTime: 300_000,
    refetchInterval: 300_000,
  });
}
