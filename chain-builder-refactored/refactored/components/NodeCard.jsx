import { NODE_COLORS, NODE_W } from './constants';
import { getNodeHeight, getConditionLabel, formatTime } from './utils';

export function NodeCard({ 
  node, 
  isStart, 
  isHovered, 
  isSelected, 
  onMouseDown, 
  onMouseEnter, 
  onMouseLeave, 
  onClick, 
  onPortMouseDown 
}) {
  const c = NODE_COLORS[node.node_type];
  const height = getNodeHeight(node);
  
  return (
    <div
      onMouseDown={onMouseDown}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onClick}
      style={{ 
        position: "absolute", 
        left: node.pos_x, 
        top: node.pos_y, 
        width: NODE_W, 
        height: height,
        backgroundColor: c.bg,
        borderColor: isSelected ? c.accent : c.border,
        boxShadow: c.shadow,
        ringColor: c.accent,
      }}
      className={`rounded-xl border-2 cursor-move select-none transition-all ${
        isSelected ? 'ring-4 ring-offset-2' : ''
      } ${isHovered ? 'scale-105' : 'scale-100'}`}
      onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); }}
    >
      <div className="p-4 flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wide" style={{ color: c.accent }}>
            {node.node_type === "timer" ? "⏱ Таймер" : node.node_type === "router" ? "🔀 Router" : "💬 Сообщение"}
          </span>
          {isStart && <span className="text-xs">⭐</span>}
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {node.node_type === "message" && <MessageContent node={node} c={c} />}
          {node.node_type === "timer" && <TimerContent node={node} c={c} />}
          {node.node_type === "router" && <RouterContent node={node} c={c} onPortMouseDown={onPortMouseDown} />}
        </div>
        
        {/* Delay indicator */}
        {node.delay_seconds > 0 && node.node_type !== "timer" && (
          <div className="mt-2 text-xs text-slate-500">⏱ {node.delay_seconds}с</div>
        )}
      </div>

      {/* Connection ports */}
      {node.node_type !== "router" && (
        <>
          <div
            onMouseDown={(e) => { e.stopPropagation(); onPortMouseDown(node.id, 'top'); }}
            className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-white border-2 cursor-pointer hover:scale-125 transition-transform"
            style={{ borderColor: c.border }}
          />
          <div
            onMouseDown={(e) => { e.stopPropagation(); onPortMouseDown(node.id, 'bottom'); }}
            className="absolute -bottom-2 left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-white border-2 cursor-pointer hover:scale-125 transition-transform"
            style={{ borderColor: c.border }}
          />
        </>
      )}
      
      {/* Top port for router */}
      {node.node_type === "router" && (
        <div
          onMouseDown={(e) => { e.stopPropagation(); onPortMouseDown(node.id, 'top'); }}
          className="absolute -top-2 left-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-white border-2 cursor-pointer hover:scale-125 transition-transform"
          style={{ borderColor: c.border }}
        />
      )}
    </div>
  );
}

function MessageContent({ node, c }) {
  const contentType = node.payload.content_type || "text";
  
  if (contentType === "text") {
    return <p className="text-sm text-slate-700 line-clamp-2">{node.payload.text}</p>;
  }
  
  if (contentType === "photo") {
    return (
      <div>
        <div className="w-12 h-12 bg-slate-200 rounded mb-1 flex items-center justify-center text-2xl">📷</div>
        <p className="text-xs text-slate-600 line-clamp-1">{node.payload.caption || "Фото"}</p>
      </div>
    );
  }
  
  if (contentType === "video") {
    return (
      <div>
        <div className="w-12 h-12 bg-slate-200 rounded mb-1 flex items-center justify-center text-2xl">🎥</div>
        <p className="text-xs text-slate-600 line-clamp-1">{node.payload.caption || "Видео"}</p>
      </div>
    );
  }
  
  if (contentType === "audio") {
    return (
      <div>
        <div className="w-12 h-12 bg-slate-200 rounded mb-1 flex items-center justify-center text-2xl">🎵</div>
        <p className="text-xs text-slate-600 line-clamp-1">{node.payload.caption || "Аудио"}</p>
      </div>
    );
  }
  
  if (contentType === "link") {
    return (
      <div>
        <div className="text-2xl mb-1">🔗</div>
        <p className="text-xs text-slate-600 line-clamp-1">{node.payload.text || "Ссылка"}</p>
        <p className="text-xs text-slate-400 line-clamp-1 mt-1">{node.payload.url || ""}</p>
      </div>
    );
  }
  
  if (contentType === "buttons") {
    return (
      <div>
        <p className="text-xs text-slate-600 mb-2 line-clamp-1">{node.payload.text}</p>
        <div className="flex flex-wrap gap-1">
          {(node.payload.buttons || []).slice(0, 2).map((btn, i) => (
            <span key={i} className="px-2 py-1 bg-white rounded text-xs border" style={{ borderColor: c.border }}>
              {btn}
            </span>
          ))}
          {(node.payload.buttons || []).length > 2 && (
            <span className="text-xs text-slate-400">+{(node.payload.buttons || []).length - 2}</span>
          )}
        </div>
      </div>
    );
  }
  
  return <p className="text-xs text-slate-500">Пустое сообщение</p>;
}

function TimerContent({ node, c }) {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <div className="text-4xl mb-2">⏱</div>
      <div className="text-lg font-bold text-center" style={{ color: c.accent }}>
        {formatTime(node.payload.delay_seconds || 0)}
      </div>
    </div>
  );
}

function RouterContent({ node, c, onPortMouseDown }) {
  return (
    <div className="space-y-1">
      {(node.payload.routes || []).map((route) => (
        <div 
          key={route.id} 
          className="flex items-center gap-2 bg-white rounded px-2 py-1.5 border relative group"
          style={{ borderColor: c.border }}
        >
          <span className="text-xs flex-1 truncate">{getConditionLabel(route)}</span>
          <div
            onMouseDown={(e) => { e.stopPropagation(); onPortMouseDown(node.id, 'route', route.id); }}
            className="w-3 h-3 rounded-full bg-white border-2 cursor-pointer hover:scale-125 transition-transform flex-shrink-0"
            style={{ borderColor: c.accent }}
            title="Создать связь"
          />
        </div>
      ))}
    </div>
  );
}
