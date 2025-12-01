import { memo, useState, MouseEvent } from 'react';
import { EdgeProps, getSmoothStepPath, EdgeLabelRenderer } from '@xyflow/react';
import { Lock, Trash2, Edit3 } from 'lucide-react';
import { useDiagramStore } from '@/store/diagramStore';

interface AnimatedEdgeData {
  animated?: boolean;
  secure?: boolean;
  label?: string;
}

const AnimatedEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  data,
  label,
  selected,
}: EdgeProps) => {
  const edgeData = data as AnimatedEdgeData;
  const [isHovered, setIsHovered] = useState(false);
  const removeEdge = useDiagramStore((s) => s.removeEdge);
  const setEditingEdgeId = useDiagramStore((s) => s.setEditingEdgeId);
  
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 8,
  });

  const connectionLabel = edgeData?.label || label;
  const isSecure = edgeData?.secure;
  const isAnimated = edgeData?.animated !== false;
  const showButtons = selected || isHovered;

  const handleEditLabel = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    setEditingEdgeId(id);
  };

  return (
    <>
      {/* Invisible wider path for easier clicking/hovering */}
      <path
        d={edgePath}
        fill="none"
        strokeWidth={20}
        stroke="transparent"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
      />
      
      {/* Main visible path */}
      <path
        id={id}
        className={`
          fill-none transition-all duration-300
          ${isAnimated && !isSecure ? 'animate-dash' : ''}
          ${selected || isHovered ? 'stroke-[3px]' : 'stroke-2'}
          ${selected ? 'stroke-blue-500 drop-shadow-lg' : isSecure ? 'stroke-accent' : 'stroke-primary'}
          ${isHovered && !selected ? 'stroke-primary/80' : ''}
        `}
        strokeDasharray={isSecure ? "5,5" : isAnimated ? "8,4" : "none"}
        d={edgePath}
        markerEnd="url(#arrow)"
      />
      
      {isSecure && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="bg-accent/20 backdrop-blur-sm border border-accent/40 rounded-full p-1.5"
          >
            <Lock className="w-3 h-3 text-accent" />
          </div>
        </EdgeLabelRenderer>
      )}

      {connectionLabel && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY - 20}px)`,
              pointerEvents: 'all',
            }}
            className="glass-panel text-xs px-2 py-1 rounded-md whitespace-nowrap shadow-md border border-border/30"
          >
            {connectionLabel}
          </div>
        </EdgeLabelRenderer>
      )}

      {/* Action buttons on hover or selection */}
      {showButtons && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
              zIndex: 1000,
            }}
            className="flex gap-1.5 items-center bg-black/40 backdrop-blur-sm rounded-lg p-1 shadow-xl border border-white/20"
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
          >
            <button
              onClick={(e) => {
                e.stopPropagation();
                removeEdge(id);
              }}
              className="bg-red-500 hover:bg-red-600 text-white p-1.5 rounded shadow-lg transition-colors active:scale-95"
              title="Delete connection (Del)"
              type="button"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={handleEditLabel}
              className="bg-blue-500 hover:bg-blue-600 text-white p-1.5 rounded shadow-lg transition-colors active:scale-95"
              title={connectionLabel ? "Edit label" : "Add label"}
              type="button"
            >
              <Edit3 className="w-3.5 h-3.5" />
            </button>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
};

export default memo(AnimatedEdge);
