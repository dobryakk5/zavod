'use client';

import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { chainsApi } from '@/lib/api/chains';

import { NODE_W, NODE_H } from './constants';
import { graphReducer } from './reducer';
import { getCurvedPath, getNodeDimensions, getPortPosition, getRouterConditionPortPosition, inferSideBetweenPoints } from './utils';

import { Alert } from './components/Alert';
import { Toolbar } from './components/Toolbar';
import { NodeCard } from './components/NodeCard';
import { EdgeLine } from './components/EdgeLine';
import { ContextMenu } from './components/ContextMenu';
import { NodeEditorModal } from './components/NodeEditorModal';
import { ConditionEditorModal } from './components/ConditionEditorModal';
import { RouterConditionModal } from './components/RouterConditionModal';

const WELCOME_CHAIN_NAME = 'Welcome';

/**
 * @param {{ className?: string; chainId?: number | null }} props
 */
export default function ChainEditor({ className = '', chainId = null } = {}) {
  const [state, dispatch] = useReducer(graphReducer, { chain: null, nodes: [], edges: [], dirty: false });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const [editingNode, setEditingNode] = useState(null);
  const [editingEdge, setEditingEdge] = useState(null);
  const [editingRouterCondition, setEditingRouterCondition] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);
  const [connectingFrom, setConnectingFrom] = useState(null);
  const [draggingLink, setDraggingLink] = useState(null);
  const [hoveredNodeId, setHoveredNodeId] = useState(null);
  const [addMenu, setAddMenu] = useState(null);
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false);

  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const panRef = useRef({ startMouse: null, startPan: null });
  const dragging = useRef(null);
  const canvasRef = useRef(null);
  const resetButtonRef = useRef(null);
  const resetPopoverRef = useRef(null);
  const positionQueueRef = useRef(new Map());
  const flushTimerRef = useRef(null);
  const deleteTimersRef = useRef(new Map());
  const pendingEdgeCreatesRef = useRef(new Set());
  const stateRef = useRef(state);
  const chainApi = useMemo(() => chainsApi.forChain(chainId), [chainId]);

  const ANIM_MS = 500;
  const makeTempId = (prefix) => `tmp_${prefix}_${Date.now()}_${Math.floor(Math.random() * 100000)}`;
  const isTempId = (id) => typeof id === 'string' && id.startsWith('tmp_');

  const makeConditionId = () => `cond_${Date.now()}_${Math.floor(Math.random() * 100000)}`;

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const flushPositions = useCallback(async () => {
    if (positionQueueRef.current.size === 0) return;
    const updates = Array.from(positionQueueRef.current.entries());
    positionQueueRef.current.clear();
    setSaving(true);
    setError(null);
    try {
      await Promise.all(
        updates.map(([nodeId, pos]) => chainApi.updateNode(nodeId, pos))
      );
      dispatch({ type: 'SAVED' });
    } catch (err) {
      setError('Не удалось сохранить позиции узлов');
    } finally {
      setSaving(false);
    }
  }, []);

  const scheduleFlush = useCallback(() => {
    if (flushTimerRef.current) {
      clearTimeout(flushTimerRef.current);
    }
    flushTimerRef.current = setTimeout(() => {
      flushPositions();
    }, 600);
  }, [flushPositions]);

  const queuePositionUpdate = useCallback((nodeId, x, y) => {
    if (isTempId(nodeId)) return;
    positionQueueRef.current.set(nodeId, { pos_x: x, pos_y: y });
    scheduleFlush();
  }, [scheduleFlush]);

  useEffect(() => {
    return () => {
      if (flushTimerRef.current) {
        clearTimeout(flushTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!resetConfirmOpen) return;
    const onPointerDown = (e) => {
      if (resetPopoverRef.current?.contains(e.target)) return;
      if (resetButtonRef.current?.contains(e.target)) return;
      setResetConfirmOpen(false);
    };
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setResetConfirmOpen(false);
    };
    window.addEventListener('pointerdown', onPointerDown);
    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('pointerdown', onPointerDown);
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [resetConfirmOpen]);

  const createNodeAt = useCallback((x, y, kind = 'message') => {
    let node_type = 'text';
    let payload = { text: 'Новое сообщение' };
    let delay_seconds = 0;

    if (kind === 'buttons') {
      node_type = 'buttons';
      payload = { text: 'Выберите вариант', buttons: ['Кнопка 1'] };
    } else if (kind === 'router') {
      node_type = 'router';
      payload = {
        label: 'Новое условие',
        description: '',
        conditions: [
          {
            id: makeConditionId(),
            condition_type: 'fallback',
            params: {},
            label: 'Любой',
            port_index: 0,
          },
        ],
      };
    } else if (kind === 'timer') {
      node_type = 'timer';
      payload = {
        duration_seconds: 60,
        show_countdown: false,
        countdown_message: null,
      };
      delay_seconds = 0;
    }

    const tempId = makeTempId('node');
    const tempNode = {
      id: tempId,
      node_type,
      payload,
      delay_seconds,
      pos_x: x,
      pos_y: y,
      __anim: 'enter',
    };

    dispatch({ type: 'ADD_NODE', node: tempNode });
    requestAnimationFrame(() => {
      dispatch({ type: 'CLEAR_NODE_ANIM', id: tempId });
    });

    (async () => {
      setSaving(true);
      setError(null);
      try {
        const created = await chainApi.createNode({
          node_type,
          payload,
          delay_seconds,
          pos_x: x,
          pos_y: y,
        });

        const stillExists = stateRef.current.nodes.some((n) => n.id === tempId);
        if (!stillExists) {
          try {
            await chainApi.deleteNode(created.id);
          } catch {
            // ignore cleanup failure
          }
          return;
        }

        const tempNode = stateRef.current.nodes.find((n) => n.id === tempId);
        const nextNode = tempNode
          ? { ...created, pos_x: tempNode.pos_x, pos_y: tempNode.pos_y }
          : created;
        dispatch({ type: 'REPLACE_NODE_ID', tempId, node: nextNode });
        if (tempNode && (tempNode.pos_x !== created.pos_x || tempNode.pos_y !== created.pos_y)) {
          queuePositionUpdate(created.id, tempNode.pos_x, tempNode.pos_y);
        }
        dispatch({ type: 'SAVED' });
      } catch (err) {
        dispatch({ type: 'DELETE_NODE', id: tempId });
        setError('Не удалось создать узел');
      } finally {
        setSaving(false);
      }
    })();

    return tempNode;
  }, []);

  const createStartWithRouter = useCallback(async () => {
    const startX = 100;
    const startY = 200;
    const routerX = startX + 340;
    const routerY = startY;
    const current = stateRef.current;
    const existingStart = current.nodes.find((n) => n.node_type === 'start');
    const existingRouter = current.nodes.find((n) => n.node_type === 'router');
    const hasStartToRouterEdge = Boolean(
      existingStart && existingRouter && current.edges.some(
        (edge) => edge.source_node_id === existingStart.id && edge.target_node_id === existingRouter.id
      )
    );

    if (existingStart && existingRouter && hasStartToRouterEdge) return;

    setSaving(true);
    setError(null);
    try {
      let startNodeId = existingStart?.id;
      if (!startNodeId) {
        const createdStart = await chainApi.createNode({
          node_type: 'start',
          payload: {
            text: 'Привет! Выберите вариант:',
            buttons: [
              'Да',
              'Нет',
            ],
          },
          delay_seconds: 0,
          pos_x: startX,
          pos_y: startY,
        });
        startNodeId = createdStart.id;
      }

      let routerNodeId = existingRouter?.id;
      if (!routerNodeId) {
        const createdRouter = await chainApi.createNode({
          node_type: 'router',
          payload: {
            conditions: [
              {
                id: makeConditionId(),
                condition_type: 'button_press',
                params: { button_label: 'Да' },
                label: 'Кнопка: Да',
                port_index: 0,
              },
              {
                id: makeConditionId(),
                condition_type: 'button_press',
                params: { button_label: 'Нет' },
                label: 'Кнопка: Нет',
                port_index: 1,
              },
              {
                id: makeConditionId(),
                condition_type: 'fallback',
                params: {},
                label: 'Любой другой',
                port_index: 2,
              },
            ],
          },
          delay_seconds: 0,
          pos_x: routerX,
          pos_y: routerY,
        });
        routerNodeId = createdRouter.id;
      }

      if (!hasStartToRouterEdge && startNodeId && routerNodeId) {
        await chainApi.createEdge({
          source_node_id: startNodeId,
          target_node_id: routerNodeId,
          priority: 0,
          source_port_id: null,
        });
      }

      // 4. Перезагружаем граф
      const graph = await chainApi.getGraph();
      dispatch({ type: 'LOAD', payload: graph });
    } catch (err) {
      setError('Не удалось создать начальные узлы');
    } finally {
      setSaving(false);
    }
  }, [chainApi]);

  const createStartOnly = useCallback(async () => {
    const existing = stateRef.current.nodes.find((n) => n.node_type === 'start');
    if (existing) return;

    const startX = 100;
    const startY = 200;

    setSaving(true);
    setError(null);
    try {
      await chainApi.createNode({
        node_type: 'start',
        payload: {
          text: '',
          buttons: [],
        },
        delay_seconds: 0,
        pos_x: startX,
        pos_y: startY,
      });

      const graph = await chainApi.getGraph();
      dispatch({ type: 'LOAD', payload: graph });
    } catch (err) {
      setError('Не удалось создать стартовый узел');
    } finally {
      setSaving(false);
    }
  }, [chainApi]);

  const createInitialNodes = useCallback(async (chainName) => {
    if (chainName === WELCOME_CHAIN_NAME) {
      await createStartWithRouter();
      return;
    }
    await createStartOnly();
  }, [createStartOnly, createStartWithRouter]);

  useEffect(() => {
    let isActive = true;
    chainApi.getGraph()
      .then(async (graph) => {
        if (!isActive) return;
        dispatch({ type: 'LOAD', payload: graph });
        setLoading(false);
        const hasStartNode = graph.nodes.some((node) => node.node_type === 'start');
        const hasRouterNode = graph.nodes.some((node) => node.node_type === 'router');

        if (graph.chain?.name === WELCOME_CHAIN_NAME) {
          if (!hasStartNode || !hasRouterNode) {
            await createStartWithRouter();
          }
        } else if (!hasStartNode) {
          await createStartOnly();
        }
      })
      .catch(() => {
        if (!isActive) return;
        setError('Не удалось загрузить цепочку');
        setLoading(false);
      });
    return () => {
      isActive = false;
    };
  }, [chainApi, createStartOnly, createStartWithRouter]);

  const updateNode = useCallback(async (nodeId, data) => {
    const prev = stateRef.current.nodes.find((n) => n.id === nodeId);
    dispatch({ type: 'UPDATE_NODE', id: nodeId, data });

    if (isTempId(nodeId)) {
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const updated = await chainApi.updateNode(nodeId, data);
      dispatch({ type: 'UPDATE_NODE', id: nodeId, data: updated });
      dispatch({ type: 'SAVED' });
    } catch (err) {
      if (prev) dispatch({ type: 'UPDATE_NODE', id: nodeId, data: prev });
      setError('Не удалось обновить узел');
    } finally {
      setSaving(false);
    }
  }, []);

  const deleteNode = useCallback(async (nodeId) => {
    const node = stateRef.current.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const relatedEdges = stateRef.current.edges.filter(
      (e) => e.source_node_id === nodeId || e.target_node_id === nodeId
    );

    dispatch({ type: 'MARK_NODE_EXITING', id: nodeId });
    const timer = setTimeout(() => {
      dispatch({ type: 'DELETE_NODE', id: nodeId, keepDirty: true });
      deleteTimersRef.current.delete(`node:${nodeId}`);
    }, ANIM_MS);
    deleteTimersRef.current.set(`node:${nodeId}`, { type: 'node', timer, node, edges: relatedEdges });

    if (isTempId(nodeId)) {
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await chainApi.deleteNode(nodeId);
      dispatch({ type: 'SAVED' });
    } catch (err) {
      const pending = deleteTimersRef.current.get(`node:${nodeId}`);
      if (pending) {
        clearTimeout(pending.timer);
        deleteTimersRef.current.delete(`node:${nodeId}`);
        dispatch({ type: 'CLEAR_NODE_ANIM', id: nodeId });
        relatedEdges.forEach((edge) => dispatch({ type: 'CLEAR_EDGE_ANIM', id: edge.id }));
      } else {
        dispatch({ type: 'RESTORE_NODE', node, edges: relatedEdges });
      }
      setError('Не удалось удалить узел');
    } finally {
      setSaving(false);
    }
  }, []);

  const setStartNode = useCallback(async (nodeId) => {
    if (!state.chain) return;
    setSaving(true);
    setError(null);
    try {
      await chainApi.updateChain({ start_node_id: nodeId });
      dispatch({ type: 'SET_START_NODE', id: nodeId });
      dispatch({ type: 'SAVED' });
    } catch (err) {
      setError('Не удалось обновить стартовый узел');
    } finally {
      setSaving(false);
    }
  }, [state.chain]);

  const createEdgeOnServer = useCallback(async (edge) => {
    if (pendingEdgeCreatesRef.current.has(edge.id)) return;
    pendingEdgeCreatesRef.current.add(edge.id);

    const currentEdge = stateRef.current.edges.find((e) => e.id === edge.id) || edge;

    setSaving(true);
    setError(null);
    try {
      const created = await chainApi.createEdge({
        source_node_id: currentEdge.source_node_id,
        target_node_id: currentEdge.target_node_id,
        priority: currentEdge.priority || 0,
        source_port_id: currentEdge.source_port_id || null,
      });

      const stillExists = stateRef.current.edges.some((e) => e.id === edge.id);
      if (!stillExists) {
        try {
          await chainApi.deleteEdge(created.id);
        } catch {
          // ignore cleanup failure
        }
        return;
      }

      dispatch({ type: 'REPLACE_EDGE_ID', tempId: edge.id, edge: { ...created, conditions: currentEdge.conditions || [] } });
      dispatch({ type: 'SAVED' });
    } catch (err) {
      dispatch({ type: 'DELETE_EDGE', id: edge.id });
      setError('Не удалось создать ребро');
    } finally {
      pendingEdgeCreatesRef.current.delete(edge.id);
      setSaving(false);
    }
  }, []);

  const createEdge = useCallback(async (sourceId, targetId, sourcePortId = null) => {
    const edges = stateRef.current.edges.filter((edge) => edge.__anim !== 'exit');
    const existing = sourcePortId
      ? edges.find((edge) => (
        edge.source_node_id === sourceId
        && edge.source_port_id === sourcePortId
      ))
      : null;

    if (!sourcePortId && edges.some((edge) => edge.source_node_id === sourceId && edge.target_node_id === targetId && !edge.source_port_id)) {
      return;
    }

    if (existing) {
      if (existing.target_node_id === targetId) return;
      const prev = { ...existing };
      dispatch({ type: 'UPDATE_EDGE', id: existing.id, data: { target_node_id: targetId } });

      if (isTempId(existing.id) || isTempId(sourceId) || isTempId(targetId)) {
        return;
      }

      setSaving(true);
      setError(null);
      try {
        const updated = await chainApi.updateEdge(existing.id, { target_node_id: targetId });
        dispatch({ type: 'UPDATE_EDGE', id: existing.id, data: { ...updated, conditions: existing.conditions || [] } });
        dispatch({ type: 'SAVED' });
      } catch (err) {
        dispatch({ type: 'UPDATE_EDGE', id: existing.id, data: prev });
        setError('Не удалось обновить ребро');
      } finally {
        setSaving(false);
      }
      return;
    }

    const priorities = edges
      .filter((edge) => edge.source_node_id === sourceId)
      .map((edge) => edge.priority || 0);
    const nextPriority = priorities.length ? Math.max(...priorities) + 1 : 0;

    const tempId = makeTempId('edge');
    const tempEdge = {
      id: tempId,
      source_node_id: sourceId,
      target_node_id: targetId,
      priority: nextPriority,
      source_port_id: sourcePortId || null,
      conditions: [],
      __anim: 'enter',
      __pendingCreate: true,
    };

    dispatch({ type: 'ADD_EDGE', edge: tempEdge });
    requestAnimationFrame(() => {
      dispatch({ type: 'CLEAR_EDGE_ANIM', id: tempId });
    });

    if (isTempId(sourceId) || isTempId(targetId)) {
      return;
    }

    await createEdgeOnServer(tempEdge);
  }, []);

  useEffect(() => {
    const pending = state.edges.filter((edge) => (
      edge.__pendingCreate
      && edge.__anim !== 'exit'
      && !isTempId(edge.source_node_id)
      && !isTempId(edge.target_node_id)
    ));
    pending.forEach((edge) => {
      void createEdgeOnServer(edge);
    });
  }, [state.edges, createEdgeOnServer]);

  const deleteEdge = useCallback(async (edgeId) => {
    const edge = stateRef.current.edges.find((e) => e.id === edgeId);
    if (!edge) return;

    dispatch({ type: 'MARK_EDGE_EXITING', id: edgeId });
    const timer = setTimeout(() => {
      dispatch({ type: 'DELETE_EDGE', id: edgeId, keepDirty: true });
      deleteTimersRef.current.delete(`edge:${edgeId}`);
    }, ANIM_MS);
    deleteTimersRef.current.set(`edge:${edgeId}`, { type: 'edge', timer, edge });

    if (isTempId(edgeId)) {
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await chainApi.deleteEdge(edgeId);
      dispatch({ type: 'SAVED' });
    } catch (err) {
      const pending = deleteTimersRef.current.get(`edge:${edgeId}`);
      if (pending) {
        clearTimeout(pending.timer);
        deleteTimersRef.current.delete(`edge:${edgeId}`);
        dispatch({ type: 'CLEAR_EDGE_ANIM', id: edgeId });
      } else {
        dispatch({ type: 'RESTORE_EDGE', edge });
      }
      setError('Не удалось удалить ребро');
    } finally {
      setSaving(false);
    }
  }, []);

  const saveEdgeConditions = useCallback(async (edgeId, nextConditions) => {
    if (isTempId(edgeId)) {
      dispatch({ type: 'UPDATE_EDGE_CONDITIONS', edgeId, conditions: nextConditions });
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const edge = stateRef.current.edges.find((item) => item.id === edgeId);
      const existing = edge?.conditions || [];
      const existingIds = existing
        .map((cond) => cond.id)
        .filter((id) => typeof id === 'number' && id > 0);

      await Promise.all(existingIds.map((id) => chainApi.deleteCondition(edgeId, id)));

      const created = [];
      for (const condition of nextConditions) {
        const payload = {
          condition_type: condition.condition_type,
          params: condition.params || {},
        };
        const saved = await chainApi.createCondition(edgeId, payload);
        created.push(saved);
      }

      dispatch({ type: 'UPDATE_EDGE_CONDITIONS', edgeId, conditions: created });
      dispatch({ type: 'SAVED' });
    } catch (err) {
      setError('Не удалось сохранить условия');
    } finally {
      setSaving(false);
    }
  }, []);

  const saveRouterCondition = useCallback(async (nodeId, condition) => {
    const node = stateRef.current.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const current = Array.isArray(node.payload?.conditions) ? [...node.payload.conditions] : [];
    const isFallback = condition.condition_type === 'fallback';
    const existingIndex = current.findIndex((c) => c.id === condition.id);

    let next = current.filter((c) => !(isFallback && c.condition_type === 'fallback' && c.id !== condition.id));
    if (existingIndex >= 0) {
      next = next.map((c) => (c.id === condition.id ? { ...c, ...condition } : c));
    } else {
      next.push({
        ...condition,
        id: condition.id || makeConditionId(),
      });
    }

    next = next.map((c, i) => ({ ...c, port_index: i }));
    await updateNode(nodeId, { payload: { ...node.payload, conditions: next } });
  }, [updateNode]);

  const deleteRouterCondition = useCallback(async (nodeId, conditionId) => {
    const node = stateRef.current.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const current = Array.isArray(node.payload?.conditions) ? node.payload.conditions : [];
    const next = current.filter((c) => c.id !== conditionId).map((c, i) => ({ ...c, port_index: i }));
    await updateNode(nodeId, { payload: { ...node.payload, conditions: next } });
    const edgesToDelete = stateRef.current.edges.filter((edge) => (
      edge.source_node_id === nodeId && edge.source_port_id === conditionId
    ));
    for (const edge of edgesToDelete) {
      await deleteEdge(edge.id);
    }
  }, [updateNode, deleteEdge]);

  const onCanvasPointerDown = useCallback((e) => {
    if (e.target !== canvasRef.current && e.target.tagName !== 'svg') return;
    panRef.current = { startMouse: { x: e.clientX, y: e.clientY }, startPan: { ...pan } };
    e.preventDefault();
  }, [pan]);

  const onWheel = useCallback((e) => {
    e.preventDefault();
    const delta = e.deltaY;
    const zoomSpeed = 0.001;
    const minZoom = 0.1;
    const maxZoom = 3;
    
    setZoom((prevZoom) => {
      const nextZoom = prevZoom - delta * zoomSpeed;
      return Math.max(minZoom, Math.min(maxZoom, nextZoom));
    });
  }, []);

  const onPointerMove = useCallback((e) => {
    if (draggingLink) {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = (e.clientX - rect.left - pan.x) / zoom;
      const y = (e.clientY - rect.top - pan.y) / zoom;
      setDraggingLink((prev) => (prev ? { ...prev, x, y } : prev));
      return;
    }
    if (dragging.current) {
      const rect = canvasRef.current.getBoundingClientRect();
      const x = (e.clientX - rect.left - pan.x) / zoom - dragging.current.offsetX;
      const y = (e.clientY - rect.top - pan.y) / zoom - dragging.current.offsetY;
      dispatch({ type: 'MOVE_NODE', id: dragging.current.id, x, y });
      queuePositionUpdate(dragging.current.id, x, y);
      return;
    }
    if (panRef.current?.startMouse) {
      const dx = e.clientX - panRef.current.startMouse.x;
      const dy = e.clientY - panRef.current.startMouse.y;
      setPan({ x: panRef.current.startPan.x + dx, y: panRef.current.startPan.y + dy });
    }
  }, [pan, zoom, queuePositionUpdate, draggingLink]);

  const findNodeAtPoint = useCallback((x, y) => {
    const scaledX = x / zoom;
    const scaledY = y / zoom;
    for (let i = state.nodes.length - 1; i >= 0; i -= 1) {
      const node = state.nodes[i];
      const { w, h } = getNodeDimensions(node);
      if (scaledX >= node.pos_x && scaledX <= node.pos_x + w && scaledY >= node.pos_y && scaledY <= node.pos_y + h) {
        return node;
      }
    }
    return null;
  }, [state.nodes, zoom]);

  const onPointerUp = useCallback((e) => {
    if (draggingLink) {
      let targetId = null;
      if (canvasRef.current && e?.clientX != null && e?.clientY != null) {
        const rect = canvasRef.current.getBoundingClientRect();
        const x = e.clientX - rect.left - pan.x;
        const y = e.clientY - rect.top - pan.y;
        const targetNode = findNodeAtPoint(x, y);
        if (targetNode) targetId = targetNode.id;
      }
      if (!targetId && hoveredNodeId) {
        targetId = hoveredNodeId;
      }
      if (targetId && targetId !== draggingLink.sourceId) {
        createEdge(draggingLink.sourceId, targetId, draggingLink.sourcePortId || null);
      }
      setDraggingLink(null);
    }
    dragging.current = null;
    panRef.current = null;
  }, [createEdge, draggingLink, findNodeAtPoint, hoveredNodeId, pan]);

  useEffect(() => {
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    return () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
  }, [onPointerMove, onPointerUp]);

  const onNodePointerDown = (e, node) => {
    e.stopPropagation();
    const rect = canvasRef.current.getBoundingClientRect();
    dragging.current = {
      id: node.id,
      offsetX: (e.clientX - rect.left - pan.x) / zoom - node.pos_x,
      offsetY: (e.clientY - rect.top - pan.y) / zoom - node.pos_y,
    };
  };

  const onNodeClick = (e, node) => {
    e.stopPropagation();
    if (connectingFrom !== null) {
      if (connectingFrom !== node.id) {
        createEdge(connectingFrom, node.id);
      }
      setConnectingFrom(null);
      return;
    }
  };

  const onNodeCtx = (e, node) => {
    e.preventDefault();
    e.stopPropagation();
    setAddMenu(null);
    const isRouter = node.node_type === 'router';
    const isStartNode = node.node_type === 'start';
    
    // START узел нельзя удалить
    if (isStartNode) {
      setContextMenu({
        x: e.clientX, y: e.clientY,
        items: [
          { label: '✏️  Редактировать', action: () => setEditingNode(node) },
        ],
      });
      return;
    }
    
    setContextMenu({
      x: e.clientX, y: e.clientY,
      items: [
        { label: '✏️  Редактировать', action: () => setEditingNode(node) },
        ...(!isRouter ? [{ label: '🔗  Провести ребро', action: () => setConnectingFrom(node.id) }] : []),
        { label: '🗑️  Удалить', action: () => deleteNode(node.id) },
      ],
    });
  };

  const onPortPointerDown = (nodeId, side, e) => {
    if (!canvasRef.current) return;
    setConnectingFrom(null);
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left - pan.x) / zoom;
    const y = (e.clientY - rect.top - pan.y) / zoom;
    setDraggingLink({ sourceId: nodeId, side, x, y, sourcePortId: null });
  };

  const onConditionPortPointerDown = (nodeId, conditionId, e) => {
    if (!canvasRef.current) return;
    setConnectingFrom(null);
    const node = state.nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left - pan.x) / zoom;
    const y = (e.clientY - rect.top - pan.y) / zoom;
    const port = getRouterConditionPortPosition(node, conditionId);
    setDraggingLink({
      sourceId: nodeId,
      side: 'right',
      x: port?.x ?? x,
      y: port?.y ?? y,
      sourcePortId: conditionId,
    });
  };

  const addNodeFromSide = useCallback(async (nodeId, side, kind = 'message') => {
    const source = state.nodes.find((n) => n.id === nodeId);
    if (!source) return;
    const gap = 120;
    let x = source.pos_x;
    let y = source.pos_y;
    switch (side) {
      case 'top':
        y = source.pos_y - NODE_H - gap;
        break;
      case 'right':
        x = source.pos_x + NODE_W + gap;
        break;
      case 'bottom':
        y = source.pos_y + NODE_H + gap;
        break;
      case 'left':
        x = source.pos_x - NODE_W - gap;
        break;
      default:
        break;
    }
    const created = await createNodeAt(x, y, kind);
    if (created) {
      await createEdge(source.id, created.id);
    }
  }, [createEdge, createNodeAt, state.nodes]);

  const openAddMenu = (nodeId, side, e) => {
    setContextMenu(null);
    setAddMenu({ nodeId, side, x: e.clientX, y: e.clientY });
  };

  const onEdgeClick = (e, edge) => {
    e.stopPropagation();
    const srcNode = nodeMap[edge.source_node_id];
    if (srcNode?.node_type === 'router') {
      const conditions = srcNode.payload?.conditions || [];
      const cond = conditions.find((c) => c.id === edge.source_port_id);
      if (cond) {
        setEditingRouterCondition({ nodeId: srcNode.id, condition: cond });
      }
      return;
    }
    setEditingEdge(edge);
  };

  const onCanvasDblClick = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    createNodeAt(
      (e.clientX - rect.left - pan.x) / zoom - NODE_W / 2,
      (e.clientY - rect.top - pan.y) / zoom - NODE_H / 2
    );
  };

  const handleAddNode = (kind = 'message') => {
    const cx = ((canvasRef.current?.clientWidth || 600) / 2 - pan.x) / zoom - NODE_W / 2;
    const cy = ((canvasRef.current?.clientHeight || 400) / 2 - pan.y) / zoom - NODE_H / 2;
    createNodeAt(cx, cy, kind);
  };

  const handleStatusChange = async (newStatus) => {
    setSaving(true);
    setError(null);
    try {
      await chainApi.updateChain({ status: newStatus });
      dispatch({ type: 'SET_STATUS', status: newStatus });
      dispatch({ type: 'SAVED' });
    } catch (err) {
      setError('Не удалось обновить статус цепочки');
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    await flushPositions();
  };

  const handleResetChain = useCallback(async () => {
    if (saving) return;
    setResetConfirmOpen(false);
    setContextMenu(null);
    setAddMenu(null);

    const current = stateRef.current;
    const edgesToDelete = current.edges.filter((edge) => !isTempId(edge.id));
    const nodesToDelete = current.nodes.filter((node) => node.node_type !== 'start' && !isTempId(node.id));

    if (edgesToDelete.length === 0 && nodesToDelete.length === 0) {
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (edgesToDelete.length) {
        await Promise.all(edgesToDelete.map((edge) => chainApi.deleteEdge(edge.id)));
      }
      if (nodesToDelete.length) {
        await Promise.all(nodesToDelete.map((node) => chainApi.deleteNode(node.id)));
      }
      const graph = await chainApi.getGraph();
      dispatch({ type: 'LOAD', payload: graph });
      // После сброса пересоздаём базовые узлы для текущей цепочки
      await createInitialNodes(current.chain?.name);
    } catch (err) {
      setError('Не удалось очистить цепочку');
      try {
        const graph = await chainApi.getGraph();
        dispatch({ type: 'LOAD', payload: graph });
      } catch {
        // ignore reload failure
      }
    } finally {
      setSaving(false);
    }
  }, [saving, chainApi, createInitialNodes]);

  if (loading) return <div className="min-h-[400px] flex items-center justify-center text-slate-600">Загрузка...</div>;
  if (!state.chain) return <div className="min-h-[400px] flex items-center justify-center text-slate-600">Цепочка недоступна</div>;

  const nodeMap = Object.fromEntries(state.nodes.map(n => [n.id, n]));

  return (
    <div className={`flex flex-col h-full min-h-[600px] bg-slate-50 ${className}`}>
      <Toolbar
        chain={state.chain}
        dirty={state.dirty}
        saving={saving}
        onSave={handleSave}
        onAddNode={handleAddNode}
        onStatusChange={handleStatusChange}
      />

      {error && (
        <div className="px-6 py-3 bg-red-50 border-b border-red-200">
          <Alert variant="error">{error}</Alert>
        </div>
      )}

      {connectingFrom && (
        <div className="px-6 py-3 bg-blue-50 border-b border-blue-200 flex items-center justify-center gap-4">
          <span className="text-sm text-blue-900">🔗 Кликните на целевой узел для соединения</span>
          <button onClick={() => setConnectingFrom(null)} className="text-sm text-blue-700 underline">отменить</button>
        </div>
      )}

      <div className="flex-1 relative overflow-hidden">
        <div
          ref={canvasRef}
          onPointerDown={onCanvasPointerDown}
          onDoubleClick={onCanvasDblClick}
          onContextMenu={e => e.preventDefault()}
          onWheel={onWheel}
          className="w-full h-full relative cursor-grab"
        >
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            <defs>
              <pattern id="grid" width={32} height={32} patternUnits="userSpaceOnUse" patternTransform={`translate(${pan.x % 32}, ${pan.y % 32}) scale(${zoom})`}>
                <circle cx={16} cy={16} r={1} fill="#cbd5e1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
          </svg>

          <div style={{ position: 'absolute', left: pan.x, top: pan.y, width: 0, height: 0, transform: `scale(${zoom})`, transformOrigin: '0 0' }}>
            <svg 
              style={{ position: 'absolute', overflow: 'visible', left: 0, top: 0, pointerEvents: 'none' }}
              width="5000"
              height="5000"
            >
              <g style={{ pointerEvents: 'auto' }}>
                {draggingLink && (() => {
                  const sourceNode = nodeMap[draggingLink.sourceId];
                  if (!sourceNode) return null;
                  const start = draggingLink.sourcePortId
                    ? (getRouterConditionPortPosition(sourceNode, draggingLink.sourcePortId) || getPortPosition(sourceNode, 'right'))
                    : getPortPosition(sourceNode, draggingLink.side);
                  const side = draggingLink.sourcePortId ? 'right' : draggingLink.side;
                  const dir = side === 'top'
                    ? { x: 0, y: -1 }
                    : side === 'bottom'
                      ? { x: 0, y: 1 }
                      : side === 'left'
                        ? { x: -1, y: 0 }
                        : { x: 1, y: 0 };
                  const stub = { x: start.x + dir.x * 16, y: start.y + dir.y * 16 };
                  const end = { x: draggingLink.x, y: draggingLink.y };
                  const endSide = inferSideBetweenPoints(end, stub);
                  const path = getCurvedPath(stub, side, end, endSide);
                  return (
                    <>
                      <path
                        d={`M ${start.x} ${start.y} L ${stub.x} ${stub.y}`}
                        fill="none"
                        stroke="#2563eb"
                        strokeWidth={2}
                        strokeDasharray="5 4"
                        strokeLinecap="round"
                        pointerEvents="none"
                      />
                      <path
                        d={path}
                        fill="none"
                        stroke="#2563eb"
                        strokeWidth={2}
                        strokeDasharray="5 4"
                        strokeLinecap="round"
                        pointerEvents="none"
                      />
                    </>
                  );
                })()}
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
                      isSelected={false}
                      conditions={edge.conditions || []}
                      onClick={(e) => onEdgeClick(e, edge)}
                    />
                  );
                })}
              </g>
            </svg>

            {state.nodes.map(node => (
              <NodeCard
                key={node.id}
                node={node}
                isSelected={connectingFrom === node.id}
                isHovered={hoveredNodeId === node.id}
                onPointerDown={e => onNodePointerDown(e, node)}
                onClick={e => onNodeClick(e, node)}
                onContextMenu={e => onNodeCtx(e, node)}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId((prev) => (prev === node.id ? null : prev))}
                onPortPointerDown={onPortPointerDown}
                onConditionPortPointerDown={onConditionPortPointerDown}
                onConditionAdd={(nodeId) => setEditingRouterCondition({ nodeId, condition: null })}
                onConditionEdit={(nodeId, condition) => setEditingRouterCondition({ nodeId, condition })}
                onConditionDelete={deleteRouterCondition}
                onAddFromSide={openAddMenu}
                onNodeUpdate={updateNode}
              />
            ))}
          </div>
        </div>

        <div className="absolute bottom-0 left-0 right-0 bg-white/90 backdrop-blur border-t border-slate-200 px-6 py-2 flex gap-6 text-xs text-slate-500">
          <span>Двойной клик — добавить узел</span>
          <span>Правый клик — контекст</span>
          <span>Клик на ребро — условия</span>
          <div className="flex items-center gap-2">
            <span>Колесо мыши — масштаб</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setZoom(z => Math.max(0.1, z - 0.1))}
                className="w-6 h-6 rounded border border-slate-300 hover:bg-slate-100 flex items-center justify-center text-slate-600"
                title="Уменьшить"
              >
                −
              </button>
              <span className="text-xs text-slate-600 font-mono w-12 text-center">
                {Math.round(zoom * 100)}%
              </span>
              <button
                onClick={() => setZoom(z => Math.min(3, z + 0.1))}
                className="w-6 h-6 rounded border border-slate-300 hover:bg-slate-100 flex items-center justify-center text-slate-600"
                title="Увеличить"
              >
                +
              </button>
              <button
                onClick={() => setZoom(1)}
                className="px-2 py-1 rounded border border-slate-300 hover:bg-slate-100 text-slate-600"
                title="Сбросить масштаб"
              >
                100%
              </button>
            </div>
          </div>
          <span>{state.dirty && !saving && '● Несохранённые изменения'}</span>
          {saving && <span>💾 Сохранение...</span>}
          <div className="ml-auto flex items-center gap-4">
            <div className="relative flex items-center">
              <button
                ref={resetButtonRef}
                type="button"
                onClick={() => setResetConfirmOpen(true)}
                className={`text-xs text-red-500 hover:text-red-600 ${saving ? 'opacity-60 cursor-not-allowed' : ''}`}
                disabled={saving}
              >
                Сброс
              </button>
              {resetConfirmOpen && (
                <div
                  ref={resetPopoverRef}
                  className="absolute bottom-full right-0 mb-2 z-30 bg-white border border-slate-200 rounded-lg shadow-xl px-3 py-2 text-xs text-slate-700"
                >
                  <div className="mb-2 whitespace-nowrap">Очистить цепочку сообщений?</div>
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={handleResetChain}
                      className="px-2 py-1 rounded border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                    >
                      Да
                    </button>
                    <button
                      type="button"
                      onClick={() => setResetConfirmOpen(false)}
                      className="px-2 py-1 rounded border border-slate-200 bg-slate-50 text-slate-600 hover:bg-slate-100"
                    >
                      Нет
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {editingNode && (
        <NodeEditorModal
          node={editingNode}
          onSave={async data => {
            await updateNode(editingNode.id, data);
            setEditingNode(null);
          }}
          onClose={() => setEditingNode(null)}
        />
      )}
      {editingEdge && (
        <ConditionEditorModal
          edge={editingEdge}
          srcNode={nodeMap[editingEdge.source_node_id]}
          tgtNode={nodeMap[editingEdge.target_node_id]}
          onSave={async conditions => {
            await saveEdgeConditions(editingEdge.id, conditions);
          }}
          onDelete={async () => {
            await deleteEdge(editingEdge.id);
          }}
          onClose={() => setEditingEdge(null)}
        />
      )}
      {editingRouterCondition && (
        <RouterConditionModal
          condition={editingRouterCondition.condition}
          onSave={async (condition) => {
            await saveRouterCondition(editingRouterCondition.nodeId, condition);
            setEditingRouterCondition(null);
          }}
          onClose={() => setEditingRouterCondition(null)}
        />
      )}
      {contextMenu && <ContextMenu pos={contextMenu} items={contextMenu.items} onClose={() => setContextMenu(null)} />}
      {addMenu && (
        <ContextMenu
          pos={addMenu}
          items={[
            { label: '💬 Сообщение', action: () => { addNodeFromSide(addMenu.nodeId, addMenu.side, 'message'); setAddMenu(null); } },
            { label: '🔘 Кнопки', action: () => { addNodeFromSide(addMenu.nodeId, addMenu.side, 'buttons'); setAddMenu(null); } },
            { label: '⏱️ Задержка', action: () => { addNodeFromSide(addMenu.nodeId, addMenu.side, 'timer'); setAddMenu(null); } },
            { label: '🔀 Условие', action: () => { addNodeFromSide(addMenu.nodeId, addMenu.side, 'router'); setAddMenu(null); } },
          ]}
          onClose={() => setAddMenu(null)}
        />
      )}
    </div>
  );
}
