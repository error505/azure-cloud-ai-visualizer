import { memo } from 'react';
import { EdgeProps, getSmoothStepPath, EdgeLabelRenderer } from '@xyflow/react';
import { Lock } from 'lucide-react';

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
}: EdgeProps) => {
  const edgeData = data as AnimatedEdgeData;
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

  return (
    <>
      <path
        id={id}
        style={style}
        className={`
          fill-none stroke-2 transition-all duration-300
          ${isAnimated && !isSecure ? 'animate-dash' : ''}
          ${isSecure ? 'stroke-accent' : 'stroke-primary'}
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
    </>
  );
};

export default memo(AnimatedEdge);
