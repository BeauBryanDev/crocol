import { FieldProductionRecord } from '../../../types/production.types';

export const HISTORICAL_PRODUCTION_DATA: Record<string, FieldProductionRecord> = {
  rubiales: {
    fieldId: 'rubiales',
    fieldName: 'Campo Rubiales',
    basin: 'Cuenca Llanos Orientales',
    department: 'Meta',
    cumulativeOilMMBO: 520,
    observations: [
      { year: 2010, oilBopd: 145000, gasMpcd: 380, waterBwpd: 120 },
      { year: 2011, oilBopd: 198000, gasMpcd: 520, waterBwpd: 210 },
      { year: 2012, oilBopd: 285000, gasMpcd: 680, waterBwpd: 310 },
      { year: 2013, oilBopd: 380000, gasMpcd: 940, waterBwpd: 450 },
      { year: 2014, oilBopd: 460000, gasMpcd: 1120, waterBwpd: 590 },
      { year: 2015, oilBopd: 480000, gasMpcd: 1140, waterBwpd: 680 },
      { year: 2016, oilBopd: 425000, gasMpcd: 1100, waterBwpd: 710 },
      { year: 2017, oilBopd: 380000, gasMpcd: 1120, waterBwpd: 720 },
      { year: 2018, oilBopd: 340000, gasMpcd: 1050, waterBwpd: 690 },
      { year: 2019, oilBopd: 295000, gasMpcd: 1020, waterBwpd: 670 },
      { year: 2020, oilBopd: 260000, gasMpcd: 940, waterBwpd: 640 },
      { year: 2021, oilBopd: 280000, gasMpcd: 950, waterBwpd: 660 },
      { year: 2022, oilBopd: 250000, gasMpcd: 890, waterBwpd: 650 },
      { year: 2023, oilBopd: 230000, gasMpcd: 840, waterBwpd: 630 },
      { year: 2024, oilBopd: 215000, gasMpcd: 780, waterBwpd: 610 }
    ]
  },
  cusiana: {
    fieldId: 'cusiana',
    fieldName: 'Campo Cusiana',
    basin: 'Piedemonte Llanero',
    department: 'Casanare',
    cumulativeOilMMBO: 980,
    observations: [
      { year: 2010, oilBopd: 95000, gasMpcd: 1450, waterBwpd: 80 },
      { year: 2011, oilBopd: 88000, gasMpcd: 1520, waterBwpd: 95 },
      { year: 2012, oilBopd: 79000, gasMpcd: 1610, waterBwpd: 110 },
      { year: 2013, oilBopd: 72000, gasMpcd: 1680, waterBwpd: 130 },
      { year: 2014, oilBopd: 65000, gasMpcd: 1720, waterBwpd: 160 },
      { year: 2015, oilBopd: 58000, gasMpcd: 1690, waterBwpd: 190 },
      { year: 2016, oilBopd: 52000, gasMpcd: 1640, waterBwpd: 220 },
      { year: 2017, oilBopd: 48000, gasMpcd: 1590, waterBwpd: 260 },
      { year: 2018, oilBopd: 44000, gasMpcd: 1520, waterBwpd: 290 },
      { year: 2019, oilBopd: 41000, gasMpcd: 1470, waterBwpd: 310 },
      { year: 2020, oilBopd: 38000, gasMpcd: 1390, waterBwpd: 330 },
      { year: 2021, oilBopd: 36000, gasMpcd: 1350, waterBwpd: 350 },
      { year: 2022, oilBopd: 34000, gasMpcd: 1310, waterBwpd: 370 },
      { year: 2023, oilBopd: 33000, gasMpcd: 1260, waterBwpd: 390 },
      { year: 2024, oilBopd: 32000, gasMpcd: 1210, waterBwpd: 400 }
    ]
  },
  'la-cira-infantas': {
    fieldId: 'la-cira-infantas',
    fieldName: 'Campo La Cira-Infantas',
    basin: 'Valle Medio del Magdalena (VMM)',
    department: 'Santander',
    cumulativeOilMMBO: 890,
    observations: [
      { year: 2010, oilBopd: 32000, gasMpcd: 140, waterBwpd: 410 },
      { year: 2011, oilBopd: 36000, gasMpcd: 155, waterBwpd: 460 },
      { year: 2012, oilBopd: 41000, gasMpcd: 170, waterBwpd: 520 },
      { year: 2013, oilBopd: 44000, gasMpcd: 190, waterBwpd: 590 },
      { year: 2014, oilBopd: 43000, gasMpcd: 185, waterBwpd: 640 },
      { year: 2015, oilBopd: 40000, gasMpcd: 175, waterBwpd: 680 },
      { year: 2016, oilBopd: 37000, gasMpcd: 160, waterBwpd: 710 },
      { year: 2017, oilBopd: 35000, gasMpcd: 150, waterBwpd: 740 },
      { year: 2018, oilBopd: 33000, gasMpcd: 145, waterBwpd: 770 },
      { year: 2019, oilBopd: 31000, gasMpcd: 140, waterBwpd: 790 },
      { year: 2020, oilBopd: 28000, gasMpcd: 130, waterBwpd: 810 },
      { year: 2021, oilBopd: 29000, gasMpcd: 135, waterBwpd: 830 },
      { year: 2022, oilBopd: 29500, gasMpcd: 138, waterBwpd: 840 },
      { year: 2023, oilBopd: 28800, gasMpcd: 132, waterBwpd: 850 },
      { year: 2024, oilBopd: 28000, gasMpcd: 128, waterBwpd: 860 }
    ]
  },
  'cano-limon': {
    fieldId: 'cano-limon',
    fieldName: 'Campo Caño Limón',
    basin: 'Cuenca Llanos Norte',
    department: 'Arauca',
    cumulativeOilMMBO: 1450,
    observations: [
      { year: 2010, oilBopd: 92000, gasMpcd: 210, waterBwpd: 780 },
      { year: 2012, oilBopd: 82000, gasMpcd: 190, waterBwpd: 840 },
      { year: 2014, oilBopd: 71000, gasMpcd: 170, waterBwpd: 890 },
      { year: 2016, oilBopd: 63000, gasMpcd: 155, waterBwpd: 930 },
      { year: 2018, oilBopd: 55000, gasMpcd: 140, waterBwpd: 960 },
      { year: 2020, oilBopd: 49000, gasMpcd: 130, waterBwpd: 980 },
      { year: 2022, oilBopd: 47000, gasMpcd: 125, waterBwpd: 990 },
      { year: 2024, oilBopd: 46000, gasMpcd: 120, waterBwpd: 1010 }
    ]
  },
  castilla: {
    fieldId: 'castilla',
    fieldName: 'Campo Castilla',
    basin: 'Cuenca Llanos Orientales',
    department: 'Meta',
    cumulativeOilMMBO: 680,
    observations: [
      { year: 2010, oilBopd: 82000, gasMpcd: 290, waterBwpd: 210 },
      { year: 2012, oilBopd: 102000, gasMpcd: 360, waterBwpd: 340 },
      { year: 2014, oilBopd: 118000, gasMpcd: 410, waterBwpd: 460 },
      { year: 2016, oilBopd: 122000, gasMpcd: 430, waterBwpd: 580 },
      { year: 2018, oilBopd: 115000, gasMpcd: 410, waterBwpd: 690 },
      { year: 2020, oilBopd: 108000, gasMpcd: 380, waterBwpd: 760 },
      { year: 2022, oilBopd: 106000, gasMpcd: 370, waterBwpd: 810 },
      { year: 2024, oilBopd: 104000, gasMpcd: 360, waterBwpd: 840 }
    ]
  }
};
