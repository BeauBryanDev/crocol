import axios from 'axios';

// Servicio Geológico Colombiano, Mapa Geológico de Colombia 2023 (ArcGIS MapServer).
// It renders images on demand ("export") and allows browser origins (CORS).
const SGC_MAPSERVER =
  'https://srvags.sgc.gov.co/arcgis/rest/services/Mapa_Geologico_Colombia/Mapa_Geologico_Colombia_V2023/MapServer';

export const SGC_EXPORT_TILES =
  `${SGC_MAPSERVER}/export?bbox={bbox-epsg-3857}&bboxSR=3857&imageSR=3857&size=256,256` +
  '&format=png32&transparent=true&dpi=96&f=image';

export const SGC_ATTRIBUTION =
  '<a href="https://www2.sgc.gov.co/MGC/Paginas/mgc_1_5M2023.aspx">Servicio Geológico Colombiano – Mapa Geológico de Colombia 2023</a>';

const IDENTIFY_TIMEOUT_MS = 10_000;

export interface GeologicUnit {
  symbol: string;
  age: string;
  description: string;
  code: string;
}

interface IdentifyResult {
  layerName: string;
  attributes: Record<string, unknown>;
}

const fold = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

const pick = (attributes: Record<string, unknown>, ...names: string[]): string => {
  for (const [key, value] of Object.entries(attributes)) {
    if (names.some((n) => fold(key).startsWith(n)) && value !== null && value !== 'Null') return String(value);
  }
  return '';
};

// The chronostratigraphic unit under a clicked point, or null over sea or gaps.
export const identifyUnit = async (
  lng: number,
  lat: number,
  extent: [number, number, number, number],
  size: [number, number],
  signal?: AbortSignal
): Promise<GeologicUnit | null> => {
  const response = await axios.get<{ results?: IdentifyResult[] }>(`${SGC_MAPSERVER}/identify`, {
    params: {
      geometry: `${lng},${lat}`,
      geometryType: 'esriGeometryPoint',
      sr: 4326,
      layers: 'visible',
      tolerance: 2,
      mapExtent: extent.join(','),
      imageDisplay: `${Math.round(size[0])},${Math.round(size[1])},96`,
      returnGeometry: false,
      f: 'json'
    },
    timeout: IDENTIFY_TIMEOUT_MS,
    signal
  });
  const unit = (response.data.results ?? []).find((r) => fold(r.layerName).includes('cronoestratigraf'));
  if (!unit) return null;
  const symbol = pick(unit.attributes, 'simbolo');
  if (!symbol) return null;
  return {
    symbol,
    age: pick(unit.attributes, 'edad'),
    description: pick(unit.attributes, 'descripcion'),
    code: pick(unit.attributes, 'codigo')
  };
};
