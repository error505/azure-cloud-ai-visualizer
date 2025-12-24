import { memo, useEffect, useRef } from 'react';
import { EdgeProps, getBezierPath } from '@xyflow/react';
import { gsap } from 'gsap';

const ParticleEdge = ({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
}: EdgeProps) => {
  const particleRef = useRef<SVGCircleElement>(null);
  const pathRef = useRef<SVGPathElement>(null);

  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

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
          <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.2" />
          <stop offset="50%" stopColor="hsl(var(--primary))" stopOpacity="0.8" />
          <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0.2" />
        </linearGradient>
      </defs>
      
      <path
        ref={pathRef}
        id={id}
        style={style}
        className="fill-none stroke-2"
        stroke={`url(#gradient-${id})`}
        d={edgePath}
        markerEnd="url(#arrow)"
      />
      
      <circle
        ref={particleRef}
        r="4"
        className="fill-primary drop-shadow-lg"
      >
        <animate
          attributeName="r"
          values="3;5;3"
          dur="1s"
          repeatCount="indefinite"
        />
      </circle>
    </>
  );
};

export default memo(ParticleEdge);
