import { useState, useRef, useEffect } from 'react';
import { Icon } from '@iconify/react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ExportModal } from '@/components/modals/ExportModal';
import ThemeToggle from '@/components/ui/theme-toggle';
import { useSupabase } from '@/context/SupabaseContext';

interface TopBarProps {
  titleOverride?: string;
  onChatToggle?: () => void;
  isChatOpen?: boolean;
  onAssetsToggle?: () => void;
  isAssetsOpen?: boolean;
  onIacToggle?: () => void;
  isIacOpen?: boolean;
  onSave?: () => void;
  projectId?: string;
  onRename?: (newTitle: string) => void;
  onDelete?: () => void;
}

const TopBar = ({
  titleOverride,
  onChatToggle,
  isChatOpen,
  onAssetsToggle,
  isAssetsOpen,
  onIacToggle,
  isIacOpen,
  onSave,
  projectId,
  onRename,
  onDelete,
}: TopBarProps) => {
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const canvasRef = useRef<HTMLElement | null>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [localTitle, setLocalTitle] = useState<string>(titleOverride ?? 'Azure Architect');
  const { user, signOut, signInWithProvider, isReady, supabaseAvailable } = useSupabase();
  
  useEffect(() => {
    setLocalTitle(titleOverride ?? 'Azure Architect');
  }, [titleOverride]);

  // Get canvas element reference
  const getCanvasElement = () => {
    if (!canvasRef.current) {
      canvasRef.current = document.querySelector('.react-flow');
    }
    return canvasRef.current;
  };

  return (
    <header className="glass-panel border-b border-border/50 px-4 h-14 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <img src="/logo.png" alt="Azure Architect" className="h-8 w-8 object-contain" />
          <div>
            {editingTitle ? (
              <input
                autoFocus
                value={localTitle}
                onChange={(e) => setLocalTitle(e.target.value)}
                onBlur={async () => {
                  setEditingTitle(false);
                  if (onRename && localTitle.trim()) {
                    await onRename(localTitle.trim());
                  }
                }}
                onKeyDown={async (e) => {
                  if (e.key === 'Enter') {
                    setEditingTitle(false);
                    if (onRename && localTitle.trim()) {
                      await onRename(localTitle.trim());
                    }
                  } else if (e.key === 'Escape') {
                    setLocalTitle(titleOverride ?? 'Azure Architect');
                    setEditingTitle(false);
                  }
                }}
                className="text-lg font-bold bg-transparent border-b border-white/20 px-1 py-0 w-64"
              />
            ) : (
              <h1 className="text-lg font-bold">
                <button
                  type="button"
                  onClick={() => {
                    if (projectId && onRename) {
                      setEditingTitle(true);
                    }
                  }}
                  className="text-left"
                >
                  {titleOverride ?? 'Azure Architect'}
                </button>
              </h1>
            )}
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" className="gap-2">
            <Icon icon="mdi:folder-open" />
            <span className="hidden md:inline">Open</span>
          </Button>
          <Button 
            variant="ghost" 
            size="sm" 
            className="gap-2"
            onClick={onSave}
            disabled={!projectId || !onSave}
            title={projectId ? "Save diagram" : "Sign in to save projects"}
          >
            <Icon icon="mdi:content-save" />
            <span className="hidden md:inline">Save</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="gap-2 text-red-400"
            onClick={() => {
              if (!projectId) return;
              if (!onDelete) return;
              const ok = window.confirm('Delete project and all associated data? This cannot be undone.');
              if (ok) onDelete();
            }}
            disabled={!projectId || !onDelete}
            title={projectId ? 'Delete project' : 'Sign in to manage projects'}
          >
            <Icon icon="mdi:delete" />
            <span className="hidden md:inline">Delete</span>
          </Button>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button 
          variant={isIacOpen ? "default" : "outline"} 
          size="sm" 
          className="gap-2"
          onClick={onIacToggle}
        >
          <Icon icon="mdi:code-json" />
          {isIacOpen ? 'IaC Panel' : 'Generate IaC'}
        </Button>
        <Button variant="default" size="sm" className="gap-2 bg-accent hover:bg-accent/90">
          <Icon icon="mdi:cloud-upload" />
          Deploy
        </Button>
        <Button 
          variant="ghost" 
          size="sm" 
          className="gap-2"
          onClick={() => setExportModalOpen(true)}
        >
          <Icon icon="mdi:download" />
          Export
        </Button>
        <Button 
          variant={isAssetsOpen ? "default" : "ghost"} 
          size="icon"
          onClick={onAssetsToggle}
          title="Asset Manager"
        >
          <Icon icon="mdi:folder-multiple-image" className="text-xl" />
        </Button>
        <Button 
          variant={isChatOpen ? "default" : "ghost"} 
          size="icon"
          onClick={onChatToggle}
          title="AI Assistant"
        >
          <Icon icon="mdi:robot" className="text-xl" />
        </Button>
        <ThemeToggle />
        {isReady && user ? (
          <Button variant="ghost" size="sm" className="gap-2" onClick={() => signOut()}>
            <Icon icon="mdi:account" className="text-xl" />
            <span className="hidden md:inline">{user.email?.split('@')[0] ?? 'Account'}</span>
          </Button>
        ) : supabaseAvailable ? (
          <Button
            variant="ghost"
            size="sm"
            className="gap-2"
            onClick={() => signInWithProvider('github')}
          >
            <Icon icon="mdi:github" className="text-xl" />
            <span className="hidden md:inline">Sign in</span>
          </Button>
        ) : (
          <Badge variant="secondary" className="bg-muted text-muted-foreground border border-border">
            Supabase disabled
          </Badge>
        )}
      </div>

      <ExportModal 
        open={exportModalOpen}
        onOpenChange={setExportModalOpen}
        canvasElement={getCanvasElement()}
      />
    </header>
  );
};

export default TopBar;
