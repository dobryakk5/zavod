import { getConnectionPoints, getCurvedPath, getEdgeMid } from '../utils';

export function EdgeLine({ edge, srcNode, tgtNode, isHovered, onClick, onDelete }) {
  const { sx, sy, tx, ty } = getConnectionPoints(srcNode, tgtNode, edge.route_id);
  const path = getCurvedPath(sx, sy, tx, ty);
  const { x: mx, y: my } = getEdgeMid(sx, sy, tx, ty);

  return (
    <g className={`transition-opacity ${isHovered ? "opacity-100" : "opacity-70"}`}>
      {/* Invisible thick path for easier clicking */}
      <path 
        d={path} 
        fill="none" 
        stroke="transparent" 
        strokeWidth={20} 
        className="cursor-pointer" 
        onClick={onClick} 
      />
      
      {/* Visible path */}
      <path 
        d={path} 
        fill="none" 
        stroke="#94a3b8" 
        strokeWidth={isHovered ? 3 : 2} 
        className="pointer-events-none" 
      />

      {/* Delete button on hover */}
      {isHovered && (
        <g transform={`translate(${mx}, ${my})`}>
          <circle 
            r={10} 
            fill="#ef4444" 
            className="cursor-pointer" 
            onClick={(e) => { e.stopPropagation(); onDelete(); }} 
          />
          <text 
            x={0} 
            y={1} 
            textAnchor="middle" 
            fontSize={12} 
            fill="white" 
            fontWeight="bold" 
            className="pointer-events-none select-none"
          >
            ×
          </text>
        </g>
      )}
    </g>
  );
}

export function DrawingLine({ from, to }) {
  return (
    <line 
      x1={from.x} 
      y1={from.y} 
      x2={to.x} 
      y2={to.y} 
      stroke="#3b82f6" 
      strokeWidth={2} 
      strokeDasharray="5,5" 
      className="pointer-events-none" 
    />
  );
}
