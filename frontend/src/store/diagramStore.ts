import { create } from 'zustand';
import { Node as RFNode, Edge, Connection, addEdge, applyNodeChanges, applyEdgeChanges, NodeChange, EdgeChange } from '@xyflow/react';

interface DiagramState {
  nodes: RFNode[];
  edges: Edge[];
  selectedNode: RFNode | null;
  editingEdgeId: string | null;
  onNodesChange: (changes: NodeChange<RFNode>[]) => void;
  onEdgesChange: (changes: EdgeChange[]) => void;
  onConnect: (connection: Connection) => void;
  addNode: (node: RFNode) => void;
  addNodesFromArchitecture: (nodes: RFNode[], connections: { from: string; to: string; label?: string }[]) => void;
  replaceDiagram: (nodes: RFNode[], connections: { from: string; to: string; label?: string }[]) => void;
  loadDiagram: (nodes: RFNode[], edges: Edge[]) => void;
  clearDiagram: () => void;
  setSelectedNode: (node: RFNode | null) => void;
  updateNodeData: (nodeId: string, data: Record<string, unknown>) => void;
  removeEdge: (edgeId: string) => void;
  updateEdgeLabel: (edgeId: string, label?: string, data?: Record<string, unknown>) => void;
  setEditingEdgeId: (edgeId: string | null) => void;
}

export const useDiagramStore = create<DiagramState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  editingEdgeId: null,

  onNodesChange: (changes) => {
    set({
      nodes: applyNodeChanges(changes, get().nodes),
    });
  },

  onEdgesChange: (changes) => {
    set({
      edges: applyEdgeChanges(changes, get().edges),
    });
  },

  onConnect: (connection) => {
    set({
      edges: addEdge(
        {
          ...connection,
          type: 'animated',
          data: { animated: true },
        },
        get().edges
      ),
    });
  },

  addNode: (node) => {
    set({
      nodes: [...get().nodes, node],
    });
  },

  addNodesFromArchitecture: (nodes: RFNode[], connections: { from: string; to: string; label?: string }[]) => {
    const existingNodes = get().nodes;
    const nodeMap = new Map<string, RFNode>();

    existingNodes.forEach((node) => {
      nodeMap.set(node.id, node);
    });

    nodes.forEach((node) => {
      nodeMap.set(node.id, node);
    });

    const newNodes = Array.from(nodeMap.values());
    const nodeIdSet = new Set(newNodes.map((node) => node.id));

    const existingEdges = get().edges;
    const existingEdgeKeys = new Set(existingEdges.map((edge) => `${edge.source}__${edge.target}`));
    const baseEdgeIndex = existingEdges.length;

    const filteredConnections = connections.filter((conn) => {
      const hasEndpoints = nodeIdSet.has(conn.from) && nodeIdSet.has(conn.to);
      if (!hasEndpoints) {
        console.warn('[DiagramStore] Dropping connection with missing endpoint(s)', conn);
      }
      return hasEndpoints;
    });

    // Helper to compute absolute position of a node (accounts for parent groups with extent: 'parent')
    const computeAbsolutePosition = (nodeId: string, map: Map<string, RFNode>, cache = new Map<string, { x: number; y: number }>()): { x: number; y: number } | null => {
      if (cache.has(nodeId)) return cache.get(nodeId)!;
      const node = map.get(nodeId);
      if (!node || !node.position) return null;
      let abs = { x: node.position.x, y: node.position.y };
      // If the node has a parent that's using extent 'parent', add parent's absolute position
      const nodeMeta = node as unknown as Record<string, unknown>;
      const parentIdCandidate =
        typeof nodeMeta.parentId === 'string'
          ? (nodeMeta.parentId as string)
          : typeof nodeMeta.parentNode === 'string'
          ? (nodeMeta.parentNode as string)
          : undefined;
      if (parentIdCandidate && map.has(parentIdCandidate)) {
        const parentAbs = computeAbsolutePosition(parentIdCandidate, map, cache);
        if (parentAbs) {
          abs = { x: parentAbs.x + abs.x, y: parentAbs.y + abs.y };
        }
      }
      cache.set(nodeId, abs);
      return abs;
    };

    // Choose a handle name based on the relative direction between two points
    const chooseHandle = (fromPos: { x: number; y: number }, toPos: { x: number; y: number }, role: 'source' | 'target') => {
      const dx = toPos.x - fromPos.x;
      const dy = toPos.y - fromPos.y;
      // Prefer horizontal if horizontal distance is larger, otherwise vertical
      const horizontal = Math.abs(dx) > Math.abs(dy);
      if (horizontal) {
        return dx > 0 ? `right-${role}` : `left-${role}`;
      }
      return dy > 0 ? `bottom-${role}` : `top-${role}`;
    };

    const newEdges = filteredConnections
      .filter((conn) => !!conn.from && !!conn.to)
      .filter((conn) => {
        const key = `${conn.from}__${conn.to}`;
        if (existingEdgeKeys.has(key)) {
          return false;
        }
        existingEdgeKeys.add(key);
        return true;
      })
      .map((conn, index) => {
        const sourceNode = nodeMap.get(conn.from);
        const targetNode = nodeMap.get(conn.to);
        let sourceHandle: string | undefined;
        let targetHandle: string | undefined;

        try {
          const absCache = new Map<string, { x: number; y: number }>();
          const sourcePos = computeAbsolutePosition(conn.from, nodeMap, absCache) || sourceNode?.position;
          const targetPos = computeAbsolutePosition(conn.to, nodeMap, absCache) || targetNode?.position;
          if (sourcePos && targetPos) {
            sourceHandle = chooseHandle(sourcePos, targetPos, 'source');
            targetHandle = chooseHandle(sourcePos, targetPos, 'target');
          }
        } catch (err) {
          // fall back silently
        }

        const edge: Edge = {
          id: `ai-edge-${baseEdgeIndex + index}`,
          source: conn.from,
          target: conn.to,
          type: 'animated',
          label: conn.label,
          data: { animated: true },
          // Prefer setting handles when available so edges attach to logical sides
          ...(sourceHandle ? { sourceHandle } : {}),
          ...(targetHandle ? { targetHandle } : {}),
          markerEnd: {
            type: 'arrowclosed',
          },
          style: {
            stroke: '#1f2937',
            strokeWidth: 2,
          },
        };

        return edge;
      });

    console.log('[DiagramStore] Applying architecture update', {
      incomingNodes: nodes.length,
      mergedNodeCount: newNodes.length,
      incomingConnections: connections.length,
      appliedEdges: newEdges.length,
    });

    set({
      nodes: newNodes,
      edges: [...existingEdges, ...newEdges],
    });
  },

  replaceDiagram: (nodes: RFNode[], connections: { from: string; to: string; label?: string }[]) => {
    const nodeIdSet = new Set(nodes.map((node) => node.id));
    const sanitizedEdges = connections
      .filter((conn) => nodeIdSet.has(conn.from) && nodeIdSet.has(conn.to))
      .map((conn, index) => ({
        id: `ai-edge-${index}`,
        source: conn.from,
        target: conn.to,
        type: 'animated',
        label: conn.label,
        data: { animated: true },
      }));

    console.log('[DiagramStore] Replacing diagram state', {
      nodeCount: nodes.length,
      connectionCount: connections.length,
      appliedEdges: sanitizedEdges.length,
    });

    set({
      nodes,
      edges: sanitizedEdges,
      selectedNode: null,
    });
  },

  loadDiagram: (nodes: RFNode[], edges: Edge[]) => {
    console.log('[DiagramStore] Loading diagram from saved state', {
      nodeCount: nodes.length,
      edgeCount: edges.length,
    });

    set({
      nodes,
      edges,
      selectedNode: null,
    });
  },

  clearDiagram: () => {
    set({
      nodes: [],
      edges: [],
      selectedNode: null,
    });
  },

  setSelectedNode: (node) => {
    set({ selectedNode: node });
  },

  updateNodeData: (nodeId, data) => {
    const newNodes = get().nodes.map((node) =>
      node.id === nodeId ? { ...node, data: { ...node.data, ...data } } : node
    );
    // If the currently selected node is the one we updated, keep selectedNode in sync
    const currentSelected = get().selectedNode;
    const newSelected = currentSelected && currentSelected.id === nodeId
      ? newNodes.find((n) => n.id === nodeId) || currentSelected
      : currentSelected;
    set({
      nodes: newNodes,
      selectedNode: newSelected,
    });
  },
  // Remove an edge by id
  removeEdge: (edgeId: string) => {
    set({
      edges: get().edges.filter((e) => e.id !== edgeId),
    });
  },

  // Update an edge's label or data
  updateEdgeLabel: (edgeId: string, label?: string, data?: Record<string, unknown> | undefined) => {
    const newEdges = get().edges.map((edge) =>
      edge.id === edgeId ? { ...edge, label: label ?? edge.label, data: { ...(edge.data || {}), ...(data || {}) } } : edge
    );
    set({ edges: newEdges });
  },

  // Set which edge is being edited (for modal)
  setEditingEdgeId: (edgeId: string | null) => {
    set({ editingEdgeId: edgeId });
  },
}));
