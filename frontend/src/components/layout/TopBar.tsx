import { useState, useEffect } from 'react';
import { Icon } from '@iconify/react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import ThemeToggle from '@/components/ui/theme-toggle';
import { useSupabase } from '@/context/SupabaseContext';

interface TopBarProps {
  titleOverride?: string;
  projectId?: string;
  onRename?: (newTitle: string) => void;
  onDelete?: () => void;
}

const TopBar = ({
  titleOverride,
  projectId,
  onRename,
  onDelete,
}: TopBarProps) => {
  const [editingTitle, setEditingTitle] = useState(false);
  const [localTitle, setLocalTitle] = useState<string>(titleOverride ?? 'Azure Architect');
  const { user, signOut, signInWithProvider, isReady, supabaseAvailable } = useSupabase();
  
  useEffect(() => {
    setLocalTitle(titleOverride ?? 'Azure Architect');
  }, [titleOverride]);

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
        
        {projectId && onDelete && (
          <Button
            variant="ghost"
            size="sm"
            className="gap-2 text-red-400"
            onClick={() => {
              const ok = window.confirm('Delete project and all associated data? This cannot be undone.');
              if (ok) onDelete();
            }}
            title="Delete project"
          >
            <Icon icon="mdi:delete" />
            <span className="hidden md:inline">Delete</span>
          </Button>
        )}
      </div>

      <div className="flex items-center gap-2">
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
          <Badge variant="secondary" className="bg-white/10 text-white/70">
            Supabase disabled
          </Badge>
        )}
      </div>
    </header>
  );
};

export default TopBar;
