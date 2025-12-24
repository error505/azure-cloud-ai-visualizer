import { useEffect } from 'react';
import { toast } from 'sonner';

export const useKeyboardShortcuts = (callbacks: {
  onSave?: () => void;
  onDelete?: () => void;
  onDuplicate?: () => void;
  onUndo?: () => void;
  onRedo?: () => void;
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const isMod = e.ctrlKey || e.metaKey;

      // Save: Ctrl/Cmd + S
      if (isMod && e.key === 's') {
        e.preventDefault();
        if (callbacks.onSave) {
          callbacks.onSave();
        } else {
          toast.success('Diagram saved!');
        }
      }

      // Undo: Ctrl/Cmd + Z
      if (isMod && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        callbacks.onUndo?.();
      }

      // Redo: Ctrl/Cmd + Shift + Z or Ctrl/Cmd + Y
      if (isMod && ((e.key === 'z' && e.shiftKey) || e.key === 'y')) {
        e.preventDefault();
        callbacks.onRedo?.();
      }

      // Duplicate: Ctrl/Cmd + D
      if (isMod && e.key === 'd') {
        e.preventDefault();
        callbacks.onDuplicate?.();
      }

      // Delete: Delete or Backspace
      if (e.key === 'Delete' || e.key === 'Backspace') {
        const target = e.target as HTMLElement;
        // Don't trigger if user is typing in an input
        if (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA') {
          callbacks.onDelete?.();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [callbacks]);
};
