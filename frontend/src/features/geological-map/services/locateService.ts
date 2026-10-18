import { request } from '../../../api/apiClient';
import { GeoJsonGeometry, LocateResponse } from '../../../types/api.types';

export const locatePlace = (name: string, signal?: AbortSignal) =>
  request<LocateResponse>(`/map/locate?name=${encodeURIComponent(name)}`, { signal });

const collectPositions = (value: unknown, out: [number, number][]): void => {
  if (!Array.isArray(value)) return;
  if (value.length >= 2 && typeof value[0] === 'number' && typeof value[1] === 'number') {
    out.push([value[0], value[1]]);
    return;
  }
  value.forEach((child) => collectPositions(child, out));
};

// Bounding-box center as [lat, lng]; GeoJSON positions are [lng, lat].
export const geometryCenter = (geometry: GeoJsonGeometry | null): [number, number] | null => {
  if (!geometry) return null;
  const positions: [number, number][] = [];
  if (geometry.type === 'GeometryCollection') {
    geometry.geometries?.forEach((g) => collectPositions(g.coordinates, positions));
  } else {
    collectPositions(geometry.coordinates, positions);
  }
  if (!positions.length) return null;
  const lngs = positions.map((p) => p[0]);
  const lats = positions.map((p) => p[1]);
  return [(Math.min(...lats) + Math.max(...lats)) / 2, (Math.min(...lngs) + Math.max(...lngs)) / 2];
};
