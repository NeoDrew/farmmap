import { create } from 'zustand';
import type { BBox, ChoroplethMetric } from '../types';

// Map store
interface MapState {
  bbox: BBox | null;
  zoom: number;
  selectedCompany: string | null;
  setBbox: (bbox: BBox) => void;
  setZoom: (zoom: number) => void;
  selectCompany: (companyNumber: string | null) => void;
}

export const useMapStore = create<MapState>((set) => ({
  bbox: null,
  zoom: 7,
  selectedCompany: null,
  setBbox: (bbox) => set({ bbox }),
  setZoom: (zoom) => set({ zoom }),
  selectCompany: (selectedCompany) => set({ selectedCompany }),
}));

// Filter store
interface FilterState {
  hasAccounts: boolean | null;
  sicFilter: string[];
  metric: ChoroplethMetric;
  setHasAccounts: (hasAccounts: boolean | null) => void;
  setSicFilter: (sicFilter: string[]) => void;
  setMetric: (metric: ChoroplethMetric) => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  hasAccounts: null,
  sicFilter: [],
  metric: 'net_assets',
  setHasAccounts: (hasAccounts) => set({ hasAccounts }),
  setSicFilter: (sicFilter) => set({ sicFilter }),
  setMetric: (metric) => set({ metric }),
}));

// UI store
interface UIState {
  panelOpen: boolean;
  openPanel: () => void;
  closePanel: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  panelOpen: false,
  openPanel: () => set({ panelOpen: true }),
  closePanel: () => set({ panelOpen: false }),
}));
