import { useCallback, useRef, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  ReactFlowProvider,
  MarkerType,
  Node as RFNode,
  Edge as RFEdge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { useDiagramStore } from '@/store/diagramStore';
import AzureServiceNode from '@/components/nodes/AzureServiceNode';
import AzureGroupNode from '@/components/nodes/AzureGroupNode';
import AnimatedEdge from '@/components/edges/AnimatedEdge';
import ParticleEdge from '@/components/edges/ParticleEdge';
import EdgeLabelModal from '@/components/layout/EdgeLabelModal';
import { Button } from '@/components/ui/button';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { toast } from 'sonner';

const nodeTypes = {
  'azure.service': AzureServiceNode,
  'azure.group': AzureGroupNode,
};

const edgeTypes = {
  animated: AnimatedEdge,
  particle: ParticleEdge,
};

const DiagramCanvas = () => {
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const {
    nodes,
    edges,
    onNodesChange,
    onEdgesChange,
    onConnect,
    addNode,
    setSelectedNode,
    editingEdgeId,
    setEditingEdgeId,
  } = useDiagramStore();
  const removeEdge = useDiagramStore((s) => s.removeEdge);
  const updateEdgeLabel = useDiagramStore((s) => s.updateEdgeLabel);
  const bringNodeToFront = useDiagramStore((s) => s.bringNodeToFront);
  const sendNodeToBack = useDiagramStore((s) => s.sendNodeToBack);
  const bringNodeForward = useDiagramStore((s) => s.bringNodeForward);
  const sendNodeBackward = useDiagramStore((s) => s.sendNodeBackward);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect();
      const data = event.dataTransfer.getData('application/reactflow');

      if (data && reactFlowBounds) {
        const nodeData = JSON.parse(data);
        const position = {
          x: event.clientX - reactFlowBounds.left - 90,
          y: event.clientY - reactFlowBounds.top - 40,
        };

        const nodeId = `node-${Date.now()}`;
        const nodeType = nodeData.type ?? 'azure.service';

        const newNode: RFNode = {
          id: nodeId,
          type: nodeType,
          position,
          data: nodeData.data ?? {},
          ...(nodeData.style ? { style: nodeData.style } : {}),
        };

        if (nodeType === 'azure.group') {
          newNode.style = {
            width: nodeData.style?.width ?? 420,
            height: nodeData.style?.height ?? 280,
            ...(nodeData.style || {}),
          };
          newNode.data = {
            label: nodeData.data?.label ?? 'Resource Group',
            groupType: nodeData.data?.groupType ?? 'default',
            metadata: nodeData.data?.metadata,
            status: 'group',
          };
          newNode.draggable = true;
          newNode.selectable = true;
        }

        addNode(newNode);
      }
    },
    [addNode]
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: RFNode) => {
      setSelectedNode(node);
    },
    [setSelectedNode]
  );

  const onEdgeDoubleClick = useCallback((_: React.MouseEvent, edge: RFEdge) => {
    // Open modal to edit label
    setEditingEdgeId(edge.id);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, [setSelectedNode]);

  const onSelectionChange = useCallback(() => {
    // Handle selection changes if needed
  }, []);

  // Keyboard shortcuts
  useKeyboardShortcuts({
    onSave: () => {
      toast.success('Diagram saved!');
    },
    onDelete: () => {
      const selectedNodes = nodes.filter((n) => n.selected);
      const selectedEdges = edges.filter((e) => e.selected);
      
      if (selectedNodes.length > 0 || selectedEdges.length > 0) {
        toast.info(`Deleted ${selectedNodes.length} node(s) and ${selectedEdges.length} edge(s)`);
      }
    },
    onBringToFront: () => {
      const selectedNodes = nodes.filter((n) => n.selected);
      if (selectedNodes.length === 1) {
        bringNodeToFront(selectedNodes[0].id);
        toast.success('Brought to front');
      }
    },
    onSendToBack: () => {
      const selectedNodes = nodes.filter((n) => n.selected);
      if (selectedNodes.length === 1) {
        sendNodeToBack(selectedNodes[0].id);
        toast.success('Sent to back');
      }
    },
    onBringForward: () => {
      const selectedNodes = nodes.filter((n) => n.selected);
      if (selectedNodes.length === 1) {
        bringNodeForward(selectedNodes[0].id);
        toast.success('Brought forward');
      }
    },
    onSendBackward: () => {
      const selectedNodes = nodes.filter((n) => n.selected);
      if (selectedNodes.length === 1) {
        sendNodeBackward(selectedNodes[0].id);
        toast.success('Sent backward');
      }
    },
  });

  return (
    <div ref={reactFlowWrapper} className="flex-1 relative bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onNodeClick={onNodeClick}
        onEdgeDoubleClick={onEdgeDoubleClick}
        onSelectionChange={onSelectionChange}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        snapToGrid
        snapGrid={[15, 15]}
        deleteKeyCode={['Delete', 'Backspace']}
        defaultEdgeOptions={{
          type: 'animated',
          style: { strokeWidth: 2 },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 20,
            height: 20,
            color: 'hsl(var(--primary))',
          },
        }}
        edgesReconnectable={true}
        elevateEdgesOnSelect={true}
      >
        <Background 
          variant={BackgroundVariant.Dots} 
          gap={20} 
          size={1.5} 
          color="hsl(var(--muted-foreground) / 0.15)" 
        />
        <Controls className="glass-panel !border-border/50" />
        <MiniMap
          className="glass-panel !border-border/50"
          nodeColor={(node) => {
            if (node.type === 'azure.group') return 'hsl(var(--primary) / 0.35)';
            if (node.data.status === 'active') return 'hsl(var(--primary))';
            return 'hsl(var(--muted))';
          }}
        />
        {/* Dimmed background watermark */}
        <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
          {/* Try to load public/logo.png; if missing the img will 404 silently in dev. */}
          <img
            src="/logo.png"
            alt="logo"
            className="max-w-[40%] opacity-10 dark:opacity-6 select-none"
            style={{ filter: 'grayscale(1) blur(0.5px)', width: '40%', height: 'auto' }}
          />
        </div>
        {/* Edge label editor modal */}
        {editingEdgeId !== null && (
          <div className="absolute top-6 right-6 z-50">
            {/* floating modal is implemented with EdgeLabelModal component */}
          </div>
        )}
      </ReactFlow>
      {/* Edge edit/delete floating controls */}
      {editingEdgeId && (
        <div className="absolute top-4 right-4 z-50 flex gap-2">
          <button
            onClick={() => {
              // Show the EdgeLabelModal by keeping editingEdgeId
              // The modal component is rendered below which reads editingEdgeId
              setEditingEdgeId(editingEdgeId);
            }}
            className="btn glass-panel px-3 py-2 rounded-md border"
            title="Edit edge label"
          >
            Edit
          </button>
          <button
            onClick={() => {
              removeEdge(editingEdgeId);
              setEditingEdgeId(null);
            }}
            className="btn glass-panel px-3 py-2 rounded-md border text-destructive"
            title="Delete edge"
          >
            Delete
          </button>
        </div>
      )}
      {/* EdgeLabelModal rendered outside ReactFlow so Dialog portal works */}
      <EdgeLabelModal
        edgeId={editingEdgeId}
        open={!!editingEdgeId}
        onClose={() => setEditingEdgeId(null)}
      />
    </div>
  );
};

const DiagramCanvasWrapper = () => (
  <ReactFlowProvider>
    <DiagramCanvas />
  </ReactFlowProvider>
);

export default DiagramCanvasWrapper;
