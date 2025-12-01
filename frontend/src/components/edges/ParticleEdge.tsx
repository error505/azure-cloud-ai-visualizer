import { memo, useEffect, useRef, useState, MouseEvent } from 'react';
import { EdgeProps, getBezierPath, EdgeLabelRenderer } from '@xyflow/react';
import { gsap } from 'gsap';
import { Trash2, Edit3 } from 'lucide-react';
import { useDiagramStore } from '@/store/diagramStore';

const ParticleEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  selected,
  data,
}: EdgeProps) => {
  const particleRef = useRef<SVGCircleElement>(null);
  const pathRef = useRef<SVGPathElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const removeEdge = useDiagramStore((s) => s.removeEdge);
  const setEditingEdgeId = useDiagramStore((s) => s.setEditingEdgeId);

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const connectionLabel = (data as any)?.label;
  const showButtons = selected || isHovered;

  const handleEditLabel = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    setEditingEdgeId(id);
  };

  useEffect(() => {
    if (particleRef.current && pathRef.current) {
      const path = pathRef.current;
      const pathLength = path.getTotalLength();
      
      gsap.to(particleRef.current, {
        motionPath: {
          path: path,
          align: path,
          autoRotate: false,
        },
        duration: 3,
        ease: 'none',
        repeat: -1,
      });
    }
  }, [edgePath]);

  return (
    <>
      <defs>
        <linearGradient id={`gradient-${id}`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor={selected ? "#3b82f6" : "hsl(var(--primary))"} stopOpacity="0.2" />
          <stop offset="50%" stopColor={selected ? "#3b82f6" : "hsl(var(--primary))"} stopOpacity="0.8" />
          <stop offset="100%" stopColor={selected ? "#3b82f6" : "hsl(var(--primary))"} stopOpacity="0.2" />
        </linearGradient>
      </defs>
      
      {/* Invisible wider path for easier clicking */}
      <path
        d={edgePath}
        fill="none"
        strokeWidth={20}
        stroke="transparent"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{ cursor: 'pointer', pointerEvents: 'stroke' }}
      />
      
      <path
        ref={pathRef}
        id={id}
        className={`fill-none transition-all ${selected || isHovered ? 'stroke-[3px]' : 'stroke-2'}`}
        stroke={`url(#gradient-${id})`}
        d={edgePath}
        markerEnd="url(#arrow)"
      />
      
      <circle
        ref={particleRef}
        r="4"
        className={`drop-shadow-lg ${selected ? 'fill-blue-500' : 'fill-primary'}`}
      >
        <animate
          attributeName="r"
          values="3;5;3"
          dur="1s"
          repeatCount="indefinite"
        />
      </circle>

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

export default memo(ParticleEdge);
