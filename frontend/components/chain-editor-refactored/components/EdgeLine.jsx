import { CONDITION_LABELS } from '../constants';
import { getEdgeMid, getEdgePath, getNodeCenter, getPortPosition, inferSideBetweenPoints } from '../utils';

export function EdgeLine({ edge, srcNode, tgtNode, isSelected, onClick, conditions }) {
  const path = getEdgePath(srcNode, tgtNode, edge);
  const mid = getEdgeMid(srcNode, tgtNode, edge);
  const sCenter = getNodeCenter(srcNode);
  const tCenter = getNodeCenter(tgtNode);
  const tSide = inferSideBetweenPoints(tCenter, sCenter);
  const tPort = getPortPosition(tgtNode, tSide);
  const isFromRouter = srcNode?.node_type === 'router';
  const strokeColor = isSelected ? '#0f172a' : isFromRouter ? '#9333ea' : '#64748b';
  const isEntering = edge.__anim === 'enter';
  const isExiting = edge.__anim === 'exit';
  return (
    <g
      onClick={onClick}
      className="cursor-pointer"
      style={{
        opacity: isEntering || isExiting ? 0 : 1,
        transition: 'opacity 0.5s ease',
      }}
    >
      <path d={path} fill="none" stroke="transparent" strokeWidth={16} />
      <path
        d={path}
        fill="none"
        stroke={strokeColor}
        strokeWidth={isSelected ? 3 : isFromRouter ? 2.5 : 2}
        strokeDasharray={!isFromRouter && conditions.length === 0 ? '6 4' : 'none'}
      />
      <circle cx={tPort.x} cy={tPort.y} r={5} fill={strokeColor} />
      {!isFromRouter && conditions.slice(0, 2).map((cond, i) => (
        <foreignObject key={cond.id} x={mid.x - 60 + i * 2} y={mid.y - 14 - i * 20} width={120} height={24}>
          <div className="backdrop-blur border rounded-lg px-2 py-1 text-xs font-medium shadow-sm whitespace-nowrap bg-white/95 border-slate-200 text-slate-700">
            {CONDITION_LABELS[cond.condition_type]}
            {cond.params.button_label ? `: ${cond.params.button_label}` : ''}
            {cond.params.substring ? `: "${cond.params.substring}"` : ''}
            {cond.params.pattern ? `: /${cond.params.pattern}/` : ''}
            {cond.params.message_type ? ` = ${cond.params.message_type}` : ''}
            {cond.params.entity_type ? ` [${cond.params.entity_type}]` : ''}
            {cond.params.exact_text ? ` = "${cond.params.exact_text}"` : ''}
          </div>
        </foreignObject>
      ))}
    </g>
  );
}
