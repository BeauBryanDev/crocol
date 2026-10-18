import { GeologicalFormation, GeologicalPeriodMeta } from '../../../types/stratigraphy.types';

export const GEOLOGICAL_PERIODS: GeologicalPeriodMeta[] = [
  {
    id: 'quaternary',
    name: { en: 'Quaternary', es: 'Cuaternario' },
    color: '#EAD68B',
    textColor: '#1a120b',
    order: 1
  },
  {
    id: 'neogene',
    name: { en: 'Neogene', es: 'Neógeno' },
    color: '#E4A836',
    textColor: '#1a120b',
    order: 2
  },
  {
    id: 'paleogene',
    name: { en: 'Paleogene', es: 'Paleógeno' },
    color: '#D8975A',
    textColor: '#1a120b',
    order: 3
  },
  {
    id: 'cretaceous',
    name: { en: 'Cretaceous', es: 'Cretácico' },
    color: '#6A9B6B',
    textColor: '#ffffff',
    order: 4
  },
  {
    id: 'jurassic',
    name: { en: 'Jurassic', es: 'Jurásico' },
    color: '#4A9BB8',
    textColor: '#ffffff',
    order: 5
  },
  {
    id: 'triassic',
    name: { en: 'Triassic', es: 'Triásico' },
    color: '#9F7BB8',
    textColor: '#ffffff',
    order: 6
  },
  {
    id: 'permian',
    name: { en: 'Permian', es: 'Pérmico' },
    color: '#B2594D',
    textColor: '#ffffff',
    order: 7
  },
  {
    id: 'pre-mesozoic',
    name: { en: 'Pre-Mesozoic', es: 'Basamento' },
    color: '#B0707D',
    textColor: '#ffffff',
    order: 8
  }
];

export const FORMATIONS_DATA: GeologicalFormation[] = [
  {
    id: 'alluvial-deposits',
    name: 'Alluvial Deposits and Terraces',
    displayName: {
      en: 'Alluvial Deposits & Terraces',
      es: 'Depósitos Aluviales y Terrazas'
    },
    periodId: 'quaternary',
    epochOrAge: {
      en: 'Holocene / Pleistocene',
      es: 'Holoceno / Pleistoceno'
    },
    lithologies: ['sandstone', 'mudstone', 'conglomerate'],
    lithologyText: {
      en: 'Unconsolidated gravel, fine sand, silt and clay',
      es: 'Arenas, limos, gravas inconsolidadas y arcillas'
    },
    facies: {
      en: 'Fluvial: braided channels & floodplains',
      es: 'Fluvial: canales trenzados y llanuras de inundación'
    },
    description: {
      en: 'Recent quaternary alluvial deposits capping the Middle Magdalena Valley and Caribbean basins.',
      es: 'Depósitos aluviales y terrazas cuaternarias recientes que coronan el Valle Medio del Magdalena.'
    },
    sourceIds: ['ANH-2020-VMM', 'SGC-Atlas-2015'],
    validationStatus: 'validated',
    petroleumSignificance: {
      en: 'Regional overburden and shallow freshwater hydrogeology.',
      es: 'Sobrecarga regional y zona hidrogeológica somera.'
    }
  },
  {
    id: 'mesa-formation',
    name: 'Mesa Formation',
    displayName: {
      en: 'Mesa Formation',
      es: 'Formación Mesa'
    },
    periodId: 'neogene',
    epochOrAge: {
      en: 'Pliocene',
      es: 'Plioceno'
    },
    lithologies: ['conglomerate', 'sandstone', 'mudstone'],
    lithologyText: {
      en: 'Polymictic conglomerates, tuffaceous sandstones, green mudstones',
      es: 'Conglomerados polimícticos, areniscas tobáceas y lodolitas verdes'
    },
    facies: {
      en: 'Continental fluvio-lacustrine & debris flows',
      es: 'Continental fluvio-lacustre y flujos de detritos'
    },
    description: {
      en: 'Upper Neogene molassic sequence deposited during intense Andean tectonic uplift.',
      es: 'Secuencia molásica del Neógeno superior depositada durante la orogenia andina principal.'
    },
    sourceIds: ['ANH-VMM-B-04'],
    validationStatus: 'validated'
  },
  {
    id: 'real-group',
    name: 'Real Group',
    displayName: {
      en: 'Real Group (Upper & Lower)',
      es: 'Grupo Real (Sup. e Inf.)'
    },
    periodId: 'neogene',
    epochOrAge: {
      en: 'Miocene',
      es: 'Mioceno'
    },
    lithologies: ['sandstone', 'conglomerate', 'mudstone'],
    lithologyText: {
      en: 'Coarse to conglomeratic sandstones with variegated mudstones',
      es: 'Areniscas conglomeráticas intercaladas con lutitas abigarradas'
    },
    facies: {
      en: 'Continental fluvial systems, meandering & braided',
      es: 'Sistemas fluviales continentales meándricos y trenzados'
    },
    description: {
      en: 'Widespread Miocene formation in VMM, containing prolific shallow heavy-oil reservoirs in fields like Infantas and Colorado.',
      es: 'Ampliamente extendido en el VMM; almacena crudo pesado y medio en campos históricos como La Cira e Infantas.'
    },
    members: ['Real Superior', 'Real Inferior'],
    sourceIds: ['ANH-VMM-G-02'],
    validationStatus: 'validated',
    petroleumSignificance: {
      en: 'Prolific shallow sandstone reservoir in VMM oil fields.',
      es: 'Yacimiento prolífico somero de areniscas en el VMM.'
    }
  },
  {
    id: 'colorado-formation',
    name: 'Colorado Formation',
    displayName: {
      en: 'Colorado Formation',
      es: 'Formación Colorado'
    },
    periodId: 'paleogene',
    epochOrAge: {
      en: 'Oligocene',
      es: 'Oligoceno'
    },
    lithologies: ['sandstone', 'shale', 'mudstone'],
    lithologyText: {
      en: 'Reddish medium to coarse sandstones & thick red mudstones',
      es: 'Alternancia de areniscas rojizas y gruesas capas de lutitas rojas'
    },
    facies: {
      en: 'Continental floodplains & fluvial channels',
      es: 'Llanuras de inundación continentales y canales fluviales'
    },
    description: {
      en: 'Distinctive red-bed sequence with channel sandstone bodies acting as secondary oil reservoirs.',
      es: 'Secuencia típica de capas rojas con cuerpos de arenisca canalizada como yacimientos secundarios.'
    },
    sourceIds: ['ANH-VMM-08'],
    validationStatus: 'validated'
  },
  {
    id: 'mugrosa-formation',
    name: 'Mugrosa Formation',
    displayName: {
      en: 'Mugrosa Formation',
      es: 'Formación Mugrosa'
    },
    periodId: 'paleogene',
    epochOrAge: {
      en: 'Late Eocene',
      es: 'Eoceno Tardío'
    },
    lithologies: ['shale', 'sandstone', 'mudstone'],
    lithologyText: {
      en: 'Gray & variegated mudstones with fossiliferous horizons and gray sandstones',
      es: 'Predominio de lutitas grises y abigarradas con niveles fosilíferos'
    },
    facies: {
      en: 'Continental, transitional to fluvial',
      es: 'Continental transicional a fluvial'
    },
    description: {
      en: 'Contains Zones A and B productive sandstones in the central VMM depocenter.',
      es: 'Alberga las areniscas productoras de las Zonas A y B en el campo La Cira-Infantas.'
    },
    members: ['Zona A', 'Zona B'],
    sourceIds: ['ANH-VMM-M-01'],
    validationStatus: 'validated',
    petroleumSignificance: {
      en: 'Primary producing reservoir in La Cira-Infantas field.',
      es: 'Yacimiento productor principal en La Cira-Infantas.'
    }
  },
  {
    id: 'esmeraldas-formation',
    name: 'Esmeraldas Formation',
    displayName: {
      en: 'Esmeraldas Formation',
      es: 'Formación Esmeraldas'
    },
    periodId: 'paleogene',
    epochOrAge: {
      en: 'Middle Eocene',
      es: 'Eoceno Medio'
    },
    lithologies: ['shale', 'sandstone', 'coal'],
    lithologyText: {
      en: 'Dark carbonaceous mudstones interbedded with thin sandstones',
      es: 'Lutitas oscuras carbonosas intercaladas con areniscas delgadas'
    },
    facies: {
      en: 'Fluvio-estuarine coastal plains, marine influence',
      es: 'Planicie costera fluvio-estuarina con incursiones marinas'
    },
    description: {
      en: 'Fine-grained sequence representing restricted coastal marsh and bayhead delta environments.',
      es: 'Secuencia de grano fino con areniscas de estuario y sellos locales intra-formacionales.'
    },
    sourceIds: ['ANH-VMM-ES-03'],
    validationStatus: 'validated'
  },
  {
    id: 'la-paz-formation',
    name: 'La Paz Formation',
    displayName: {
      en: 'La Paz Formation',
      es: 'Formación La Paz'
    },
    periodId: 'paleogene',
    epochOrAge: {
      en: 'Early Eocene',
      es: 'Eoceno Temprano'
    },
    lithologies: ['sandstone', 'conglomerate'],
    lithologyText: {
      en: 'Massive coarse to conglomeratic quartzose sandstones',
      es: 'Areniscas cuarzosas gruesas a conglomeráticas masivas'
    },
    facies: {
      en: 'High-energy fluvial channels & braided rivers',
      es: 'Canales fluviales de alta energía y ríos trenzados'
    },
    description: {
      en: 'High-porosity, high-permeability regional reservoir sandstones developed across Middle Magdalena.',
      es: 'Excelente yacimiento de areniscas cuarzosas de alta porosidad en campos como Cantagallo y Yariguí.'
    },
    sourceIds: ['ANH-VMM-LP-01'],
    validationStatus: 'validated',
    petroleumSignificance: {
      en: 'High quality sandstone reservoir with excellent petrophysical properties.',
      es: 'Excelente yacimiento de alta calidad con porosidad de 18-24%.'
    }
  },
  {
    id: 'lisama-formation',
    name: 'Lisama Formation',
    displayName: {
      en: 'Lisama Formation',
      es: 'Formación Lisama'
    },
    periodId: 'paleogene',
    epochOrAge: {
      en: 'Paleocene',
      es: 'Paleoceno'
    },
    lithologies: ['sandstone', 'mudstone', 'coal'],
    lithologyText: {
      en: 'Rhythmic interbeds of fine sandstones, siltstones, mudstones & coal',
      es: 'Areniscas finas, limolitas y lodolitas con mantos de carbón'
    },
    facies: {
      en: 'Deltaic alluvial plains & coal swamps',
      es: 'Llanuras aluviales deltaicas y pantanos con carbón'
    },
    description: {
      en: 'Transitional Paleocene sequence marking initial Andean retroarc foreland development.',
      es: 'Secuencia deltaica del Paleoceno con mantos de carbón y areniscas productoras en Casabe y Llanito.'
    },
    sourceIds: ['ANH-VMM-LIS-02'],
    validationStatus: 'validated'
  },
  {
    id: 'umir-formation',
    name: 'Umir Formation',
    displayName: {
      en: 'Umir Formation',
      es: 'Formación Umir'
    },
    periodId: 'cretaceous',
    epochOrAge: {
      en: 'Maastrichtian',
      es: 'Maastrichtiano'
    },
    lithologies: ['shale', 'mudstone', 'sandstone'],
    lithologyText: {
      en: 'Dark gray shales, carbonaceous mudstones, thin sandstones',
      es: 'Lutitas grises oscuras, lodolitas carbonosas y areniscas delgadas'
    },
    facies: {
      en: 'Shallow marine to transitional delta fronts & estuaries',
      es: 'Marino somero a frentes deltaicos y estuarios'
    },
    description: {
      en: 'Major regional top seal for Cretaceous reservoirs throughout Middle Magdalena Valley.',
      es: 'Sello regional principal para los yacimientos cretácicos en el Valle Medio del Magdalena.'
    },
    sourceIds: ['ANH-VMM-UM-01'],
    validationStatus: 'validated',
    petroleumSignificance: {
      en: 'Regional caprock seal protecting underlying Cretaceous accumulations.',
      es: 'Sello regional suprayacente de las acumulaciones cretácicas.'
    }
  },
  {
    id: 'la-luna-formation',
    name: 'La Luna Formation',
    displayName: {
      en: 'La Luna Formation (Galembo, Pujamana, Salada)',
      es: 'Formación La Luna (Galembo, Pujamana, Salada)'
    },
    periodId: 'cretaceous',
    epochOrAge: {
      en: 'Campanian – Turonian',
      es: 'Campaniano – Turoniano'
    },
    lithologies: ['limestone', 'shale'],
    lithologyText: {
      en: 'Bituminous limestones, calcareous black shales & chert nodules',
      es: 'Calizas fosilíferas, calizas bituminosas, lutitas negras calcáreas y chert'
    },
    facies: {
      en: 'Deep anoxic marine outer shelf; world-class source rock',
      es: 'Marino anóxico profundo y plataforma externa; roca madre estelar'
    },
    description: {
      en: 'The premier hydrocarbon source rock of northern South America (TOC up to 12%, Type II kerogen), generating over 80% of Colombia petroleum.',
      es: 'La principal roca generadora de petróleo de Colombia y el norte de Sudamérica (COT hasta 12%, kerógeno Tipo II).'
    },
    members: ['Galembo Member', 'Pujamana Member', 'Salada Member'],
    sourceIds: ['ANH-2018-LALUNA', 'SGC-2017-PETRO', 'Rangel-et-al-2017'],
    validationStatus: 'validated',
    petroleumSignificance: {
      en: 'Principal source rock of Colombia. Self-sourced unconventional target.',
      es: 'Roca generadora principal de hidrocarburos de Colombia y objetivo no convencional.'
    }
  },
  {
    id: 'simiti-formation',
    name: 'Simití Formation',
    displayName: {
      en: 'Simití Formation',
      es: 'Formación Simití'
    },
    periodId: 'cretaceous',
    epochOrAge: {
      en: 'Cenomanian – Albian',
      es: 'Cenomaniano – Albiano'
    },
    lithologies: ['shale'],
    lithologyText: {
      en: 'Uniform black marine shales with spherical calcareous concretions',
      es: 'Lutitas negras homogéneas con concreciones calcáreas esféricas'
    },
    facies: {
      en: 'Inner to outer marine shelf',
      es: 'Plataforma marina interna a externa'
    },
    description: {
      en: 'Thick marine shale succession providing secondary source rock potential and intraformational seals.',
      es: 'Espesa sucesión de lutitas marinas con potencial generador secundario y sellos competentes.'
    },
    sourceIds: ['ANH-VMM-SIM-04'],
    validationStatus: 'validated'
  },
  {
    id: 'tablazo-formation',
    name: 'Tablazo Formation',
    displayName: {
      en: 'Tablazo Formation',
      es: 'Formación Tablazo'
    },
    periodId: 'cretaceous',
    epochOrAge: {
      en: 'Albian – Aptian',
      es: 'Albiano – Aptiano'
    },
    lithologies: ['limestone', 'shale'],
    lithologyText: {
      en: 'Massive dark-gray wackestones and packstones with fossiliferous marls',
      es: 'Calizas wackestones y packstones oscuras con margas fosilíferas'
    },
    facies: {
      en: 'Shallow marine, open carbonate shelf',
      es: 'Marino somero, plataforma carbonatada abierta'
    },
    description: {
      en: 'Carbonate shelf sequence with bioclastic limestone intervals and fracture-enhanced permeability.',
      es: 'Plataforma carbonatada con bivalvos y amonites; almacén fracturado en estructuras anticlinales.'
    },
    sourceIds: ['ANH-VMM-TAB-01'],
    validationStatus: 'validated',
    petroleumSignificance: {
      en: 'Naturally fractured carbonate reservoir with oil shows in VMM.',
      es: 'Yacimiento de carbonatos fracturados con producción en el flanco oriental del VMM.'
    }
  },
  {
    id: 'paja-formation',
    name: 'Paja Formation',
    displayName: {
      en: 'Paja Formation',
      es: 'Formación Paja'
    },
    periodId: 'cretaceous',
    epochOrAge: {
      en: 'Aptian – Barremian',
      es: 'Aptiano – Barremiano'
    },
    lithologies: ['shale', 'mudstone'],
    lithologyText: {
      en: 'Black, micaceous, fossiliferous clay-rich mudstones',
      es: 'Lutitas negras ricas en arcilla, micáceas y altamente fosilíferas'
    },
    facies: {
      en: 'Restricted shallow marine, inner to middle shelf',
      es: 'Marino somero restringido, plataforma interna a media'
    },
    description: {
      en: 'Fossil-rich marine shale unit (famous for Kronosaurus and marine reptiles) with notable organic richness.',
      es: 'Unidad marina fosilífera de lutitas oscuras con alta riqueza orgánica y potencial generador secundario.'
    },
    sourceIds: ['SGC-PAJA-2016'],
    validationStatus: 'validated'
  },
  {
    id: 'rosablanca-formation',
    name: 'Rosa Blanca Formation',
    displayName: {
      en: 'Rosa Blanca Formation',
      es: 'Formación Rosa Blanca'
    },
    periodId: 'cretaceous',
    epochOrAge: {
      en: 'Barremian – Hauterivian',
      es: 'Barremiano – Hauteriviano'
    },
    lithologies: ['limestone', 'shale'],
    lithologyText: {
      en: 'Fossiliferous limestones, dolomites and calcareous packstones',
      es: 'Calizas fosilíferas, dolomías y packstones calcáreos'
    },
    facies: {
      en: 'Shallow carbonate marine, lagoonal, reefal & intertidal',
      es: 'Marino carbonatado somero, lagunar, arrecifal e intermareal'
    },
    description: {
      en: 'Basal Cretaceous marine carbonate platform, prominent fractured reservoir in various Andean foothill structures.',
      es: 'Plataforma carbonatada marina basal cretácica; almacén carbonatado fracturado de petróleo y gas.'
    },
    sourceIds: ['ANH-VMM-RB-02'],
    validationStatus: 'validated',
    petroleumSignificance: {
      en: 'Fractured limestone and dolomite reservoir.',
      es: 'Yacimiento de calizas y dolomías fracturadas.'
    }
  },
  {
    id: 'tambor-los-santos',
    name: 'Tambor / Los Santos formations',
    displayName: {
      en: 'Tambor / Los Santos Formations',
      es: 'Formaciones Tambor / Los Santos'
    },
    periodId: 'cretaceous',
    epochOrAge: {
      en: 'Valanginian – Berriasian',
      es: 'Valanginiano – Berriasiano'
    },
    lithologies: ['sandstone', 'conglomerate'],
    lithologyText: {
      en: 'Red conglomeratic quartz arenites interbedded with mudstones',
      es: 'Areniscas cuarzosas conglomeráticas rojizas con lutitas'
    },
    facies: {
      en: 'Basal continental fluvial to shallow transitional environments',
      es: 'Continental fluvial basal a transicional somero'
    },
    description: {
      en: 'Transgressive basal clastic sandstone blankets marking the Cretaceous marine flooding event.',
      es: 'Manto clástico basal de areniscas que registra la ingresión marina cretácica en Colombia.'
    },
    sourceIds: ['ANH-VMM-TS-01'],
    validationStatus: 'validated'
  },
  {
    id: 'norean-giron',
    name: 'Noreán / Girón formations',
    displayName: {
      en: 'Noreán / Girón Formations',
      es: 'Formaciones Noreán / Girón'
    },
    periodId: 'jurassic',
    epochOrAge: {
      en: 'Upper Jurassic',
      es: 'Jurásico Superior'
    },
    lithologies: ['sandstone', 'volcanic', 'conglomerate'],
    lithologyText: {
      en: 'Red feldspathic sandstones, conglomerates & interbedded volcanic rocks',
      es: 'Areniscas feldespáticas rojizas, conglomerados y rocas volcánicas'
    },
    facies: {
      en: 'Continental tectonic rift, alluvial fans & braided rivers',
      es: 'Rift tectónico continental, abanicos aluviales y ríos trenzados'
    },
    description: {
      en: 'Syn-rift continental red-beds with interbedded rhyolites and andesites associated with Pangea breakup.',
      es: 'Secuencia continental sin-rift de capas rojas y volcanitas asociadas a la fragmentación de Pangea.'
    },
    sourceIds: ['SGC-GIRON-2018'],
    validationStatus: 'validated'
  },
  {
    id: 'crystalline-basement',
    name: 'Crystalline Basement',
    displayName: {
      en: 'Crystalline Basement (San Lucas Gneiss)',
      es: 'Basamento Cristalino (Gneis de San Lucas)'
    },
    periodId: 'pre-mesozoic',
    epochOrAge: {
      en: 'Precambrian – Paleozoic',
      es: 'Precámbrico – Paleozoico'
    },
    lithologies: ['basement', 'volcanic'],
    lithologyText: {
      en: 'Plutonic granodiorites, schists and high-grade gneisses',
      es: 'Rocas plutónicas (granodioritas), esquistos y gneis de alto grado'
    },
    facies: {
      en: 'Ancient continental craton / orogenic metamorphic basement',
      es: 'Cratón continental antiguo o basamento metamórfico orogénico'
    },
    description: {
      en: 'Acoustic and structural basement forming the economic floor of Colombian petroleum systems.',
      es: 'Piso económico y basamento acústico estructural de los sistemas petrolíferos colombianos.'
    },
    sourceIds: ['ANH-BASEMENT-01', 'SGC-GEOMAP-2020'],
    validationStatus: 'validated',
    petroleumSignificance: {
      en: 'Structural floor; rarely fractured basement play.',
      es: 'Piso estructural de la cuenca; objetivo no convencional solo si está densamente fracturado.'
    }
  }
];
