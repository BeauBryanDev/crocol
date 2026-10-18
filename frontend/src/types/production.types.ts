export interface ProductionDataPoint {
  year: number;
  oilBopd: number;      // Barrels of oil per day
  gasMpcd: number;      // Thousand cubic feet per day
  waterBwpd: number;    // Barrels of water per day
}

export interface FieldProductionRecord {
  fieldId: string;
  fieldName: string;
  basin: string;
  department: string;
  cumulativeOilMMBO: number;
  observations: ProductionDataPoint[];
}
