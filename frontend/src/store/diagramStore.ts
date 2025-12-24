import { create } from 'zustand';
import { Node as RFNode, Edge, Connection, addEdge, applyNodeChanges, applyEdgeChanges, NodeChange, EdgeChange } from '@xyflow/react';
import { chooseHandle } from '@/lib/handleChooser';

type DiagramView = 'source' | 'azure';

interface DiagramSnapshot {
  nodes: RFNode[];
  edges: Edge[];
}

interface DiagramState {
  nodes: RFNode[];
  edges: Edge[];
  selectedNode: RFNode | null;
  currentView: DiagramView;
  views: Record<string, DiagramSnapshot>;
  isGenerating: boolean;
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
  updateEdgeConnection: (edgeId: string, connection: { source?: string; target?: string; sourceHandle?: string; targetHandle?: string }) => void;
  setViewSnapshot: (view: DiagramView, nodes: RFNode[], edges: Edge[]) => void;
  switchView: (view: DiagramView) => void;
  setIsGenerating: (isGenerating: boolean) => void;
}
const withUpdatedView = (viewKey: DiagramView, snapshot: DiagramSnapshot, views: Record<string, DiagramSnapshot>) => ({
  ...views,
  [viewKey]: snapshot,
});

export const useDiagramStore = create<DiagramState>((set, get) => ({
  nodes: [],
  edges: [],
  selectedNode: null,
  currentView: 'source',
  views: { source: { nodes: [], edges: [] } },
  isGenerating: false,

  onNodesChange: (changes) => {
    set((state) => {
      const nodes = applyNodeChanges(changes, state.nodes);
      return {
        nodes,
        views: withUpdatedView(state.currentView, { nodes, edges: state.edges }, state.views),
      };
    });
  },

  onEdgesChange: (changes) => {
    set((state) => {
      const edges = applyEdgeChanges(changes, state.edges);
      return {
        edges,
        views: withUpdatedView(state.currentView, { nodes: state.nodes, edges }, state.views),
      };
    });
  },

  onConnect: (connection) => {
    set((state) => {
      const edges = addEdge(
        {
          ...connection,
          type: 'animated',
          data: { animated: true },
        },
        state.edges
      );
      return {
        edges,
        views: withUpdatedView(state.currentView, { nodes: state.nodes, edges }, state.views),
      };
    });
  },

  addNode: (node) => {
    set((state) => {
      const nodes = [...state.nodes, node];
      return {
        nodes,
        views: withUpdatedView(state.currentView, { nodes, edges: state.edges }, state.views),
      };
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

    // Choose a handle name based on the relative direction between two points using angle bins
    const chooseHandle = (fromPos: { x: number; y: number }, toPos: { x: number; y: number }, role: 'source' | 'target') => {
      const dx = toPos.x - fromPos.x;
      const dy = toPos.y - fromPos.y;
      // Angle in radians (browser coordinates: y increases downward)
      const angle = Math.atan2(dy, dx);
      const PI = Math.PI;
      // Angle bins: right (-PI/4 .. PI/4), bottom (PI/4 .. 3PI/4), left (3PI/4 .. PI or -PI .. -3PI/4), top (-3PI/4 .. -PI/4)
      if (angle > -PI / 4 && angle <= PI / 4) {
        return `right-${role}`;
      }
      if (angle > PI / 4 && angle <= (3 * PI) / 4) {
        return `bottom-${role}`;
      }
      if (angle > (3 * PI) / 4 || angle <= -((3 * PI) / 4)) {
        return `left-${role}`;
      }
      return `top-${role}`;
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

    const mergedEdges = [...existingEdges, ...newEdges];

    set((state) => ({
      nodes: newNodes,
      edges: mergedEdges,
      views: withUpdatedView(state.currentView, { nodes: newNodes, edges: mergedEdges }, state.views),
    }));
  },

  replaceDiagram: (nodes: RFNode[], connections: { from: string; to: string; label?: string }[]) => {
    // Deduplicate incoming nodes by id (preserve last occurrence)
    const uniqueNodes = Array.from(new Map(nodes.map((node) => [node.id, node])).values());
    const nodeIdSet = new Set(uniqueNodes.map((node) => node.id));
    // Helper to compute absolute position of a node (accounts for parent groups with extent: 'parent')
    const nodeMap = new Map<string, RFNode>(uniqueNodes.map((n) => [n.id, n]));
    const computeAbsolutePosition = (nodeId: string, map: Map<string, RFNode>, cache = new Map<string, { x: number; y: number }>()): { x: number; y: number } | null => {
      if (cache.has(nodeId)) return cache.get(nodeId)!;
      const node = map.get(nodeId);
      if (!node || !node.position) return null;
      let abs = { x: node.position.x, y: node.position.y };
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

    const chooseHandle = (fromPos: { x: number; y: number }, toPos: { x: number; y: number }, role: 'source' | 'target') => {
      const dx = toPos.x - fromPos.x;
      const dy = toPos.y - fromPos.y;
      const angle = Math.atan2(dy, dx);
      const PI = Math.PI;
      if (angle > -PI / 4 && angle <= PI / 4) {
        return `right-${role}`;
      }
      if (angle > PI / 4 && angle <= (3 * PI) / 4) {
        return `bottom-${role}`;
      }
      if (angle > (3 * PI) / 4 || angle <= -((3 * PI) / 4)) {
        return `left-${role}`;
      }
      return `top-${role}`;
    };

    const sanitizedEdges = connections
      .filter((conn) => nodeIdSet.has(conn.from) && nodeIdSet.has(conn.to))
      .map((conn, index) => {
        const absCache = new Map<string, { x: number; y: number }>();
        const sourcePos = computeAbsolutePosition(conn.from, nodeMap, absCache) || nodeMap.get(conn.from)?.position;
        const targetPos = computeAbsolutePosition(conn.to, nodeMap, absCache) || nodeMap.get(conn.to)?.position;

        let sourceHandle: string | undefined;
        let targetHandle: string | undefined;
        try {
          if (sourcePos && targetPos) {
            sourceHandle = chooseHandle(sourcePos, targetPos, 'source');
            targetHandle = chooseHandle(sourcePos, targetPos, 'target');
          }
        } catch (err) {
          // ignore and leave handles undefined
        }

        return {
          id: `ai-edge-${index}`,
          source: conn.from,
          target: conn.to,
          type: 'animated',
          label: conn.label,
          data: { animated: true },
          ...(sourceHandle ? { sourceHandle } : {}),
          ...(targetHandle ? { targetHandle } : {}),
        } as Edge;
      });

    console.log('[DiagramStore] Replacing diagram state', {
      nodeCount: nodes.length,
      connectionCount: connections.length,
      appliedEdges: sanitizedEdges.length,
    });

    set((state) => ({
      nodes: uniqueNodes,
      edges: sanitizedEdges,
      selectedNode: null,
      views: withUpdatedView(state.currentView, { nodes: uniqueNodes, edges: sanitizedEdges }, state.views),
    }));
  },

  loadDiagram: (nodes: RFNode[], edges: Edge[]) => {
    console.log('[DiagramStore] Loading diagram from saved state', {
      nodeCount: nodes.length,
      edgeCount: edges.length,
    });

    // Deduplicate nodes by id to avoid duplicate React keys (MiniMap warnings)
    const uniqueNodes = Array.from(new Map(nodes.map((node) => [node.id, node])).values());
    const nodeIdSet = new Set(uniqueNodes.map((n) => n.id));
    // Filter edges to those that reference existing nodes
    const filteredEdges = Array.isArray(edges)
      ? edges.filter((e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target))
      : [];

    set({
      nodes: uniqueNodes,
      edges: filteredEdges,
      selectedNode: null,
      currentView: 'source',
      views: {
        source: { nodes: uniqueNodes, edges: filteredEdges },
      },
    });
  },

  clearDiagram: () => {
    set({
      nodes: [],
      edges: [],
      selectedNode: null,
      currentView: 'source',
      views: { source: { nodes: [], edges: [] } },
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
    set((state) => ({
      nodes: newNodes,
      selectedNode: newSelected,
      views: withUpdatedView(state.currentView, { nodes: newNodes, edges: state.edges }, state.views),
    }));
  },
  // Remove an edge by id
  removeEdge: (edgeId: string) => {
    set((state) => {
      const edges = state.edges.filter((e) => e.id !== edgeId);
      return {
        edges,
        views: withUpdatedView(state.currentView, { nodes: state.nodes, edges }, state.views),
      };
    });
  },

  // Update an edge's label or data
  updateEdgeLabel: (edgeId: string, label?: string, data?: Record<string, unknown> | undefined) => {
    set((state) => {
      const newEdges = state.edges.map((edge) =>
        edge.id === edgeId ? { ...edge, label: label ?? edge.label, data: { ...(edge.data || {}), ...(data || {}) } } : edge
      );
      return {
        edges: newEdges,
        views: withUpdatedView(state.currentView, { nodes: state.nodes, edges: newEdges }, state.views),
      };
    });
  },

  updateEdgeConnection: (edgeId, connection) => {
    set((state) => {
      const newEdges = state.edges.map((edge) => {
        if (edge.id !== edgeId) {
          return edge;
        }
        return {
          ...edge,
          source: connection.source ?? edge.source,
          target: connection.target ?? edge.target,
          sourceHandle: connection.sourceHandle ?? undefined,
          targetHandle: connection.targetHandle ?? undefined,
        };
      });
      return {
        edges: newEdges,
        views: withUpdatedView(state.currentView, { nodes: state.nodes, edges: newEdges }, state.views),
      };
    });
  },

  setViewSnapshot: (view, nodes, edges) => {
    set((state) => {
      const updatedViews = withUpdatedView(view, { nodes, edges }, state.views);
      if (view === state.currentView) {
        return {
          nodes,
          edges,
          selectedNode: null,
          views: updatedViews,
        };
      }
      return { views: updatedViews };
    });
  },

  switchView: (view) => {
    set((state) => {
      const snapshot = state.views[view];
      if (!snapshot) {
        console.warn('[DiagramStore] Requested view missing snapshot', view);
        return {};
      }
      return {
        currentView: view,
        nodes: snapshot.nodes,
        edges: snapshot.edges,
        selectedNode: null,
      };
    });
  },

  setIsGenerating: (isGenerating) => {
    set({ isGenerating });
  },
}));
