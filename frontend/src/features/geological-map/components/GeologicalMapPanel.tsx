import React, { useEffect, useRef, useState } from 'react';
import {
  Map as MapLibreMap,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type GeoJSONSource,
  type MapMouseEvent
} from 'maplibre-gl';
import type { StyleSpecification } from '@maplibre/maplibre-gl-style-spec';
import type { FeatureCollection, Geometry } from 'geojson';
import 'maplibre-gl/dist/maplibre-gl.css';
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
import { Map as MapIcon, Search, Loader2, X, ExternalLink, Layers, Crosshair, Globe2 } from 'lucide-react';
import { useLanguage } from '../../../i18n/useLanguage';
import { ApiError } from '../../../api/apiClient';
import { GeoJsonGeometry, EntityKind, LocateResponse, UiContext } from '../../../types/api.types';
import { locatePlace } from '../services/locateService';
import { GeologicUnit, identifyUnit, SGC_ATTRIBUTION, SGC_EXPORT_TILES } from '../services/sgcService';
import { EntityCard } from '../../../components/EntityCard/EntityCard';

interface GeologicalMapPanelProps {
  onInvestigateFeature?: (question: string, uiContext?: UiContext) => void;
}

// MapLibre finds its worker next to its own module, which Vite moves when it
// pre-bundles dependencies; let Vite bundle the worker and pass its URL.
setWorkerUrl(maplibreWorkerUrl);

type Bounds = [[number, number], [number, number]];

const VMM_BOUNDS: Bounds = [[-75.4, 5.2], [-72.8, 8.9]];
const COLOMBIA_BOUNDS: Bounds = [[-79.1, -4.3], [-66.8, 12.6]];
const EMPTY: FeatureCollection = { type: 'FeatureCollection', features: [] };

const STYLE: StyleSpecification = {
  version: 8,
  sources: {
    basemap: {
      type: 'raster',
      // CARTO raster tiles now answer every request with an "API KEY REQUIRED" image.
      tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}'],
      tileSize: 256,
      maxzoom: 19,
      attribution: 'Tiles © <a href="https://www.esri.com/">Esri</a> — Esri, HERE, Garmin, FAO, NOAA, USGS, © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    },
    sgc: { type: 'raster', tiles: [SGC_EXPORT_TILES], tileSize: 256, attribution: SGC_ATTRIBUTION },
    located: { type: 'geojson', data: EMPTY },
    clicked: { type: 'geojson', data: EMPTY }
  },
  layers: [
    { id: 'basemap', type: 'raster', source: 'basemap' },
    { id: 'sgc', type: 'raster', source: 'sgc', paint: { 'raster-opacity': 0.7 } },
    { id: 'located-fill', type: 'fill', source: 'located', filter: ['==', ['geometry-type'], 'Polygon'],
      paint: { 'fill-color': '#2F7D32', 'fill-opacity': 0.18 } },
    { id: 'located-line', type: 'line', source: 'located', filter: ['!=', ['geometry-type'], 'Point'],
      paint: { 'line-color': '#24180F', 'line-width': 2.5 } },
    { id: 'located-point', type: 'circle', source: 'located', filter: ['==', ['geometry-type'], 'Point'],
      paint: { 'circle-radius': 7, 'circle-color': '#2F7D32', 'circle-stroke-color': '#F2E8D5', 'circle-stroke-width': 2 } },
    { id: 'clicked-point', type: 'circle', source: 'clicked',
      paint: { 'circle-radius': 5, 'circle-color': '#D9B36C', 'circle-stroke-color': '#24180F', 'circle-stroke-width': 2 } }
  ]
};

const positions = (geometry: GeoJsonGeometry): [number, number][] => {
  const out: [number, number][] = [];
  const walk = (value: unknown) => {
    if (!Array.isArray(value)) return;
    if (value.length >= 2 && typeof value[0] === 'number' && typeof value[1] === 'number') {
      out.push([value[0], value[1]]);
      return;
    }
    value.forEach(walk);
  };
  if (geometry.type === 'GeometryCollection') geometry.geometries?.forEach((g) => walk(g.coordinates));
  else walk(geometry.coordinates);
  return out;
};

const feature = (geometry: GeoJsonGeometry): FeatureCollection => ({
  type: 'FeatureCollection',
  features: [{ type: 'Feature', properties: {}, geometry: geometry as Geometry }]
});

export const GeologicalMapPanel: React.FC<GeologicalMapPanelProps> = ({ onInvestigateFeature }) => {
  const { language, t } = useLanguage();
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const identifyAbort = useRef<AbortController | null>(null);
  const locateAbort = useRef<AbortController | null>(null);

  const [geologyOn, setGeologyOn] = useState(true);
  const [opacity, setOpacity] = useState(0.7);
  const [query, setQuery] = useState('');
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState<string | null>(null);
  const [located, setLocated] = useState<LocateResponse | null>(null);
  const [unit, setUnit] = useState<GeologicUnit | null>(null);
  const [identifying, setIdentifying] = useState(false);
  const [identifyError, setIdentifyError] = useState<string | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new MapLibreMap({
      container: containerRef.current,
      style: STYLE,
      bounds: VMM_BOUNDS,
      attributionControl: { compact: true },
      maxBounds: [[-85, -8], [-62, 16]]
    });
    map.addControl(new NavigationControl({ showCompass: false }), 'top-right');
    map.addControl(new ScaleControl({ unit: 'metric' }), 'bottom-right');

    map.on('click', async (event: MapMouseEvent) => {
      const { lng, lat } = event.lngLat;
      (map.getSource('clicked') as GeoJSONSource | undefined)?.setData(
        feature({ type: 'Point', coordinates: [lng, lat] }));
      identifyAbort.current?.abort();
      const controller = new AbortController();
      identifyAbort.current = controller;
      setIdentifying(true);
      setIdentifyError(null);
      setLocated(null);
      try {
        const bounds = map.getBounds();
        const canvas = map.getCanvas();
        const found = await identifyUnit(lng, lat,
          [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()],
          [canvas.clientWidth, canvas.clientHeight], controller.signal);
        setUnit(found);
        if (!found) setIdentifyError('none');
      } catch (exc) {
        if (exc instanceof DOMException && exc.name === 'AbortError') return;
        if (exc instanceof Error && exc.name === 'CanceledError') return;
        setUnit(null);
        setIdentifyError('unavailable');
      } finally {
        if (identifyAbort.current === controller) setIdentifying(false);
      }
    });

    // The panel is hidden on small screens until its tab is chosen.
    const observer = new ResizeObserver(() => map.resize());
    observer.observe(containerRef.current);
    mapRef.current = map;
    return () => {
      observer.disconnect();
      identifyAbort.current?.abort();
      locateAbort.current?.abort();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      map.setLayoutProperty('sgc', 'visibility', geologyOn ? 'visible' : 'none');
      map.setPaintProperty('sgc', 'raster-opacity', opacity);
    };
    if (map.isStyleLoaded()) apply();
    else map.once('load', apply);
  }, [geologyOn, opacity]);

  const fitTo = (bounds: Bounds) => mapRef.current?.fitBounds(bounds, { padding: 20, duration: 700 });

  const handleLocate = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = query.trim();
    const map = mapRef.current;
    if (name.length < 2 || locating || !map) return;
    locateAbort.current?.abort();
    const controller = new AbortController();
    locateAbort.current = controller;
    setLocating(true);
    setLocateError(null);
    try {
      const place = await locatePlace(name, controller.signal);
      setLocated(place);
      setUnit(null);
      setIdentifyError(null);
      const source = map.getSource('located') as GeoJSONSource | undefined;
      if (place.geojson) {
        source?.setData(feature(place.geojson));
        const pts = positions(place.geojson);
        if (pts.length === 1) map.flyTo({ center: pts[0], zoom: 11, duration: 800 });
        else if (pts.length > 1) {
          const lngs = pts.map((p) => p[0]);
          const lats = pts.map((p) => p[1]);
          map.fitBounds([[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]],
            { padding: 40, maxZoom: 12, duration: 800 });
        }
      } else {
        source?.setData(EMPTY);
      }
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === 'AbortError') return;
      setLocated(null);
      setLocateError(exc instanceof ApiError && exc.status === 404 ? t.mapNotFound : t.mapLocateError);
    } finally {
      if (locateAbort.current === controller) setLocating(false);
    }
  };

  const askAboutUnit = (found: GeologicUnit) =>
    onInvestigateFeature?.(
      language === 'es'
        ? `¿Qué se sabe de la unidad geológica ${found.symbol} (${found.age}) en el Valle Medio del Magdalena? Descripción del SGC: ${found.description}`
        : `What is known about the geological unit ${found.symbol} (${found.age}) in the Middle Magdalena Valley? SGC description: ${found.description}`,
      { formation: `${found.symbol} (${found.age})`.slice(0, 120) }
    );

  const askAboutPlace = (place: LocateResponse) =>
    onInvestigateFeature?.(
      language === 'es' ? `¿Qué información geológica hay sobre ${place.name}?` : `What geological information is there about ${place.name}?`,
      { place: place.name.slice(0, 120) }
    );

  const clearLocated = () => {
    setLocated(null);
    (mapRef.current?.getSource('located') as GeoJSONSource | undefined)?.setData(EMPTY);
  };

  return (
    <div className="flex flex-col h-full min-h-0 bg-[#24180F] border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-lg">
      <div className="shrink-0 mb-2 pb-2 border-b border-[#F2E8D5]/30 flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <MapIcon className="w-4 h-4 text-[#D9B36C] shrink-0" />
          <h2 className="text-xs font-bold tracking-tight text-[#F2E8D5] font-serif-academic truncate">{t.mapTitle}</h2>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button type="button" onClick={() => fitTo(VMM_BOUNDS)} title={t.mapViewVmm}
            className="px-1.5 py-0.5 rounded-xs text-[10px] border border-[#F2E8D5]/40 hover:bg-[#2F7D32] hover:text-[#F2E8D5] flex items-center gap-1">
            <Crosshair className="w-3 h-3" />VMM
          </button>
          <button type="button" onClick={() => fitTo(COLOMBIA_BOUNDS)} title={t.mapViewColombia}
            className="px-1.5 py-0.5 rounded-xs text-[10px] border border-[#F2E8D5]/40 hover:bg-[#2F7D32] hover:text-[#F2E8D5] flex items-center gap-1">
            <Globe2 className="w-3 h-3" />COL
          </button>
        </div>
      </div>

      <form onSubmit={handleLocate} className="shrink-0 mb-1.5 flex items-center gap-1.5">
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.mapSearchPlaceholder} maxLength={120}
          className="flex-1 min-w-0 px-2.5 py-1 rounded-md bg-[#18100a] border border-[#F2E8D5]/40 text-[11px] text-[#F2E8D5] placeholder-[#D9B36C]/60 focus:outline-hidden focus:border-[#D9B36C]" />
        <button type="submit" disabled={query.trim().length < 2 || locating}
          className="px-2 py-1 rounded-md bg-[#D9B36C] text-[#24180F] text-[10.5px] font-bold flex items-center gap-1 disabled:opacity-40">
          {locating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
          <span>{t.mapSearch}</span>
        </button>
      </form>
      {locateError && <p className="shrink-0 -mt-0.5 mb-1 text-[10px] text-[#e57373]">{locateError}</p>}

      <div className="relative flex-1 min-h-0 rounded-md overflow-hidden border border-[#F2E8D5]/20">
        {/* maplibre-gl.css sets .maplibregl-map { position: relative } outside any
            cascade layer, so it beats Tailwind's layered `absolute`; position a wrapper. */}
        <div className="absolute inset-0">
          <div ref={containerRef} className="h-full w-full" />
        </div>

        <div className="absolute top-2 left-2 z-10 bg-[#24180F]/90 border border-[#F2E8D5]/40 rounded-md px-2 py-1.5 text-[10px] text-[#F2E8D5] space-y-1 shadow-md">
          <label className="flex items-center gap-1.5 cursor-pointer select-none">
            <input type="checkbox" checked={geologyOn} onChange={(e) => setGeologyOn(e.target.checked)} className="accent-[#2F7D32]" />
            <Layers className="w-3 h-3 text-[#D9B36C]" />
            <span>{t.mapGeologyLayer}</span>
          </label>
          <label className="flex items-center gap-1.5">
            <span className="text-[#D9B36C]">{t.mapOpacity}</span>
            <input type="range" min={0.2} max={1} step={0.05} value={opacity} disabled={!geologyOn}
              onChange={(e) => setOpacity(Number(e.target.value))} className="w-20 accent-[#D9B36C]" />
          </label>
        </div>

        {(identifying || unit || identifyError) && !located && (
          <div className="absolute bottom-2 left-2 z-10 max-w-[260px] bg-[#24180F]/95 border-2 border-[#F2E8D5] rounded-md p-2.5 shadow-2xl text-[10px] text-[#F2E8D5]">
            <div className="flex items-center justify-between gap-2 mb-1 pb-1 border-b border-[#F2E8D5]/30">
              <span className="font-bold text-[10.5px] truncate">{unit ? unit.symbol : t.mapGeologyLayer}</span>
              <button type="button" onClick={() => { setUnit(null); setIdentifyError(null); }} className="text-[#D9B36C] hover:text-[#F2E8D5]" aria-label={t.close}>
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            {identifying ? (
              <div className="flex items-center gap-1.5 text-[#D9B36C]"><Loader2 className="w-3 h-3 animate-spin" />{t.mapIdentifying}</div>
            ) : unit ? (
              <>
                <div><strong className="text-[#D9B36C]">{t.mapUnitAge}:</strong> {unit.age}</div>
                <p className="mt-1 leading-snug text-[#F2E8D5]/90">{unit.description}</p>
                <button type="button" onClick={() => askAboutUnit(unit)}
                  className="mt-2 w-full py-1 rounded-xs bg-[#2F7D32] hover:bg-[#256828] text-[#F2E8D5] font-semibold flex items-center justify-center gap-1">
                  <span>{t.investigateWithCrocol}</span><ExternalLink className="w-2.5 h-2.5" />
                </button>
              </>
            ) : (
              <p className="text-[#D9B36C]/80">{identifyError === 'none' ? t.mapUnitNone : t.mapGeologyUnavailable}</p>
            )}
          </div>
        )}

        {located && (
          <div className="absolute bottom-2 left-2 z-10 max-w-[240px] max-h-[75%] overflow-y-auto bg-[#24180F]/95 border-2 border-[#F2E8D5] rounded-md p-2.5 shadow-2xl text-[10px] text-[#F2E8D5]">
            <div className="flex items-center justify-between gap-2 mb-1 pb-1 border-b border-[#F2E8D5]/30">
              <span className="font-bold text-[10.5px] truncate">{located.name}</span>
              <button type="button" onClick={clearLocated} className="text-[#D9B36C] hover:text-[#F2E8D5]" aria-label={t.close}>
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div><strong className="text-[#D9B36C]">{t.mapKind}:</strong> {located.kind}</div>
            <div><strong className="text-[#D9B36C]">{t.mapSource}:</strong> {located.source}</div>
            <div className="mt-1.5"><EntityCard name={located.name} kinds={[located.kind as EntityKind]} compact /></div>
            <button type="button" onClick={() => askAboutPlace(located)}
              className="mt-2 w-full py-1 rounded-xs bg-[#2F7D32] hover:bg-[#256828] text-[#F2E8D5] font-semibold flex items-center justify-center gap-1">
              <span>{t.investigateWithCrocol}</span><ExternalLink className="w-2.5 h-2.5" />
            </button>
          </div>
        )}

        {!unit && !located && !identifying && !identifyError && (
          <p className="absolute bottom-2 left-2 z-10 bg-[#24180F]/80 rounded-xs px-1.5 py-0.5 text-[9.5px] text-[#F2E8D5]/80 pointer-events-none">
            {t.mapClickHint}
          </p>
        )}
      </div>
    </div>
  );
};
