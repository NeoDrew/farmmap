import { useEffect, useRef, useCallback } from 'react';
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
  useMapEvents,
} from 'react-leaflet';
import type { Map as LeafletMap } from 'leaflet';
import { useMapStore, useFilterStore, useUIStore } from '../../stores';
import { useMapPoints } from '../../hooks/useMapData';
import type { BBox } from '../../types';
import ChoroplethLayer from './ChoroplethLayer';

function parseStatus(status: string | null): string {
  if (status === 'ok') return '#22c55e';
  if (status === 'partial') return '#f59e0b';
  return '#9ca3af';
}

function MapEventHandler() {
  const setBbox = useMapStore((s) => s.setBbox);
  const setZoom = useMapStore((s) => s.setZoom);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const updateBounds = useCallback(
    (map: LeafletMap) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        const bounds = map.getBounds();
        const bbox: BBox = [
          bounds.getWest(),
          bounds.getSouth(),
          bounds.getEast(),
          bounds.getNorth(),
        ];
        setBbox(bbox);
        setZoom(map.getZoom());
      }, 300);
    },
    [setBbox, setZoom]
  );

  const map = useMapEvents({
    moveend: () => updateBounds(map),
    zoomend: () => updateBounds(map),
    load: () => updateBounds(map),
  });

  useEffect(() => {
    // Fire once on mount
    updateBounds(map);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [map, updateBounds]);

  return null;
}

interface ClusterPoint {
  lat: number;
  lng: number;
  count: number;
  color: string;
}

function ClusterLayer({ features }: { features: GeoJSON.Feature[] }) {
  // Simple grid-based clustering
  const GRID_SIZE = 0.5; // degrees
  const clusters = new Map<string, ClusterPoint>();

  for (const f of features) {
    if (f.geometry.type !== 'Point') continue;
    const [lng, lat] = (f.geometry as GeoJSON.Point).coordinates;
    const key = `${Math.floor(lat / GRID_SIZE)},${Math.floor(lng / GRID_SIZE)}`;
    const status = (f.properties as { parse_status?: string | null })?.parse_status ?? null;
    if (!clusters.has(key)) {
      clusters.set(key, {
        lat: Math.floor(lat / GRID_SIZE) * GRID_SIZE + GRID_SIZE / 2,
        lng: Math.floor(lng / GRID_SIZE) * GRID_SIZE + GRID_SIZE / 2,
        count: 0,
        color: parseStatus(status),
      });
    }
    clusters.get(key)!.count++;
  }

  return (
    <>
      {Array.from(clusters.values()).map((c, i) => (
        <CircleMarker
          key={i}
          center={[c.lat, c.lng]}
          radius={Math.min(6 + Math.sqrt(c.count) * 2, 30)}
          pathOptions={{
            color: '#1e40af',
            fillColor: '#3b82f6',
            fillOpacity: 0.6,
            weight: 1,
          }}
        >
          <Popup>
            <div className="text-sm font-medium">{c.count} companies</div>
          </Popup>
        </CircleMarker>
      ))}
    </>
  );
}

function CompanyMarkerLayer({ features }: { features: GeoJSON.Feature[] }) {
  const selectCompany = useMapStore((s) => s.selectCompany);
  const openPanel = useUIStore((s) => s.openPanel);

  return (
    <>
      {features.map((f, i) => {
        if (f.geometry.type !== 'Point') return null;
        const [lng, lat] = (f.geometry as GeoJSON.Point).coordinates;
        const props = f.properties as {
          company_number?: string;
          company_name?: string;
          parse_status?: string | null;
        };
        const color = parseStatus(props.parse_status ?? null);
        return (
          <CircleMarker
            key={props.company_number ?? i}
            center={[lat, lng]}
            radius={6}
            pathOptions={{
              color: color,
              fillColor: color,
              fillOpacity: 0.8,
              weight: 1.5,
            }}
            eventHandlers={{
              click: () => {
                if (props.company_number) {
                  selectCompany(props.company_number);
                  openPanel();
                }
              },
            }}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-semibold">{props.company_name}</div>
                <div className="text-gray-500 text-xs">{props.company_number}</div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </>
  );
}

export default function MapView() {
  const bbox = useMapStore((s) => s.bbox);
  const zoom = useMapStore((s) => s.zoom);
  const { hasAccounts, sicFilter, metric } = useFilterStore();
  const { data: pointsData, isLoading } = useMapPoints(bbox, { hasAccounts, sicFilter });

  const features = pointsData?.features ?? [];

  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={[52.5, -1.5]}
        zoom={7}
        style={{ width: '100%', height: '100%' }}
        zoomControl={true}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          maxZoom={19}
        />
        <MapEventHandler />
        <ChoroplethLayer metric={metric} />
        {features.length > 0 && zoom > 12 ? (
          <CompanyMarkerLayer features={features} />
        ) : features.length > 0 ? (
          <ClusterLayer features={features} />
        ) : null}
      </MapContainer>

      {isLoading && (
        <div className="absolute top-4 right-4 z-[1000] bg-white rounded-lg shadow-lg px-3 py-2 flex items-center gap-2">
          <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-gray-600">Loading...</span>
        </div>
      )}
    </div>
  );
}
