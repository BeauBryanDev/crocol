import React, { useEffect, useRef, useState } from 'react';
import { useLanguage } from '../../../i18n/useLanguage';
import { COLOMBIA_BASINS, COLOMBIA_WELLS, COLOMBIA_FIELDS } from '../data/colombiaGeoData';
import { OilWell, SedimentaryBasin, OilField } from '../../../types/map.types';
import { LocateResponse } from '../../../types/api.types';
import { ApiError } from '../../../api/apiClient';
import { geometryCenter, locatePlace } from '../services/locateService';
import { Map, Plus, Minus, Layers, Compass, X, ExternalLink, Search, Loader2, MapPin } from 'lucide-react';

interface LocatedPlace extends LocateResponse {
  center: [number, number] | null;
}

interface GeologicalMapPanelProps {
  onSelectWell?: (well: OilWell) => void;
  onSelectField?: (field: OilField) => void;
  onInvestigateFeature?: (query: string) => void;
}

export const GeologicalMapPanel: React.FC<GeologicalMapPanelProps> = ({
  onSelectWell,
  onSelectField,
  onInvestigateFeature
}) => {
  const { language, t } = useLanguage();
  const [activeLayer, setActiveLayer] = useState<'geologico' | 'cuencas' | 'yacimientos'>('geologico');
  const [zoomLevel, setZoomLevel] = useState(1);
  const [selectedWell, setSelectedWell] = useState<OilWell | null>(null);
  const [selectedBasin, setSelectedBasin] = useState<SedimentaryBasin | null>(null);
  const [query, setQuery] = useState('');
  const [located, setLocated] = useState<LocatedPlace | null>(null);
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState<string | null>(null);
  const locateAbort = useRef<AbortController | null>(null);

  useEffect(() => () => locateAbort.current?.abort(), []);

  const handleLocate = async (e: React.FormEvent) => {
    e.preventDefault();
    const name = query.trim();
    if (name.length < 2 || locating) return;
    locateAbort.current?.abort();
    const controller = new AbortController();
    locateAbort.current = controller;
    setLocating(true);
    setLocateError(null);
    try {
      const place = await locatePlace(name, controller.signal);
      setLocated({ ...place, center: geometryCenter(place.geojson) });
      setSelectedWell(null);
      setSelectedBasin(null);
    } catch (exc) {
      if (exc instanceof DOMException && exc.name === 'AbortError') return;
      setLocated(null);
      setLocateError(exc instanceof ApiError && exc.status === 404 ? t.mapNotFound : t.mapLocateError);
    } finally {
      if (locateAbort.current === controller) setLocating(false);
    }
  };

  // Geographic bounds for Colombia map projection:
  // Lat: -4.2 (South) to 12.5 (North)
  // Lng: -79.0 (West) to -66.8 (East)
  const mapCoordsToPercent = (lat: number, lng: number) => {
    const minLat = -4.2;
    const maxLat = 12.8;
    const minLng = -79.2;
    const maxLng = -66.8;

    const x = ((lng - minLng) / (maxLng - minLng)) * 100;
    const y = ((maxLat - lat) / (maxLat - minLat)) * 100;
    return { x: Math.max(5, Math.min(95, x)), y: Math.max(5, Math.min(95, y)) };
  };

  const handleZoom = (delta: number) => {
    setZoomLevel((prev) => Math.min(2.2, Math.max(0.8, prev + delta)));
  };

  return (
    <div className="flex flex-col h-full bg-[#24180F] border border-[#F2E8D5] rounded-lg p-3 text-[#D9B36C] shadow-lg relative overflow-hidden">
      {/* Panel Header matching mockup */}
      <div className="mb-2 pb-2 border-b border-[#F2E8D5]/30 flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <Map className="w-4 h-4 text-[#D9B36C]" />
          <h2 className="text-xs font-bold tracking-tight text-[#F2E8D5] font-serif-academic truncate">
            {t.mapTitle}
          </h2>
        </div>

        {/* 3 Layer Toggle Buttons */}
        <div className="flex items-center gap-1 bg-[#18100a] p-0.5 rounded-md border border-[#F2E8D5]/30">
          <button
            onClick={() => setActiveLayer('geologico')}
            className={`px-2 py-0.5 rounded-xs text-[10px] font-medium transition-all ${
              activeLayer === 'geologico'
                ? 'bg-[#F2E8D5] text-[#24180F] font-bold shadow-xs'
                : 'text-[#D9B36C] hover:text-[#F2E8D5]'
            }`}
          >
            {t.tabGeological}
          </button>
          <button
            onClick={() => setActiveLayer('cuencas')}
            className={`px-2 py-0.5 rounded-xs text-[10px] font-medium transition-all ${
              activeLayer === 'cuencas'
                ? 'bg-[#F2E8D5] text-[#24180F] font-bold shadow-xs'
                : 'text-[#D9B36C] hover:text-[#F2E8D5]'
            }`}
          >
            {t.tabBasins}
          </button>
          <button
            onClick={() => setActiveLayer('yacimientos')}
            className={`px-2 py-0.5 rounded-xs text-[10px] font-medium transition-all ${
              activeLayer === 'yacimientos'
                ? 'bg-[#F2E8D5] text-[#24180F] font-bold shadow-xs'
                : 'text-[#D9B36C] hover:text-[#F2E8D5]'
            }`}
          >
            {t.tabFields}
          </button>
        </div>
      </div>

      <form onSubmit={handleLocate} className="mb-2 flex items-center gap-1.5">
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t.mapSearchPlaceholder}
          maxLength={120}
          className="flex-1 min-w-0 px-2.5 py-1 rounded-md bg-[#18100a] border border-[#F2E8D5]/40 text-[11px] text-[#F2E8D5] placeholder-[#D9B36C]/60 focus:outline-hidden focus:border-[#D9B36C]"
        />
        <button
          type="submit"
          disabled={query.trim().length < 2 || locating}
          className="px-2 py-1 rounded-md bg-[#D9B36C] text-[#24180F] text-[10.5px] font-bold flex items-center gap-1 disabled:opacity-40"
        >
          {locating ? <Loader2 className="w-3 h-3 animate-spin" /> : <Search className="w-3 h-3" />}
          <span>{t.mapSearch}</span>
        </button>
      </form>
      {locateError && <p className="-mt-1 mb-1.5 text-[10px] text-[#e57373]">{locateError}</p>}

      {/* Map Viewport Area */}
      <div className="relative flex-1 bg-[#18100a] rounded-md border border-[#F2E8D5]/20 overflow-hidden flex items-center justify-center">
        {/* Background Map Graphic: Scaled & Optimized WebP */}
        <div
          className="absolute inset-0 transition-transform duration-200 flex items-center justify-center"
          style={{ transform: `scale(${zoomLevel})` }}
        >
          <img
            src="/assets/colombia-geology-map.webp"
            alt="Geological Map of Colombia"
            className="w-full h-full object-contain filter contrast-105"
            referrerPolicy="no-referrer"
          />

          {/* Interactive Basins Overlay */}
          {(activeLayer === 'cuencas' || activeLayer === 'geologico') && (
            <div className="absolute inset-0 pointer-events-none">
              {COLOMBIA_BASINS.map((b) => {
                const pos = mapCoordsToPercent(b.coordinates[0], b.coordinates[1]);
                return (
                  <div
                    key={b.id}
                    style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
                    className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto cursor-pointer group"
                    onClick={() => {
                      setSelectedBasin(b);
                      setSelectedWell(null);
                    }}
                  >
                    <div className="px-1.5 py-0.5 rounded-xs bg-[#24180F]/90 border border-[#D9B36C] text-[8.5px] font-bold text-[#D9B36C] shadow-md group-hover:bg-[#2F7D32] group-hover:text-[#F2E8D5] group-hover:border-[#F2E8D5] transition-all whitespace-nowrap">
                      {b.name.split('(')[0]}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Interactive Wells & Fields Overlay */}
          {(activeLayer === 'geologico' || activeLayer === 'yacimientos') && (
            <div className="absolute inset-0 pointer-events-none">
              {COLOMBIA_WELLS.map((w) => {
                const pos = mapCoordsToPercent(w.coordinates[0], w.coordinates[1]);
                const isSelected = selectedWell?.id === w.id;
                return (
                  <button
                    key={w.id}
                    style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedWell(w);
                      setSelectedBasin(null);
                      onSelectWell?.(w);
                    }}
                    title={`${w.name} (${w.field})`}
                    className={`absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto rounded-full transition-transform hover:scale-150 focus:outline-hidden ${
                      isSelected
                        ? 'w-3.5 h-3.5 bg-[#F2E8D5] border-2 border-[#D9B36C] z-30 ring-2 ring-[#2F7D32]'
                        : 'w-2.5 h-2.5 bg-[#e53935] border border-[#F2E8D5] shadow-xs z-20 hover:z-30'
                    }`}
                  />
                );
              })}

              {/* Oil Fields Markers */}
              {activeLayer === 'yacimientos' &&
                COLOMBIA_FIELDS.map((f) => {
                  const pos = mapCoordsToPercent(f.coordinates[0], f.coordinates[1]);
                  return (
                    <div
                      key={f.id}
                      style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
                      className="absolute -translate-x-1/2 -translate-y-1/2 pointer-events-auto cursor-pointer"
                      onClick={() => onSelectField?.(f)}
                    >
                      <div className="w-3 h-3 bg-[#D9B36C] border border-[#F2E8D5] rotate-45 shadow-sm" />
                    </div>
                  );
                })}
            </div>
          )}

          {located?.center && (() => {
            const pos = mapCoordsToPercent(located.center[0], located.center[1]);
            return (
              <div
                style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
                className="absolute -translate-x-1/2 -translate-y-full z-40 pointer-events-none"
                title={located.name}
              >
                <MapPin className="w-5 h-5 text-[#2F7D32] fill-[#F2E8D5] drop-shadow" />
              </div>
            );
          })()}
        </div>

        {/* Map Controls: Top Left (+ / - / layers) */}
        <div className="absolute top-2 left-2 flex flex-col gap-1 z-30">
          <button
            onClick={() => handleZoom(0.2)}
            className="w-6 h-6 rounded-xs bg-[#24180F]/90 border border-[#F2E8D5]/60 text-[#F2E8D5] hover:bg-[#2F7D32] flex items-center justify-center transition-colors text-xs shadow-md"
            title="Acercar (Zoom In)"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => handleZoom(-0.2)}
            className="w-6 h-6 rounded-xs bg-[#24180F]/90 border border-[#F2E8D5]/60 text-[#F2E8D5] hover:bg-[#2F7D32] flex items-center justify-center transition-colors text-xs shadow-md"
            title="Alejar (Zoom Out)"
          >
            <Minus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() =>
              setActiveLayer(
                activeLayer === 'geologico'
                  ? 'cuencas'
                  : activeLayer === 'cuencas'
                  ? 'yacimientos'
                  : 'geologico'
              )
            }
            className="w-6 h-6 rounded-xs bg-[#24180F]/90 border border-[#F2E8D5]/60 text-[#D9B36C] hover:bg-[#2F7D32] hover:text-[#F2E8D5] flex items-center justify-center transition-colors text-xs shadow-md"
            title="Alternar capas"
          >
            <Layers className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* North Arrow: Top Right */}
        <div className="absolute top-2 right-24 z-30 pointer-events-none flex flex-col items-center">
          <div className="text-[10px] font-bold text-[#F2E8D5] tracking-widest font-serif leading-none mb-0.5">
            N
          </div>
          <Compass className="w-4 h-4 text-[#D9B36C]" />
        </div>

        {/* Map Legend Overlay on Right Side matching mockup */}
        <div className="absolute top-2 right-2 z-30 bg-[#24180F]/92 backdrop-blur-xs border border-[#F2E8D5]/40 rounded-xs p-1.5 text-[9px] shadow-lg max-w-[110px]">
          <div className="font-bold text-[#D9B36C] border-b border-[#F2E8D5]/20 pb-0.5 mb-1 text-[9.5px]">
            {t.mapLegendTitle}
          </div>
          <div className="space-y-0.5">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#e53935] border border-[#F2E8D5] shrink-0" />
              <span className="text-[#F2E8D5] truncate">{t.legendWells}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 bg-[#D9B36C] border border-[#F2E8D5] rotate-45 shrink-0" />
              <span className="text-[#F2E8D5] truncate">{t.legendFields}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 border border-dashed border-[#D9B36C] shrink-0" />
              <span className="text-[#F2E8D5] truncate">{t.legendBasins}</span>
            </div>

            {/* Geological Period Swatches */}
            <div className="pt-1 mt-1 border-t border-[#F2E8D5]/20 space-y-0.5">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-xs bg-[#EAD68B] shrink-0" />
                <span className="text-[#F2E8D5]/90 truncate">{t.legendCuaternary}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-xs bg-[#E4A836] shrink-0" />
                <span className="text-[#F2E8D5]/90 truncate">{t.legendNeogene}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-xs bg-[#D8975A] shrink-0" />
                <span className="text-[#F2E8D5]/90 truncate">{t.legendPaleogene}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-xs bg-[#6A9B6B] shrink-0" />
                <span className="text-[#F2E8D5]/90 truncate">{t.legendCretaceous}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-xs bg-[#4A9BB8] shrink-0" />
                <span className="text-[#F2E8D5]/90 truncate">{t.legendJurassic}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-xs bg-[#9F7BB8] shrink-0" />
                <span className="text-[#F2E8D5]/90 truncate">{t.legendTriassic}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-xs bg-[#B2594D] shrink-0" />
                <span className="text-[#F2E8D5]/90 truncate">{t.legendPermian}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-xs bg-[#B0707D] shrink-0" />
                <span className="text-[#F2E8D5]/90 truncate">{t.legendBasement}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Scale Bar: Bottom Right */}
        <div className="absolute bottom-1 right-2 z-30 pointer-events-none flex flex-col items-end">
          <div className="flex justify-between w-24 text-[8px] text-[#F2E8D5] font-mono leading-none">
            <span>0</span>
            <span>100</span>
            <span>200</span>
            <span>400 km</span>
          </div>
          <div className="w-24 h-1 border-b-2 border-l-2 border-r-2 border-[#F2E8D5] mt-0.5" />
        </div>

        {located && !selectedWell && !selectedBasin && (
          <div className="absolute bottom-2 left-2 z-40 bg-[#24180F]/95 border-2 border-[#F2E8D5] rounded-md p-2.5 max-w-[220px] shadow-2xl">
            <div className="flex items-center justify-between mb-1 pb-1 border-b border-[#F2E8D5]/30">
              <span className="text-[10px] font-bold text-[#F2E8D5] truncate">{located.name}</span>
              <button onClick={() => setLocated(null)} className="text-[#D9B36C] hover:text-[#F2E8D5]">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="text-[9.5px] space-y-0.5 text-[#F2E8D5]/90">
              <div><strong className="text-[#D9B36C]">{t.mapKind}:</strong> {located.kind}</div>
              {located.center && (
                <div className="font-mono">
                  {located.center[0].toFixed(4)}, {located.center[1].toFixed(4)}
                </div>
              )}
              <div><strong className="text-[#D9B36C]">{t.mapSource}:</strong> {located.source}</div>
            </div>
            <button
              onClick={() => {
                onInvestigateFeature?.(
                  language === 'es'
                    ? `¿Qué información geológica hay sobre ${located.name}?`
                    : `What geological information is there about ${located.name}?`
                );
                setLocated(null);
              }}
              className="mt-2 w-full py-1 rounded-xs bg-[#2F7D32] hover:bg-[#256828] text-[#F2E8D5] text-[9.5px] font-semibold flex items-center justify-center gap-1 transition-colors"
            >
              <span>{t.investigateWithCrocol}</span>
              <ExternalLink className="w-2.5 h-2.5" />
            </button>
          </div>
        )}

        {/* Selected Well / Basin Popup */}
        {selectedWell && (
          <div className="absolute bottom-2 left-2 z-40 bg-[#24180F]/95 border-2 border-[#F2E8D5] rounded-md p-2.5 max-w-[220px] shadow-2xl animate-in fade-in duration-150">
            <div className="flex items-center justify-between mb-1 pb-1 border-b border-[#F2E8D5]/30">
              <span className="text-[10px] font-bold text-[#F2E8D5] truncate">
                {selectedWell.name}
              </span>
              <button
                onClick={() => setSelectedWell(null)}
                className="text-[#D9B36C] hover:text-[#F2E8D5]"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="text-[9.5px] space-y-0.5 text-[#F2E8D5]/90">
              <div><strong className="text-[#D9B36C]">{t.operator}:</strong> {selectedWell.operator}</div>
              <div><strong className="text-[#D9B36C]">{t.status}:</strong> {selectedWell.status}</div>
              <div><strong className="text-[#D9B36C]">{t.depth}:</strong> {selectedWell.depthFt.toLocaleString()} ft</div>
              <div><strong className="text-[#D9B36C]">{t.formationTarget}:</strong> {selectedWell.targetFormation}</div>
            </div>
            <button
              onClick={() => {
                onInvestigateFeature?.(
                  language === 'es'
                    ? `¿Qué información técnica hay del pozo ${selectedWell.name} en ${selectedWell.field}?`
                    : `What technical information is there on the ${selectedWell.name} well in ${selectedWell.field}?`
                );
                setSelectedWell(null);
              }}
              className="mt-2 w-full py-1 rounded-xs bg-[#2F7D32] hover:bg-[#256828] text-[#F2E8D5] text-[9.5px] font-semibold flex items-center justify-center gap-1 transition-colors"
            >
              <span>{t.investigateWithCrocol}</span>
              <ExternalLink className="w-2.5 h-2.5" />
            </button>
          </div>
        )}

        {selectedBasin && (
          <div className="absolute bottom-2 left-2 z-40 bg-[#24180F]/95 border-2 border-[#F2E8D5] rounded-md p-2.5 max-w-[220px] shadow-2xl animate-in fade-in duration-150">
            <div className="flex items-center justify-between mb-1 pb-1 border-b border-[#F2E8D5]/30">
              <span className="text-[10px] font-bold text-[#F2E8D5] truncate">
                {selectedBasin.name}
              </span>
              <button
                onClick={() => setSelectedBasin(null)}
                className="text-[#D9B36C] hover:text-[#F2E8D5]"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            <div className="text-[9.5px] space-y-0.5 text-[#F2E8D5]/90">
              <div><strong className="text-[#D9B36C]">{t.area}:</strong> {selectedBasin.areaKm2.toLocaleString()} km²</div>
              <div><strong className="text-[#D9B36C]">{t.cumulativeProd}:</strong> {(selectedBasin.totalCumulativeProductionMBO / 1000).toFixed(1)} MMBO</div>
              <p className="text-[8.5px] text-[#F2E8D5]/70 pt-1 leading-tight">{selectedBasin.description[language]}</p>
            </div>
            <button
              onClick={() => {
                onInvestigateFeature?.(
                  language === 'es'
                    ? `¿Cuál es la estratigrafía y el potencial petrolífero de ${selectedBasin.name}?`
                    : `What are the stratigraphy and petroleum potential of ${selectedBasin.name}?`
                );
                setSelectedBasin(null);
              }}
              className="mt-2 w-full py-1 rounded-xs bg-[#2F7D32] hover:bg-[#256828] text-[#F2E8D5] text-[9.5px] font-semibold flex items-center justify-center gap-1 transition-colors"
            >
              <span>{t.investigateWithCrocol}</span>
              <ExternalLink className="w-2.5 h-2.5" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
