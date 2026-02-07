// ═══════════════════════════════════════════════════════════════════════════
// MOCK API & DATA
// ═══════════════════════════════════════════════════════════════════════════

const MOCK_INITIAL_GRAPH = {
  chain: { id: 1, tenant_id: 1, name: "Onboarding Flow", status: "draft", start_node_id: 1 },
  nodes: [
    { 
      id: 1, 
      chain_id: 1, 
      node_type: "message", 
      payload: { content_type: "text", text: "Привет! 👋 Добро пожаловать" }, 
      delay_seconds: 0, 
      pos_x: 100, 
      pos_y: 80 
    },
    { 
      id: 2, 
      chain_id: 1, 
      node_type: "router", 
      payload: { 
        routes: [
          { id: 201, condition_type: "button_press", params: { button_label: "Продукт" } },
          { id: 202, condition_type: "button_press", params: { button_label: "Услуги" } },
          { id: 203, condition_type: "any_reply", params: {} }
        ]
      }, 
      delay_seconds: 0, 
      pos_x: 100, 
      pos_y: 280 
    },
    { 
      id: 3, 
      chain_id: 1, 
      node_type: "message", 
      payload: { content_type: "text", text: "Отлично! Расскажем про продукт" }, 
      delay_seconds: 1, 
      pos_x: -200, 
      pos_y: 520 
    },
    { 
      id: 4, 
      chain_id: 1, 
      node_type: "message", 
      payload: { content_type: "photo", photo_url: "https://picsum.photos/400", caption: "Каталог продуктов" }, 
      delay_seconds: 2, 
      pos_x: 100, 
      pos_y: 520 
    },
  ],
  edges: [
    { id: 10, chain_id: 1, source_node_id: 1, target_node_id: 2, route_id: null, priority: 0 },
    { id: 11, chain_id: 1, source_node_id: 2, target_node_id: 3, route_id: 201, priority: 0 },
    { id: 12, chain_id: 1, source_node_id: 2, target_node_id: 4, route_id: 202, priority: 1 },
  ],
};

export const mockApi = {
  loadGraph: () => Promise.resolve(JSON.parse(JSON.stringify(MOCK_INITIAL_GRAPH))),
  saveGraph: (graph) => { 
    console.log("[SAVE]", graph); 
    return Promise.resolve({ success: true }); 
  },
};
