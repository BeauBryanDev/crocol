import React from 'react';

/**
 * Standard AAPG / USGS Geological Lithology SVG Pattern Definitions
 * Uses official Crocol color palette:
 * - Green: #2F7D32
 * - Brown: #24180F
 * - Ivory: #F2E8D5
 * - Gold: #D9B36C
 */
export const LithologyPatternDefs: React.FC = () => {
  return (
    <svg className="absolute w-0 h-0 overflow-hidden" aria-hidden="true">
      <defs>
        {/* 1. Sandstone (Arenisca) - Stippled dots pattern */}
        <pattern id="pattern-sandstone" width="16" height="16" patternUnits="userSpaceOnUse">
          <rect width="16" height="16" fill="#422e1e" />
          <circle cx="4" cy="4" r="1.2" fill="#d9b36c" />
          <circle cx="12" cy="4" r="1.2" fill="#d9b36c" />
          <circle cx="8" cy="10" r="1.2" fill="#eed59b" />
          <circle cx="2" cy="14" r="1.2" fill="#d9b36c" />
          <circle cx="14" cy="14" r="1.2" fill="#eed59b" />
        </pattern>

        {/* 2. Shale (Lutita) - Horizontal dashed lines */}
        <pattern id="pattern-shale" width="24" height="10" patternUnits="userSpaceOnUse">
          <rect width="24" height="10" fill="#2d2218" />
          <line x1="2" y1="3" x2="10" y2="3" stroke="#f2e8d5" strokeWidth="1.2" strokeLinecap="round" opacity="0.8" />
          <line x1="14" y1="3" x2="22" y2="3" stroke="#f2e8d5" strokeWidth="1.2" strokeLinecap="round" opacity="0.8" />
          <line x1="6" y1="8" x2="18" y2="8" stroke="#d9b36c" strokeWidth="1.2" strokeLinecap="round" opacity="0.7" />
        </pattern>

        {/* 3. Limestone (Caliza) - Standard brickwork pattern */}
        <pattern id="pattern-limestone" width="28" height="14" patternUnits="userSpaceOnUse">
          <rect width="28" height="14" fill="#38291b" />
          {/* Horizontal bed lines */}
          <line x1="0" y1="7" x2="28" y2="7" stroke="#f2e8d5" strokeWidth="1" opacity="0.75" />
          <line x1="0" y1="14" x2="28" y2="14" stroke="#f2e8d5" strokeWidth="1" opacity="0.75" />
          {/* Vertical joints offset (brick bond) */}
          <line x1="14" y1="0" x2="14" y2="7" stroke="#f2e8d5" strokeWidth="1" opacity="0.75" />
          <line x1="0" y1="7" x2="0" y2="14" stroke="#f2e8d5" strokeWidth="1" opacity="0.75" />
          <line x1="28" y1="7" x2="28" y2="14" stroke="#f2e8d5" strokeWidth="1" opacity="0.75" />
        </pattern>

        {/* 4. Conglomerate (Conglomerado) - Rounded gravel & pebbles */}
        <pattern id="pattern-conglomerate" width="24" height="24" patternUnits="userSpaceOnUse">
          <rect width="24" height="24" fill="#3a2717" />
          <ellipse cx="6" cy="6" rx="3.5" ry="2.5" fill="none" stroke="#d9b36c" strokeWidth="1.2" />
          <ellipse cx="18" cy="8" rx="4" ry="3" fill="none" stroke="#eed59b" strokeWidth="1.2" />
          <ellipse cx="10" cy="18" rx="5" ry="3.5" fill="none" stroke="#f2e8d5" strokeWidth="1.2" />
          <circle cx="21" cy="20" r="1.5" fill="#d9b36c" />
          <circle cx="3" cy="21" r="1" fill="#eed59b" />
        </pattern>

        {/* 5. Evaporite (Evaporita) - Salt crosses */}
        <pattern id="pattern-evaporite" width="20" height="20" patternUnits="userSpaceOnUse">
          <rect width="20" height="20" fill="#20343a" />
          <path d="M7 5 L13 5 M10 2 L10 8" stroke="#4a9bb8" strokeWidth="1.4" strokeLinecap="square" />
          <path d="M17 15 L23 15 M20 12 L20 18" stroke="#f2e8d5" strokeWidth="1.4" strokeLinecap="square" />
          <path d="M3 15 L5 15 M4 14 L4 16" stroke="#4a9bb8" strokeWidth="1" />
        </pattern>

        {/* 6. Volcanic (Volcánica) - Igneous V-shapes */}
        <pattern id="pattern-volcanic" width="20" height="16" patternUnits="userSpaceOnUse">
          <rect width="20" height="16" fill="#44221c" />
          <path d="M3 4 L6 10 L9 4" fill="none" stroke="#b2594d" strokeWidth="1.5" strokeLinecap="round" />
          <path d="M13 10 L16 16 L19 10" fill="none" stroke="#d9b36c" strokeWidth="1.5" strokeLinecap="round" />
        </pattern>

        {/* 7. Mudstone / Silt (Limo / Arcilla) - Fine parallel striations */}
        <pattern id="pattern-mudstone" width="16" height="8" patternUnits="userSpaceOnUse">
          <rect width="16" height="8" fill="#322419" />
          <line x1="0" y1="2" x2="16" y2="2" stroke="#d9b36c" strokeWidth="0.8" opacity="0.5" />
          <line x1="0" y1="6" x2="16" y2="6" stroke="#f2e8d5" strokeWidth="0.8" opacity="0.6" strokeDasharray="4 2" />
        </pattern>

        {/* 8. Coal (Carbón) - Solid black dense bars */}
        <pattern id="pattern-coal" width="16" height="10" patternUnits="userSpaceOnUse">
          <rect width="16" height="10" fill="#18110b" />
          <rect x="1" y="2" width="14" height="2" fill="#0c0704" stroke="#d9b36c" strokeWidth="0.4" />
          <rect x="3" y="6" width="10" height="2" fill="#0c0704" stroke="#d9b36c" strokeWidth="0.4" />
        </pattern>

        {/* 9. Basement (Basamento Cristalino) - Granite / gneiss pattern */}
        <pattern id="pattern-basement" width="24" height="24" patternUnits="userSpaceOnUse">
          <rect width="24" height="24" fill="#3b2229" />
          {/* Metamorphic foliation wavy curves */}
          <path d="M0 6 Q6 2 12 6 T24 6" fill="none" stroke="#b0707d" strokeWidth="1.2" opacity="0.8" />
          <path d="M0 18 Q6 14 12 18 T24 18" fill="none" stroke="#d9b36c" strokeWidth="1.2" opacity="0.7" />
          {/* Crystalline crosses */}
          <path d="M5 11 L9 11 M7 9 L7 13" stroke="#f2e8d5" strokeWidth="1" />
          <path d="M17 21 L21 21 M19 19 L19 23" stroke="#f2e8d5" strokeWidth="1" />
        </pattern>
      </defs>
    </svg>
  );
};
