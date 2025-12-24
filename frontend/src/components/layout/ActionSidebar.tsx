import { useState, useRef } from 'react';
import { Icon } from '@iconify/react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ExportModal } from '@/components/modals/ExportModal';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ActionSidebarProps {
  onSave?: () => void;
  projectId?: string;
  onDocumentationToggle?: () => void;
  onComplianceToggle?: () => void;
  onDualPassToggle?: () => void;
  onIacToggle?: () => void;
  isIacOpen?: boolean;
  onIntegrationsToggle?: () => void;
  activeIntegrationCount?: number;
  onDeployToggle?: () => void;
  onExportToggle?: () => void;
  onAssetsToggle?: () => void;
  isAssetsOpen?: boolean;
  onPaletteToggle?: () => void;
  isPaletteOpen?: boolean;
  onChatToggle?: () => void;
  isChatOpen?: boolean;
  hasNodes?: boolean;
  onInspectorToggle?: () => void;
  isInspectorOpen?: boolean;
  onShareLink?: () => void | Promise<void>;
  isShareGenerating?: boolean;
  // Multi-cloud migration props
  onMigrationToggle?: () => void;
  onCostToggle?: () => void;
}

export const ActionSidebar = ({
  onSave,
  projectId,
  onDocumentationToggle,
  onComplianceToggle,
  onDualPassToggle,
  onIacToggle,
  isIacOpen,
  onIntegrationsToggle,
  activeIntegrationCount,
  onDeployToggle,
  onExportToggle,
  onAssetsToggle,
  isAssetsOpen,
  onPaletteToggle,
  isPaletteOpen,
  onChatToggle,
  isChatOpen,
  hasNodes,
  onInspectorToggle,
  isInspectorOpen,
  onShareLink,
  isShareGenerating,
  onMigrationToggle,
  onCostToggle,
}: ActionSidebarProps) => {
  const [exportModalOpen, setExportModalOpen] = useState(false);
  const canvasRef = useRef<HTMLElement | null>(null);

  const getCanvasElement = () => {
    if (!canvasRef.current) {
      canvasRef.current = document.querySelector('.react-flow');
    }
    return canvasRef.current;
  };

  return (
    <TooltipProvider delayDuration={300}>
      <aside className="glass-panel border-r border-border/50 w-20 flex flex-col items-center py-4 gap-3 overflow-y-auto max-h-screen pb-24 sticky top-0 ">
      {/* Quick Actions */}
      <ScrollArea className="flex-1 p-2 space-y-2 min-h-0">
      <div className="flex flex-col gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="ghost"
                size="icon"
                className="w-12 h-12"
                onClick={onSave}
                disabled={!projectId || !onSave}
              >
                <Icon icon="mdi:content-save" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{projectId ? 'Save Diagram' : 'Sign in to save'}</p>
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="ghost"
                size="icon"
                className="w-12 h-12"
                onClick={onShareLink}
                disabled={!projectId || !onShareLink}
              >
                {isShareGenerating ? (
                  <Icon icon="mdi:loading" className="text-xl animate-spin" />
                ) : (
                  <Icon icon="mdi:link-variant" className="text-xl" />
                )}
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{projectId ? 'Share live collaboration link' : 'Save a project to share'}</p>
          </TooltipContent>
        </Tooltip>
      </div>

      <div className="h-px w-8 bg-border/50 my-1" />

      {/* Enterprise Features */}
      <div className="flex flex-col gap-2">


        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="outline"
                size="icon"
                className="w-12 h-12"
                onClick={onDocumentationToggle}
                disabled={!onDocumentationToggle || !hasNodes}
              >
                <Icon icon="mdi:file-document" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{!hasNodes ? 'Create a diagram first' : 'Generate Documentation'}</p>
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="outline"
                size="icon"
                className="w-12 h-12"
                onClick={onComplianceToggle}
                disabled={!onComplianceToggle || !hasNodes}
              >
                <Icon icon="mdi:shield-check" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{!hasNodes ? 'Create a diagram first' : 'Check Compliance'}</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="outline"
                size="icon"
                className="w-12 h-12"
                onClick={onDualPassToggle}
                disabled={!onDualPassToggle || !hasNodes}
              >
                <Icon icon="mdi:shield-search" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{!hasNodes ? 'Create a diagram first' : 'AI Dual-Pass Validation'}</p>
          </TooltipContent>
        </Tooltip>
      </div>

      <div className="h-px w-8 bg-border/50 my-1" />

      {/* Multi-Cloud Migration */}
      <div className="flex flex-col gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="outline"
                size="icon"
                className="w-12 h-12 border-blue-500/50 hover:bg-blue-500/10"
                onClick={onMigrationToggle}
                disabled={!hasNodes}
              >
                <Icon icon="mdi:cloud-sync" className="text-xl text-blue-400" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{!hasNodes ? 'Import inventory first' : 'Migration Planning'}</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="outline"
                size="icon"
                className="w-12 h-12 border-green-500/50 hover:bg-green-500/10"
                onClick={onCostToggle}
                disabled={!hasNodes}
              >
                <Icon icon="mdi:currency-usd" className="text-xl text-green-400" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{!hasNodes ? 'Create a diagram first' : 'Cost Optimization'}</p>
          </TooltipContent>
        </Tooltip>
      </div>

      <div className="h-px w-8 bg-border/50 my-1" />

      {/* Core Actions */}
      <div className="flex flex-col gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant={isIacOpen ? 'default' : 'outline'}
                size="icon"
                className="w-12 h-12"
                onClick={onIacToggle}
              >
                <Icon icon="mdi:code-json" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>Generate IaC</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="outline"
                size="icon"
                className="w-12 h-12 relative"
                onClick={onIntegrationsToggle}
                disabled={!onIntegrationsToggle}
              >
                <Icon icon="mdi:puzzle" className="text-xl" />
                {typeof activeIntegrationCount === 'number' && activeIntegrationCount > 0 && (
                  <Badge
                    variant="secondary"
                    className="absolute -top-1 -right-1 h-5 w-5 flex items-center justify-center p-0 bg-primary/20 text-primary text-xs"
                  >
                    {activeIntegrationCount}
                  </Badge>
                )}
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>Marketplace</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="default"
                size="icon"
                className="w-12 h-12 bg-accent hover:bg-accent/90"
                onClick={onDeployToggle}
              >
                <Icon icon="mdi:cloud-upload" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>Deploy to Azure</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant="ghost"
                size="icon"
                className="w-12 h-12"
                onClick={() => setExportModalOpen(true)}
              >
                <Icon icon="mdi:download" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>Export Diagram</p>
          </TooltipContent>
        </Tooltip>
      </div>

      <div className="h-px w-8 bg-border/50 my-1" />

      {/* View Toggles */}
      <div className="flex flex-col gap-2">
        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant={isAssetsOpen ? 'default' : 'ghost'}
                size="icon"
                className="w-12 h-12"
                onClick={onAssetsToggle}
              >
                <Icon icon="mdi:folder-multiple-image" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>Asset Manager</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant={isPaletteOpen ? 'default' : 'ghost'}
                size="icon"
                className="w-12 h-12"
                onClick={onPaletteToggle}
              >
                <Icon icon="mdi:view-grid-plus" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>Service Palette</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant={isInspectorOpen ? 'default' : 'ghost'}
                size="icon"
                className="w-12 h-12"
                onClick={onInspectorToggle}
                disabled={!onInspectorToggle}
              >
                <Icon icon="mdi:tune" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>Inspector</p>
          </TooltipContent>
        </Tooltip>

        <Tooltip>
          <TooltipTrigger asChild>
            <span className="inline-block">
              <Button
                variant={isChatOpen ? 'default' : 'ghost'}
                size="icon"
                className="w-12 h-12"
                onClick={onChatToggle}
              >
                <Icon icon="mdi:robot" className="text-xl" />
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>AI Assistant</p>
          </TooltipContent>
        </Tooltip>
      </div>

      <ExportModal
        open={exportModalOpen}
        onOpenChange={setExportModalOpen}
        canvasElement={getCanvasElement()}
      />
      </ScrollArea>
    </aside>
    </TooltipProvider>
  );
};
