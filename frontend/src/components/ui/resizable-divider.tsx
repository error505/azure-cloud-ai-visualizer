import { useCallback, useEffect, useRef, useState, MouseEvent as ReactMouseEvent } from 'react';

interface ResizableDividerProps {
  onResize: (height: number) => void;
  onMinimize?: () => void;
  onMaximize?: () => void;
  minHeight?: number;
  maxHeight?: number;
  defaultHeight?: number;
  className?: string;
}

export const ResizableDivider = ({ 
  onResize, 
  onMinimize,
  onMaximize,
  minHeight = 48, 
  maxHeight = 600,
  defaultHeight = 192,
  className = ''
}: ResizableDividerProps) => {
  const [isDragging, setIsDragging] = useState(false);
  const dragStartYRef = useRef<number>(0);
  const dragStartHeightRef = useRef<number>(0);

  const handleMouseDown = useCallback((e: ReactMouseEvent | MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    dragStartYRef.current = e.clientY;
    // We'll pass the current height from parent via callback
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging) return;
    
    const deltaY = dragStartYRef.current - e.clientY;
    const newHeight = Math.max(
      minHeight,
      Math.min(maxHeight, dragStartHeightRef.current + deltaY)
    );
    
    onResize(newHeight);
  }, [isDragging, minHeight, maxHeight, onResize]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // Update the start height when dragging begins
  useEffect(() => {
    if (isDragging) {
      const computeCurrentHeight = () => {
        const element = document.querySelector('[data-resizable-footer]');
        if (element) {
          dragStartHeightRef.current = element.getBoundingClientRect().height;
        }
      };
      computeCurrentHeight();
    }
  }, [isDragging]);

  return (
    <div className="relative group">
      <div
        onMouseDown={handleMouseDown}
        className={`
          h-1 cursor-ns-resize 
          bg-border/30 
          hover:bg-primary/50 
          transition-colors
          relative
          ${isDragging ? 'bg-primary' : ''}
          ${className}
        `}
        role="separator"
        aria-orientation="horizontal"
        aria-label="Resize footer panel"
      >
        <div className="absolute inset-0 -top-1 -bottom-1 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
          <div className="w-12 h-1 rounded-full bg-primary/70" />
        </div>
      </div>
      
      {/* Quick action buttons */}
      <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
        <div className="pointer-events-auto flex gap-1">
          {onMinimize && (
            <button
              onClick={onMinimize}
              className="p-2 rounded-md bg-background/95 border border-border/50 hover:bg-primary/20 hover:border-primary transition-all shadow-lg backdrop-blur-sm"
              title="Collapse to tabs only (48px)"
              aria-label="Minimize footer"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          )}
          {onMaximize && (
            <button
              onClick={onMaximize}
              className="p-2 rounded-md bg-background/95 border border-border/50 hover:bg-primary/20 hover:border-primary transition-all shadow-lg backdrop-blur-sm"
              title="Expand footer (400px)"
              aria-label="Maximize footer"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 15l7-7 7 7" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
