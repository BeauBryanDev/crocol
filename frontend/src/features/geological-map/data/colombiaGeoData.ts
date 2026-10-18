import { OilWell, SedimentaryBasin, OilField } from '../../../types/map.types';

export const COLOMBIA_BASINS: SedimentaryBasin[] = [
  {
    id: 'vmm',
    name: 'Valle Medio del Magdalena (VMM)',
    areaKm2: 34000,
    basinType: 'Intermontane Foreland Basin',
    keyFormations: ['La Luna', 'La Paz', 'Mugrosa', 'Esmeraldas', 'Real'],
    totalCumulativeProductionMBO: 2150000,
    coordinates: [6.8, -73.9],
    description: {
      en: 'The cradle of Colombian oil industry. Excellent Cretaceous source rock (La Luna) charging Paleogene-Neogene sandstone reservoirs.',
      es: 'Cuna de la industria petrolera colombiana. Excelente roca generadora cretácica (La Luna) que carga reservorios terciarios.'
    }
  },
  {
    id: 'llanos',
    name: 'Cuenca Llanos Orientales',
    areaKm2: 200000,
    basinType: 'Foreland Basin',
    keyFormations: ['Carbonera', 'Mirador', 'Gachetá', 'Une'],
    totalCumulativeProductionMBO: 4300000,
    coordinates: [4.2, -71.5],
    description: {
      en: 'Colombia’s most prolific producing basin, generating over 65% of national crude, dominated by heavy and intermediate oil.',
      es: 'La cuenca más productiva de Colombia, genera más del 65% del crudo nacional, dominada por crudos pesados e intermedios.'
    }
  },
  {
    id: 'catatumbo',
    name: 'Cuenca Catatumbo',
    areaKm2: 7300,
    basinType: 'Foreland Sub-basin',
    keyFormations: ['La Luna', 'Catatumbo', 'Barco', 'Los Cuervos'],
    totalCumulativeProductionMBO: 580000,
    coordinates: [8.2, -72.8],
    description: {
      en: 'South-western extension of the Maracaibo Basin with classic light oil and gas production.',
      es: 'Prolongación suroccidental de la Cuenca de Maracaibo, con producción histórica de crudo liviano y gas.'
    }
  },
  {
    id: 'putumayo',
    name: 'Cuenca Caguán-Putumayo',
    areaKm2: 110000,
    basinType: 'Sub-Andean Foreland',
    keyFormations: ['Caballos', 'Villeta', 'Pepino'],
    totalCumulativeProductionMBO: 620000,
    coordinates: [0.8, -76.2],
    description: {
      en: 'Active petroleum system in southern Colombia with Cretaceous sandstone plays.',
      es: 'Sistema petrolífero activo en el sur del país con reservorios clásticos cretácicos.'
    }
  }
];

export const COLOMBIA_WELLS: OilWell[] = [
  // Llanos Basin Wells (Rubiales, Quifa, Castilla)
  {
    id: 'w-rub-101',
    name: 'Rubiales-101',
    field: 'Campo Rubiales',
    basin: 'Cuenca Llanos Orientales',
    operator: 'Ecopetrol S.A.',
    status: 'Producing',
    depthFt: 4250,
    spudYear: 2008,
    targetFormation: 'Carbonera Fm. (Basal Sandstones)',
    coordinates: [3.85, -71.4]
  },
  {
    id: 'w-rub-204',
    name: 'Rubiales-204H',
    field: 'Campo Rubiales',
    basin: 'Cuenca Llanos Orientales',
    operator: 'Ecopetrol S.A.',
    status: 'Producing',
    depthFt: 6100,
    spudYear: 2012,
    targetFormation: 'Carbonera Fm.',
    coordinates: [3.92, -71.35]
  },
  {
    id: 'w-cas-15',
    name: 'Castilla-15',
    field: 'Campo Castilla',
    basin: 'Cuenca Llanos Orientales',
    operator: 'Ecopetrol S.A.',
    status: 'Producing',
    depthFt: 7800,
    spudYear: 2005,
    targetFormation: 'K1 / Guadalupe Fm.',
    coordinates: [3.98, -73.7]
  },
  {
    id: 'w-chich-8',
    name: 'Chichimene-8',
    field: 'Campo Chichimene',
    basin: 'Cuenca Llanos Orientales',
    operator: 'Ecopetrol S.A.',
    status: 'Producing',
    depthFt: 8400,
    spudYear: 2009,
    targetFormation: 'San Fernando / T2',
    coordinates: [3.89, -73.55]
  },
  {
    id: 'w-quifa-9',
    name: 'Quifa-9H',
    field: 'Campo Quifa',
    basin: 'Cuenca Llanos Orientales',
    operator: 'Frontera Energy',
    status: 'Producing',
    depthFt: 5300,
    spudYear: 2014,
    targetFormation: 'Carbonera Fm.',
    coordinates: [4.15, -71.1]
  },
  // VMM Basin Wells (La Cira-Infantas, Casabe, Cantagallo)
  {
    id: 'w-inf-1',
    name: 'Infantas-1 (Discovery Well)',
    field: 'Campo La Cira-Infantas',
    basin: 'Valle Medio del Magdalena (VMM)',
    operator: 'Ecopetrol / Oxy',
    status: 'Producing',
    depthFt: 2280,
    spudYear: 1918,
    targetFormation: 'Mugrosa Fm. (Zona A)',
    coordinates: [6.95, -73.78]
  },
  {
    id: 'w-cir-54',
    name: 'La Cira-54',
    field: 'Campo La Cira-Infantas',
    basin: 'Valle Medio del Magdalena (VMM)',
    operator: 'Ecopetrol / Oxy',
    status: 'Producing',
    depthFt: 3450,
    spudYear: 1965,
    targetFormation: 'Colorado / Mugrosa Fm.',
    coordinates: [7.05, -73.85]
  },
  {
    id: 'w-cas-12',
    name: 'Casabe-12',
    field: 'Campo Casabe',
    basin: 'Valle Medio del Magdalena (VMM)',
    operator: 'Ecopetrol S.A.',
    status: 'Producing',
    depthFt: 4600,
    spudYear: 1952,
    targetFormation: 'La Paz Fm.',
    coordinates: [7.12, -73.92]
  },
  {
    id: 'w-can-4',
    name: 'Cantagallo-4',
    field: 'Campo Cantagallo',
    basin: 'Valle Medio del Magdalena (VMM)',
    operator: 'Ecopetrol S.A.',
    status: 'Producing',
    depthFt: 7200,
    spudYear: 1988,
    targetFormation: 'La Paz Fm. & Lisama',
    coordinates: [7.4, -73.9]
  },
  // Piedemonte Llanero (Cusiana)
  {
    id: 'w-cus-2',
    name: 'Cusiana-2A',
    field: 'Campo Cusiana',
    basin: 'Piedemonte Llanero',
    operator: 'Ecopetrol S.A.',
    status: 'Producing',
    depthFt: 15400,
    spudYear: 1991,
    targetFormation: 'Mirador & Barco Fm.',
    coordinates: [5.05, -72.7]
  },
  // Arauca (Caño Limón)
  {
    id: 'w-cl-1',
    name: 'Caño Limón-1',
    field: 'Campo Caño Limón',
    basin: 'Cuenca Llanos Norte',
    operator: 'SierraCol Energy',
    status: 'Producing',
    depthFt: 8600,
    spudYear: 1983,
    targetFormation: 'Mirador / Carbonera',
    coordinates: [6.95, -71.2]
  },
  // Putumayo Basin Wells
  {
    id: 'w-ori-3',
    name: 'Orito-3',
    field: 'Campo Orito',
    basin: 'Cuenca Caguán-Putumayo',
    operator: 'Gran Tierra Energy',
    status: 'Producing',
    depthFt: 6700,
    spudYear: 1963,
    targetFormation: 'Caballos & Villeta T/U',
    coordinates: [0.65, -76.85]
  }
];

export const COLOMBIA_FIELDS: OilField[] = [
  {
    id: 'rubiales',
    name: 'Campo Rubiales',
    basin: 'Cuenca Llanos Orientales',
    department: 'Meta',
    discoveryYear: 1981,
    operator: 'Ecopetrol S.A.',
    primaryReservoir: 'Carbonera Fm. (Basal Sandstones)',
    currentBopd: 98000,
    coordinates: [3.88, -71.38]
  },
  {
    id: 'cusiana',
    name: 'Campo Cusiana',
    basin: 'Piedemonte Llanero',
    department: 'Casanare',
    discoveryYear: 1988,
    operator: 'Ecopetrol S.A.',
    primaryReservoir: 'Mirador, Barco, Guadalupe',
    currentBopd: 32000,
    coordinates: [5.05, -72.7]
  },
  {
    id: 'cano-limon',
    name: 'Campo Caño Limón',
    basin: 'Cuenca Llanos Norte',
    department: 'Arauca',
    discoveryYear: 1983,
    operator: 'SierraCol Energy',
    primaryReservoir: 'Mirador Fm.',
    currentBopd: 46000,
    coordinates: [6.95, -71.2]
  },
  {
    id: 'la-cira-infantas',
    name: 'Campo La Cira-Infantas',
    basin: 'Valle Medio del Magdalena (VMM)',
    department: 'Santander',
    discoveryYear: 1918,
    operator: 'Ecopetrol / Oxy',
    primaryReservoir: 'Mugrosa & Colorado Fm.',
    currentBopd: 28000,
    coordinates: [7.0, -73.8]
  },
  {
    id: 'castilla',
    name: 'Campo Castilla',
    basin: 'Cuenca Llanos Orientales',
    department: 'Meta',
    discoveryYear: 1969,
    operator: 'Ecopetrol S.A.',
    primaryReservoir: 'K1 Guadalupe Fm.',
    currentBopd: 104000,
    coordinates: [3.98, -73.7]
  },
  {
    id: 'chichimene',
    name: 'Campo Chichimene',
    basin: 'Cuenca Llanos Orientales',
    department: 'Meta',
    discoveryYear: 1969,
    operator: 'Ecopetrol S.A.',
    primaryReservoir: 'San Fernando / T2 Fm.',
    currentBopd: 72000,
    coordinates: [3.89, -73.55]
  }
];
