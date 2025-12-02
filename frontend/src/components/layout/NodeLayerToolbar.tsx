import { memo } from 'react';
import { NodeToolbar, Position } from '@xyflow/react';
import { ArrowUp, ArrowDown, ChevronsUp, ChevronsDown } from 'lucide-react';
import { useDiagramStore } from '@/store/diagramStore';

interface NodeLayerToolbarProps {
  nodeId: string;
  isVisible: boolean;
}

const NodeLayerToolbar = ({ nodeId, isVisible }: NodeLayerToolbarProps) => {
  const bringNodeToFront = useDiagramStore((s) => s.bringNodeToFront);
  const sendNodeToBack = useDiagramStore((s) => s.sendNodeToBack);
  const bringNodeForward = useDiagramStore((s) => s.bringNodeForward);
  const sendNodeBackward = useDiagramStore((s) => s.sendNodeBackward);

  return (
    <NodeToolbar
      isVisible={isVisible}
      position={Position.Top}
      offset={10}
      className="flex gap-1 bg-black/60 backdrop-blur-sm rounded-lg p-1 shadow-xl border border-white/20"
    >
      <button
        onClick={() => bringNodeToFront(nodeId)}
        className="p-2 rounded bg-blue-500 hover:bg-blue-600 text-white transition-colors active:scale-95"
        title="Bring to Front (Ctrl+Shift+])"
      >
        <ChevronsUp className="w-4 h-4" />
      </button>
      <button
        onClick={() => bringNodeForward(nodeId)}
        className="p-2 rounded bg-blue-500/80 hover:bg-blue-600 text-white transition-colors active:scale-95"
        title="Bring Forward (Ctrl+])"
      >
        <ArrowUp className="w-4 h-4" />
      </button>
      <button
        onClick={() => sendNodeBackward(nodeId)}
        className="p-2 rounded bg-gray-500/80 hover:bg-gray-600 text-white transition-colors active:scale-95"
        title="Send Backward (Ctrl+[)"
      >
        <ArrowDown className="w-4 h-4" />
      </button>
      <button
        onClick={() => sendNodeToBack(nodeId)}
        className="p-2 rounded bg-gray-500 hover:bg-gray-600 text-white transition-colors active:scale-95"
        title="Send to Back (Ctrl+Shift+[)"
      >
        <ChevronsDown className="w-4 h-4" />
      </button>
    </NodeToolbar>
  );
};

export default memo(NodeLayerToolbar);
