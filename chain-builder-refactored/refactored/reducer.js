import { uid } from './utils';

// ═══════════════════════════════════════════════════════════════════════════
// REDUCER
// ═══════════════════════════════════════════════════════════════════════════

export function graphReducer(state, action) {
  switch (action.type) {
    case "LOAD":
      return { ...action.payload, dirty: false };
      
    case "MOVE_NODE": {
      const nodes = state.nodes.map(n => n.id === action.id ? { ...n, pos_x: action.x, pos_y: action.y } : n);
      return { ...state, nodes, dirty: true };
    }
    
    case "ADD_NODE": {
      const node = action.node || { 
        id: uid(), 
        chain_id: state.chain.id, 
        node_type: "message", 
        payload: { content_type: "text", text: "Новое сообщение" }, 
        delay_seconds: 0, 
        pos_x: action.x, 
        pos_y: action.y 
      };
      return { ...state, nodes: [...state.nodes, node], dirty: true };
    }
    
    case "UPDATE_NODE": {
      const nodes = state.nodes.map(n => n.id === action.id ? { ...n, ...action.data } : n);
      return { ...state, nodes, dirty: true };
    }
    
    case "DELETE_NODE": {
      const nodes = state.nodes.filter(n => n.id !== action.id);
      const edges = state.edges.filter(e => e.source_node_id !== action.id && e.target_node_id !== action.id);
      return { 
        ...state, 
        nodes, 
        edges, 
        chain: { 
          ...state.chain, 
          start_node_id: state.chain.start_node_id === action.id ? null : state.chain.start_node_id 
        }, 
        dirty: true 
      };
    }
    
    case "ADD_EDGE": {
      const exists = state.edges.some(e => 
        e.source_node_id === action.source && 
        e.target_node_id === action.target &&
        e.route_id === action.routeId
      );
      if (exists) return state;
      const edge = { 
        id: uid(), 
        chain_id: state.chain.id, 
        source_node_id: action.source, 
        target_node_id: action.target, 
        route_id: action.routeId || null,
        priority: 0 
      };
      return { ...state, edges: [...state.edges, edge], dirty: true };
    }
    
    case "DELETE_EDGE": {
      return { ...state, edges: state.edges.filter(e => e.id !== action.id), dirty: true };
    }
    
    case "SET_START_NODE":
      return { ...state, chain: { ...state.chain, start_node_id: action.id }, dirty: true };
      
    case "SET_STATUS":
      return { ...state, chain: { ...state.chain, status: action.status }, dirty: true };
      
    case "SAVED":
      return { ...state, dirty: false };
      
    default:
      return state;
  }
}
