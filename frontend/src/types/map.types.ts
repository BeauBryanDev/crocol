export type MapLayerType = 'geologico' | 'cuencas' | 'yacimientos';

export interface SedimentaryBasin {
  id: string;
  name: string;
  areaKm2: number;
  basinType: string;
  keyFormations: string[];
  totalCumulativeProductionMBO: number;
  coordinates: [number, number]; // [lat, lng]
  svgPolygonPath?: string;
  description: { en: string; es: string };
}

export interface OilWell {
  id: string;
  name: string;
  field: string;
  basin: string;
  operator: string;
  status: 'Producing' | 'Shut-in' | 'Exploratory' | 'Abandoned';
  depthFt: number;
  spudYear: number;
  targetFormation: string;
  coordinates: [number, number]; // [lat, lng]
}

export interface OilField {
  id: string;
  name: string;
  basin: string;
  department: string;
  discoveryYear: number;
  operator: string;
  primaryReservoir: string;
  currentBopd: number;
  coordinates: [number, number];
}
