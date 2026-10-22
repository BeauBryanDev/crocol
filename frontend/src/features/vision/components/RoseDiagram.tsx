import React from 'react';

const SIZE = 150;
const CENTER = SIZE / 2;
const RADIUS = 62;
const PETAL_COLOR = '#e57373';

const point = (degrees: number, r: number): string => {
  const rad = (degrees * Math.PI) / 180;
  // Image frame: 0° to the right, angles counter-clockwise (SVG y points down).
  return `${(CENTER + r * Math.cos(rad)).toFixed(2)} ${(CENTER - r * Math.sin(rad)).toFixed(2)}`;
};

const wedge = (from: number, to: number, r: number): string =>
  `M ${CENTER} ${CENTER} L ${point(from, r)} A ${r} ${r} 0 0 0 ${point(to, r)} Z`;

// Crack orientations are axial (θ and θ + 180° are the same line), so each
// 0–180° bin is drawn twice. Petal radius grows with the square root of the
// share, so petal area stays proportional to it.
export const RoseDiagram: React.FC<{ rose: number[]; label: string }> = ({ rose, label }) => {
  const max = Math.max(...rose, 0);
  const binDeg = rose.length ? 180 / rose.length : 10;

  return (
    <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-[150px] h-[150px] shrink-0" role="img" aria-label={label}>
      {[0.5, 1].map((f) => (
        <circle key={f} cx={CENTER} cy={CENTER} r={RADIUS * f} fill="none" stroke="#F2E8D5" strokeOpacity={0.2} />
      ))}
      <line x1={CENTER - RADIUS} y1={CENTER} x2={CENTER + RADIUS} y2={CENTER} stroke="#F2E8D5" strokeOpacity={0.2} />
      <line x1={CENTER} y1={CENTER - RADIUS} x2={CENTER} y2={CENTER + RADIUS} stroke="#F2E8D5" strokeOpacity={0.2} />
      {max > 0 &&
        rose.map((share, b) => {
          if (share <= 0) return null;
          const r = RADIUS * Math.sqrt(share / max);
          const from = b * binDeg;
          return (
            <g key={b}>
              <path d={wedge(from, from + binDeg, r)} fill={PETAL_COLOR} fillOpacity={0.8} stroke="#24180F" strokeWidth={0.5} />
              <path d={wedge(from + 180, from + 180 + binDeg, r)} fill={PETAL_COLOR} fillOpacity={0.8} stroke="#24180F" strokeWidth={0.5} />
            </g>
          );
        })}
      <text x={SIZE - 2} y={CENTER - 3} textAnchor="end" fontSize={8} fill="#D9B36C">0°</text>
      <text x={CENTER + 3} y={9} fontSize={8} fill="#D9B36C">90°</text>
      <text x={2} y={CENTER - 3} fontSize={8} fill="#D9B36C">180°</text>
    </svg>
  );
};
