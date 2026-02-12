// ═══════════════════════════════════════════════════════════════════════════
// REDUCER
// ═══════════════════════════════════════════════════════════════════════════

export function graphReducer(state, action) {
  switch (action.type) {
    case 'LOAD':
      return { ...action.payload, dirty: false };

    case 'MOVE_NODE': {
      const nodes = state.nodes.map(n =>
        n.id === action.id ? { ...n, pos_x: action.x, pos_y: action.y } : n
      );
      return { ...state, nodes, dirty: true };
    }

    case 'ADD_NODE': {
      return { ...state, nodes: [...state.nodes, action.node], dirty: true };
    }

    case 'UPDATE_NODE': {
      const nodes = state.nodes.map(n => n.id === action.id ? { ...n, ...action.data } : n);
      return { ...state, nodes, dirty: true };
    }

    case 'REPLACE_NODE_ID': {
      const nodes = state.nodes.map((n) =>
        n.id === action.tempId ? { ...action.node, __anim: n.__anim } : n
      );
      const edges = state.edges.map((e) => ({
        ...e,
        source_node_id: e.source_node_id === action.tempId ? action.node.id : e.source_node_id,
        target_node_id: e.target_node_id === action.tempId ? action.node.id : e.target_node_id,
      }));
      return { ...state, nodes, edges, dirty: true };
    }

    case 'MARK_NODE_EXITING': {
      const nodes = state.nodes.map(n =>
        n.id === action.id ? { ...n, __anim: 'exit' } : n
      );
      const edges = state.edges.map(e =>
        e.source_node_id === action.id || e.target_node_id === action.id
          ? { ...e, __anim: 'exit' }
          : e
      );
      return { ...state, nodes, edges, dirty: true };
    }

    case 'CLEAR_NODE_ANIM': {
      const nodes = state.nodes.map(n =>
        n.id === action.id ? { ...n, __anim: null } : n
      );
      return { ...state, nodes, dirty: state.dirty };
    }

    case 'RESTORE_NODE': {
      const nodeExists = state.nodes.some((n) => n.id === action.node.id);
      const nodes = nodeExists
        ? state.nodes.map((n) => (n.id === action.node.id ? { ...action.node, __anim: null } : n))
        : [...state.nodes, { ...action.node, __anim: null }];
      const edges = [...state.edges];
      (action.edges || []).forEach((edge) => {
        if (!edges.some((e) => e.id === edge.id)) {
          edges.push({ ...edge, __anim: null });
        }
      });
      return { ...state, nodes, edges, dirty: true };
    }

    case 'DELETE_NODE': {
      const nodes = state.nodes.filter(n => n.id !== action.id);
      const edges = state.edges.filter(e => e.source_node_id !== action.id && e.target_node_id !== action.id);
      const dirty = action.keepDirty ? state.dirty : true;
      if (!state.chain) return { ...state, nodes, edges, dirty };
      const startNode = state.chain.start_node_id === action.id ? null : state.chain.start_node_id;
      return { ...state, nodes, edges, chain: { ...state.chain, start_node_id: startNode }, dirty };
    }

    case 'ADD_EDGE': {
      return { ...state, edges: [...state.edges, action.edge], dirty: true };
    }

    case 'REPLACE_EDGE_ID': {
      const edges = state.edges.map((e) =>
        e.id === action.tempId ? { ...action.edge, __anim: e.__anim } : e
      );
      return { ...state, edges, dirty: true };
    }

    case 'MARK_EDGE_EXITING': {
      const edges = state.edges.map((e) =>
        e.id === action.id ? { ...e, __anim: 'exit' } : e
      );
      return { ...state, edges, dirty: true };
    }

    case 'CLEAR_EDGE_ANIM': {
      const edges = state.edges.map((e) =>
        e.id === action.id ? { ...e, __anim: null } : e
      );
      return { ...state, edges, dirty: state.dirty };
    }

    case 'RESTORE_EDGE': {
      const edgeExists = state.edges.some((e) => e.id === action.edge.id);
      const edges = edgeExists
        ? state.edges.map((e) => (e.id === action.edge.id ? { ...action.edge, __anim: null } : e))
        : [...state.edges, { ...action.edge, __anim: null }];
      return { ...state, edges, dirty: true };
    }

    case 'DELETE_EDGE': {
      return { ...state, edges: state.edges.filter(e => e.id !== action.id), dirty: action.keepDirty ? state.dirty : true };
    }

    case 'UPDATE_EDGE': {
      const edges = state.edges.map(e => e.id === action.id ? { ...e, ...action.data } : e);
      return { ...state, edges, dirty: true };
    }

    case 'UPDATE_EDGE_CONDITIONS': {
      const edges = state.edges.map(e => e.id === action.edgeId ? { ...e, conditions: action.conditions } : e);
      return { ...state, edges, dirty: true };
    }

    case 'SET_START_NODE':
      if (!state.chain) return state;
      return { ...state, chain: { ...state.chain, start_node_id: action.id }, dirty: true };

    case 'SET_STATUS':
      if (!state.chain) return state;
      return { ...state, chain: { ...state.chain, status: action.status }, dirty: true };

    case 'SAVED':
      return { ...state, dirty: false };

    default:
      return state;
  }
}
