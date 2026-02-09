import { useState } from 'react';
import {
  CONDITION_PORT,
  NODE_COLORS,
  ROUTER_PADDING,
} from '../constants';
import { formatRouterConditionLabel, getNodeDimensions } from '../utils';

const PORTS = [
  { side: 'top', style: { left: '50%', top: -6, transform: 'translate(-50%, -50%)' } },
  { side: 'right', style: { right: -6, top: '50%', transform: 'translate(50%, -50%)' } },
  { side: 'bottom', style: { left: '50%', bottom: -6, transform: 'translate(-50%, 50%)' } },
  { side: 'left', style: { left: -6, top: '50%', transform: 'translate(-50%, -50%)' } },
];

const PLUS = [
  { side: 'top', style: { left: '50%', top: -26, transform: 'translate(-50%, -50%)' } },
  { side: 'right', style: { right: -26, top: '50%', transform: 'translate(50%, -50%)' } },
  { side: 'bottom', style: { left: '50%', bottom: -26, transform: 'translate(-50%, 50%)' } },
  { side: 'left', style: { left: -26, top: '50%', transform: 'translate(-50%, -50%)' } },
];

function formatDuration(seconds) {
  const total = Math.max(1, Number(seconds) || 0);
  if (total < 60) return `${total}с`;
  if (total < 3600) return `${Math.floor(total / 60)}м`;
  if (total < 86400) return `${Math.floor(total / 3600)}ч`;
  return `${Math.floor(total / 86400)}д`;
}

export function NodeCard({
  node,
  isSelected,
  isHovered,
  onPointerDown,
  onClick,
  onContextMenu,
  onMouseEnter,
  onMouseLeave,
  onPortPointerDown,
  onAddFromSide,
  onConditionPortPointerDown,
  onConditionAdd,
  onConditionEdit,
  onConditionDelete,
  onNodeUpdate,
}) {
  const c = NODE_COLORS[node.node_type];
  const isTimer = node.node_type === 'timer' || (node.node_type === 'text' && node.payload?.kind === 'timer');
  const isRouter = node.node_type === 'router';
  const isStartNode = node.node_type === 'start';
  const showControls = Boolean(isHovered);
  const { w, h } = getNodeDimensions(node);
  const isEntering = node.__anim === 'enter';
  const isExiting = node.__anim === 'exit';
  const animStyle = {
    opacity: isEntering || isExiting ? 0 : 1,
    transform: isEntering || isExiting ? 'scale(0.96)' : 'scale(1)',
    transition: 'opacity 0.5s ease, transform 0.5s ease',
    transformOrigin: 'center',
    willChange: 'opacity, transform',
  };

  // Блоки всегда выходят вправо
  const conditionSide = 'right';

  // Специальная карточка START
  if (isStartNode) {
    const buttons = Array.isArray(node.payload?.buttons) 
      ? node.payload.buttons.map(btn => 
          typeof btn === 'string' 
            ? { text: btn, color: 'green' }
            : btn
        )
      : [];
    
    const buttonStyles = {
      green: { border: 'border-emerald-500', text: 'text-emerald-700' },
      red: { border: 'border-red-500', text: 'text-red-700' },
      blue: { border: 'border-blue-500', text: 'text-blue-700' },
      black: { border: 'border-slate-700', text: 'text-slate-700' },
    };
    
    return (
      <div
        onPointerDown={onPointerDown}
        onClick={onClick}
        onContextMenu={onContextMenu}
        onMouseEnter={onMouseEnter}
        onMouseLeave={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX;
          const y = e.clientY;
          const padding = 30;
          if (
            x < rect.left - padding ||
            x > rect.right + padding ||
            y < rect.top - padding ||
            y > rect.bottom + padding
          ) {
            onMouseLeave?.(e);
          }
        }}
        className={`rounded-xl border-2 cursor-grab select-none shadow-lg transition-all ${
          isSelected ? 'ring-2 ring-offset-2' : ''
        } relative`}
        style={{
          position: 'absolute',
          left: node.pos_x,
          top: node.pos_y,
          width: w,
          height: h,
          backgroundColor: '#ecfdf5',
          borderColor: isSelected ? '#10b981' : '#6ee7b7',
          ringColor: '#10b981',
          ...animStyle,
        }}
      >
        <div className="p-4 h-full flex flex-col justify-center gap-3">
          <div className="flex items-center justify-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-bold text-emerald-700 uppercase tracking-wider">
              START
            </span>
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          </div>
          
          {node.payload?.text && (
            <p className="text-sm text-slate-700 text-center leading-snug">
              {node.payload.text}
            </p>
          )}

          {buttons.length > 0 && (
            <div className="flex flex-wrap gap-1.5 justify-center">
              {buttons.map((btn, idx) => {
                const btnStyle = buttonStyles[btn.color] || buttonStyles.green;
                return (
                  <div
                    key={idx}
                    className={`px-2 py-1 bg-white border rounded text-xs font-medium ${btnStyle.border} ${btnStyle.text}`}
                  >
                    {btn.text}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {showControls && (
          <>
            {PORTS.map((port) => (
              <div
                key={port.side}
                style={{ ...port.style, borderColor: '#6ee7b7' }}
                className="absolute w-3 h-3 rounded-full bg-white border-2 shadow-sm cursor-crosshair"
                data-port={port.side}
                onPointerDown={(e) => {
                  e.stopPropagation();
                  onPortPointerDown?.(node.id, port.side, e);
                }}
              />
            ))}

            {PLUS.map((plus) => (
              <div
                key={plus.side}
                style={plus.style}
                className="absolute w-4 h-4 rounded bg-white border border-slate-300 text-[10px] font-bold flex items-center justify-center cursor-pointer"
                onPointerDown={(e) => {
                  e.stopPropagation();
                }}
                onPointerUp={(e) => {
                  e.stopPropagation();
                  onAddFromSide?.(node.id, plus.side, e);
                }}
              >
                +
              </div>
            ))}
          </>
        )}
      </div>
    );
  }

  if (isRouter) {
    const conditions = Array.isArray(node.payload?.conditions) ? node.payload.conditions : [];
    const sorted = conditions
      .map((c, i) => ({ cond: c, order: c.port_index ?? i }))
      .sort((a, b) => a.order - b.order)
      .map((item) => item.cond);
    
    return (
      <div
        onPointerDown={onPointerDown}
        onClick={onClick}
        onContextMenu={onContextMenu}
        onMouseEnter={onMouseEnter}
        onMouseLeave={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX;
          const y = e.clientY;
          const padding = 30;
          if (
            x < rect.left - padding ||
            x > rect.right + padding ||
            y < rect.top - padding ||
            y > rect.bottom + padding
          ) {
            onMouseLeave?.(e);
          }
        }}
        className={`rounded-xl border-2 cursor-grab select-none shadow-lg transition-all ${
          isSelected ? 'ring-2 ring-offset-2' : ''
        } relative`}
        style={{
          position: 'absolute',
          left: node.pos_x,
          top: node.pos_y,
          width: w,
          height: h,
          backgroundColor: c.bg,
          borderColor: isSelected ? c.accent : c.border,
          ringColor: c.accent,
          ...animStyle,
        }}
      >
        <div className="px-4 flex flex-col justify-center h-full" style={{ paddingTop: ROUTER_PADDING, paddingBottom: ROUTER_PADDING }}>
          <div className="space-y-2">
            {sorted.map((cond) => (
              <ConditionPort
                key={cond.id}
                condition={cond}
                accent={c.accent}
                border={c.border}
                isHovered={showControls}
                side={conditionSide}
                onPortPointerDown={(e) => onConditionPortPointerDown?.(node.id, cond.id, e)}
                onEdit={() => onConditionEdit?.(node.id, cond)}
                onDelete={() => onConditionDelete?.(node.id, cond.id)}
              />
            ))}
          </div>

          <button
            onPointerDown={(e) => {
              e.stopPropagation();
            }}
            onClick={(e) => {
              e.stopPropagation();
              onConditionAdd?.(node.id);
            }}
            className={`mt-2 w-full border border-dashed rounded-lg py-2 text-xs font-medium transition-colors ${
              showControls ? 'border-purple-300 text-purple-600 hover:bg-purple-50' : 'border-transparent text-transparent'
            }`}
          >
            + Добавить условие
          </button>
        </div>

        {showControls && (
          <div
            className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2"
            style={{ backgroundColor: c.bg, borderColor: c.border }}
          />
        )}
      </div>
    );
  }

  return (
    <div
      onPointerDown={onPointerDown}
      onClick={onClick}
      onContextMenu={onContextMenu}
      onMouseEnter={onMouseEnter}
      onMouseLeave={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        const x = e.clientX;
        const y = e.clientY;
        const padding = 30;
        if (
          x < rect.left - padding ||
          x > rect.right + padding ||
          y < rect.top - padding ||
          y > rect.bottom + padding
        ) {
          onMouseLeave?.(e);
        }
      }}
      className={`rounded-xl border-2 cursor-grab select-none shadow-lg transition-all ${
        isSelected ? 'ring-2 ring-offset-2' : ''
      } relative`}
      style={{
        position: 'absolute',
        left: node.pos_x,
        top: node.pos_y,
        width: w,
        height: h,
        backgroundColor: c.bg,
        borderColor: isSelected ? c.accent : c.border,
        ringColor: c.accent,
        ...animStyle,
      }}
    >
      <div className="p-3 h-full flex flex-col justify-center">
        {isTimer ? (
          <div className="text-center flex flex-col items-center justify-center">
            <div className="text-2xl font-bold mb-0.5" style={{ color: c.accent }}>
              {formatDuration(node.payload?.duration_seconds || 60)}
            </div>
            {node.payload?.show_countdown && (
              <div className="mt-0.5 text-[10px] text-slate-500">⏳</div>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-1">
            <p className="text-sm text-slate-700 line-clamp-2 leading-snug">
              {node.payload?.text || node.payload?.caption || '📷 фото'}
            </p>
            {!isTimer && node.delay_seconds > 0 && (
              <span className="text-xs text-slate-500">⏱ {node.delay_seconds}с задержка</span>
            )}
          </div>
        )}
      </div>

      {showControls && (
        <>
          {PORTS.map((port) => (
            <div
              key={port.side}
              style={{ ...port.style, borderColor: c.border }}
              className="absolute w-3 h-3 rounded-full bg-white border-2 shadow-sm cursor-crosshair"
              data-port={port.side}
              onPointerDown={(e) => {
                e.stopPropagation();
                onPortPointerDown?.(node.id, port.side, e);
              }}
            />
          ))}

          {PLUS.map((plus) => (
            <div
              key={plus.side}
              style={plus.style}
              className="absolute w-4 h-4 rounded bg-white border border-slate-300 text-[10px] font-bold flex items-center justify-center cursor-pointer"
              onPointerDown={(e) => {
                e.stopPropagation();
              }}
              onPointerUp={(e) => {
                e.stopPropagation();
                onAddFromSide?.(node.id, plus.side, e);
              }}
            >
              +
            </div>
          ))}
        </>
      )}
    </div>
  );
}

function ConditionPort({ condition, accent, border, isHovered, side, onPortPointerDown, onEdit, onDelete }) {
  const [localHover, setLocalHover] = useState(false);
  const label = condition.label || formatRouterConditionLabel(condition);
  
  // Определяем стили выдвижения в зависимости от стороны
  const getExtrusionStyle = () => {
    const extrusion = 5; // Величина выдвижения в пикселях
    
    switch(side) {
      case 'right':
        return {
          marginRight: `-${extrusion}px`,  // Выдвигаем вправо наружу
          paddingRight: `${extrusion + 12}px`, // Компенсируем padding
        };
      case 'left':
        return {
          marginLeft: `-${extrusion}px`,   // Выдвигаем влево наружу
          paddingLeft: `${extrusion + 12}px`,
        };
      case 'top':
        return {
          marginTop: `-${extrusion}px`,    // Выдвигаем вверх наружу
          paddingTop: `${extrusion + 8}px`,
        };
      case 'bottom':
        return {
          marginBottom: `-${extrusion}px`, // Выдвигаем вниз наружу
          paddingBottom: `${extrusion + 8}px`,
        };
      default:
        return {};
    }
  };

  // Определяем позицию порта в зависимости от стороны
  const getPortPosition = () => {
    const portSize = 16; // 4 * 4px (w-4 h-4)
    
    switch(side) {
      case 'right':
        return {
          right: -8,
          top: '50%',
          transform: 'translateY(-50%)',
        };
      case 'left':
        return {
          left: -8,
          top: '50%',
          transform: 'translateY(-50%)',
        };
      case 'top':
        return {
          top: -8,
          left: '50%',
          transform: 'translateX(-50%)',
        };
      case 'bottom':
        return {
          bottom: -8,
          left: '50%',
          transform: 'translateX(-50%)',
        };
      default:
        return { right: -8, top: '50%', transform: 'translateY(-50%)' };
    }
  };

  return (
    <div
      className="relative"
      style={getExtrusionStyle()}
      onMouseEnter={() => setLocalHover(true)}
      onMouseLeave={() => setLocalHover(false)}
      onPointerDown={(e) => {
        e.stopPropagation();
      }}
      onClick={(e) => {
        e.stopPropagation();
        onEdit?.();
      }}
    >
      <div
        className="bg-purple-50 border rounded-lg px-3 py-2 flex items-center justify-between transition-all"
        style={{
          height: CONDITION_PORT.height,
          borderColor: border,
          boxShadow: localHover ? '0 2px 8px rgba(168,85,247,0.2)' : 'none',
        }}
      >
        <span className="text-xs font-medium text-purple-900 truncate">{label}</span>
        {localHover && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete?.();
            }}
            className="text-red-600 hover:text-red-700 text-xs ml-2"
          >
            ×
          </button>
        )}
      </div>
      {(isHovered || localHover) && (
        <div
          onPointerDown={(e) => {
            e.stopPropagation();
            onPortPointerDown?.(e);
          }}
          className="absolute w-4 h-4 rounded-full bg-white border-2 cursor-crosshair hover:scale-125 transition-transform z-10"
          style={{
            ...getPortPosition(),
            borderColor: accent,
          }}
        />
      )}
    </div>
  );
}
