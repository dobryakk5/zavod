import { useState, useReducer, useRef, useCallback, useEffect } from "react";
import { NODE_W, NODE_H } from './constants';
import { uid, getNodeHeight } from './utils';
import { graphReducer } from './reducer';
import { mockApi } from './mockApi';
import { Toolbar } from './components/Toolbar';
import { NodeCard } from './components/NodeCard';
import { EdgeLine, DrawingLine } from './components/EdgeLine';
import { NodeEditorModal } from './components/NodeEditorModal';
import { ContextMenu } from './components/ContextMenu';

export default function ChainBuilder() {
  // State
  const [state, dispatch] = useReducer(graphReducer, { chain: {}, nodes: [], edges: [], dirty: false });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pan, setPan] = useState({ x: 50, y: 50 });
  const [selectedNode, setSelectedNode] = useState(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [hoveredEdge, setHoveredEdge] = useState(null);
  const [editingNode, setEditingNode] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [drawingFrom, setDrawingFrom] = useState(null);
  const [drawingTo, setDrawingTo] = useState(null);

  // Refs
  const canvasRef = useRef(null);
  const dragging = useRef(null);
  const panRef = useRef(null);

  // Load initial data
  useEffect(() => {
    mockApi.loadGraph().then(g => { 
      dispatch({ type: "LOAD", payload: g }); 
      setLoading(false); 
    });
  }, []);

  // Canvas interaction handlers
  const onCanvasMouseDown = useCallback((e) => {
    if (e.target !== canvasRef.current && e.target.tagName !== "svg") return;
    setSelectedNode(null);
    panRef.current = { startMouse: { x: e.clientX, y: e.clientY }, startPan: { ...pan } };
    e.preventDefault();
  }, [pan]);

  const onMouseMove = useCallback((e) => {
    if (dragging.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left - pan.x - dragging.current.offsetX;
      const y = e.clientY - rect.top - pan.y - dragging.current.offsetY;
      dispatch({ type: "MOVE_NODE", id: dragging.current.id, x, y });
      return;
    }
    if (panRef.current?.startMouse) {
      const dx = e.clientX - panRef.current.startMouse.x;
      const dy = e.clientY - panRef.current.startMouse.y;
      setPan({ x: panRef.current.startPan.x + dx, y: panRef.current.startPan.y + dy });
    }
    if (drawingFrom) {
      const rect = canvasRef.current.getBoundingClientRect();
      setDrawingTo({ x: e.clientX - rect.left - pan.x, y: e.clientY - rect.top - pan.y });
    }
  }, [pan, drawingFrom]);

  const onMouseUp = useCallback(() => {
    dragging.current = null;
    panRef.current = null;
    if (drawingFrom) {
      setDrawingFrom(null);
      setDrawingTo(null);
    }
  }, [drawingFrom]);

  useEffect(() => {
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => { 
      window.removeEventListener("mousemove", onMouseMove); 
      window.removeEventListener("mouseup", onMouseUp); 
    };
  }, [onMouseMove, onMouseUp]);

  // Node interaction handlers
  const onNodeMouseDown = (e, node) => {
    e.stopPropagation();
    setSelectedNode(node.id);
    const rect = canvasRef.current.getBoundingClientRect();
    dragging.current = { 
      id: node.id, 
      offsetX: e.clientX - rect.left - pan.x - node.pos_x, 
      offsetY: e.clientY - rect.top - pan.y - node.pos_y 
    };
  };

  const onPortMouseDown = (nodeId, port, routeId = null) => {
    const node = state.nodes.find(n => n.id === nodeId);
    if (!node) return;
    
    let sx = node.pos_x + NODE_W / 2;
    let sy;
    
    if (port === 'top') {
      sy = node.pos_y;
    } else if (port === 'bottom') {
      sy = node.pos_y + getNodeHeight(node);
    } else if (port === 'route' && routeId) {
      const routes = node.payload.routes || [];
      const routeIndex = routes.findIndex(r => r.id === routeId);
      sy = node.pos_y + 60 + routeIndex * 30;
    }
    
    setDrawingFrom({ nodeId, routeId, x: sx, y: sy });
    setDrawingTo({ x: sx, y: sy });
  };

  const onNodeClick = (e, node) => {
    e.stopPropagation();
    if (drawingFrom && drawingFrom.nodeId !== node.id) {
      dispatch({ 
        type: "ADD_EDGE", 
        source: drawingFrom.nodeId, 
        target: node.id,
        routeId: drawingFrom.routeId 
      });
      setDrawingFrom(null);
      setDrawingTo(null);
    }
  };

  const onNodeCtx = (e, node) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      x: e.clientX, 
      y: e.clientY,
      items: [
        { label: "✏️  Редактировать", action: () => setEditingNode(node) },
        { 
          label: node.id === state.chain.start_node_id ? "⭐ Стартовый узел" : "⭐ Сделать стартом", 
          action: () => dispatch({ type: "SET_START_NODE", id: node.id }) 
        },
        { label: "🗑️  Удалить", action: () => dispatch({ type: "DELETE_NODE", id: node.id }) },
      ],
    });
  };

  // Actions
  const handleAddNode = (nodeType = "message") => {
    const cx = (canvasRef.current?.clientWidth || 600) / 2 - pan.x - NODE_W / 2;
    const cy = (canvasRef.current?.clientHeight || 400) / 2 - pan.y - NODE_H / 2;
    
    let payload = {};
    if (nodeType === "message") {
      payload = { content_type: "text", text: "Новое сообщение" };
    } else if (nodeType === "router") {
      payload = { routes: [] };
    } else if (nodeType === "timer") {
      payload = { delay_seconds: 10 };
    }
    
    const node = { 
      id: uid(), 
      chain_id: state.chain.id, 
      node_type: nodeType, 
      payload, 
      delay_seconds: nodeType === "timer" ? 0 : 0, 
      pos_x: cx, 
      pos_y: cy 
    };
    
    dispatch({ type: "ADD_NODE", node });
  };

  const handleSave = async (status) => {
    if (status) {
      dispatch({ type: "SET_STATUS", status });
    }
    setSaving(true);
    try {
      await mockApi.saveGraph(state);
      dispatch({ type: "SAVED" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        Загрузка...
      </div>
    );
  }

  const nodeMap = Object.fromEntries(state.nodes.map(n => [n.id, n]));

  return (
    <div className="flex flex-col h-screen bg-slate-50">
      <Toolbar 
        chain={state.chain} 
        dirty={state.dirty} 
        saving={saving} 
        onSave={handleSave} 
        onAddNode={handleAddNode} 
      />

      <div className="flex-1 relative overflow-hidden">
        <div 
          ref={canvasRef} 
          onMouseDown={onCanvasMouseDown} 
          className="w-full h-full relative" 
          style={{ cursor: panRef.current?.startMouse ? 'grabbing' : 'default' }}
        >
          {/* Grid background */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            <defs>
              <pattern 
                id="grid" 
                width={40} 
                height={40} 
                patternUnits="userSpaceOnUse" 
                patternTransform={`translate(${pan.x % 40}, ${pan.y % 40})`}
              >
                <circle cx={20} cy={20} r={1} fill="#cbd5e1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>

          {/* Canvas content */}
          <div style={{ position: "absolute", left: pan.x, top: pan.y }}>
            <svg style={{ position: "absolute", overflow: "visible", pointerEvents: "none" }}>
              <g style={{ pointerEvents: "auto" }}>
                {state.edges.map(edge => {
                  const src = nodeMap[edge.source_node_id];
                  const tgt = nodeMap[edge.target_node_id];
                  if (!src || !tgt) return null;
                  return (
                    <EdgeLine
                      key={edge.id}
                      edge={edge}
                      srcNode={src}
                      tgtNode={tgt}
                      isHovered={hoveredEdge === edge.id}
                      onClick={(e) => { e.stopPropagation(); setHoveredEdge(edge.id); }}
                      onDelete={() => dispatch({ type: "DELETE_EDGE", id: edge.id })}
                    />
                  );
                })}
                {drawingFrom && drawingTo && <DrawingLine from={drawingFrom} to={drawingTo} />}
              </g>
            </svg>

            {state.nodes.map(node => (
              <NodeCard
                key={node.id}
                node={node}
                isStart={state.chain.start_node_id === node.id}
                isHovered={hoveredNode === node.id}
                isSelected={selectedNode === node.id}
                onMouseDown={e => onNodeMouseDown(e, node)}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={e => onNodeClick(e, node)}
                onPortMouseDown={onPortMouseDown}
              />
            ))}
          </div>
        </div>

        {/* Instructions */}
        <div className="absolute bottom-4 left-4 bg-white/90 backdrop-blur rounded-lg px-4 py-2 text-xs text-slate-600 shadow-lg border border-slate-200">
          <div>🖱 Тяни узлы • 🔵 Тяни из точки условия → узел • ⚙️ ПКМ на узле → меню</div>
        </div>
      </div>

      {/* Modals */}
      {editingNode && (
        <NodeEditorModal 
          node={editingNode} 
          onSave={data => { 
            dispatch({ type: "UPDATE_NODE", id: editingNode.id, data }); 
            setEditingNode(null); 
          }} 
          onClose={() => setEditingNode(null)} 
        />
      )}
      
      {contextMenu && (
        <ContextMenu 
          pos={contextMenu} 
          items={contextMenu.items} 
          onClose={() => setContextMenu(null)} 
        />
      )}
    </div>
  );
}
