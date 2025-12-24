import { Icon } from '@iconify/react';
import { memo, useMemo, useState } from 'react';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import type { IntegrationSettings } from '@/services/projectService';

type McpIntegrationKey = 'bicep' | 'terraform' | 'docs';
type AgentKey = 'security' | 'reliability' | 'cost' | 'networking' | 'observability' | 'dataStorage' | 'compliance' | 'identity' | 'naming';

interface IntegrationMarketplaceProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  settings: IntegrationSettings;
  onToggle: (key: McpIntegrationKey | AgentKey, enabled: boolean, type?: 'mcp' | 'agent') => void;
  isSaving?: boolean;
  disabled?: boolean;
  projectId?: string;
}

const MCP_OPTIONS: Array<{
  key: McpIntegrationKey;
  title: string;
  description: string;
  icon: string;
  badge?: string;
}> = [
  {
    key: 'bicep',
    title: 'Azure Bicep MCP',
    description: 'Use the Bicep MCP server for IaC validation, linting, and targeted code fixes.',
    icon: 'logos:microsoft-azure',
  },
  {
    key: 'terraform',
    title: 'Terraform MCP',
    description: 'Augment IaC generation with Terraform-native validation and policy checks.',
    icon: 'logos:terraform',
  },
  {
    key: 'docs',
    title: 'Reference Docs MCP',
    description: 'Allow agents to consult curated architecture guidance while reasoning.',
    icon: 'logos:microsoft',
    badge: 'Preview',
  },
];

const AGENT_OPTIONS: Array<{
  key: AgentKey;
  title: string;
  description: string;
  icon: string;
  badge?: string;
}> = [
  {
    key: 'security',
    title: 'Security Reviewer',
    description: 'Enforces network isolation, NSGs, Key Vault, managed identities, and Defender for Cloud.',
    icon: 'mdi:shield-lock',
  },
  {
    key: 'reliability',
    title: 'Reliability Reviewer',
    description: 'Adds multi-AZ/region redundancy, backup/restore, DR strategy, and health probes.',
    icon: 'mdi:heart-pulse',
  },
  {
    key: 'cost',
    title: 'Cost & Performance Optimizer',
    description: 'Right-sizes SKUs, suggests reservations, auto-pause for dev/test, and caching layers.',
    icon: 'mdi:currency-usd',
  },
  {
    key: 'networking',
    title: 'Networking Reviewer',
    description: 'Configures VNets, subnets, NSGs, route tables, private endpoints, and DNS.',
    icon: 'mdi:network',
  },
  {
    key: 'observability',
    title: 'Observability Reviewer',
    description: 'Adds Application Insights, Log Analytics, alerts, and diagnostic settings.',
    icon: 'mdi:monitor-eye',
  },
  {
    key: 'dataStorage',
    title: 'Data & Storage Reviewer',
    description: 'Enforces backup policies, storage lifecycle management, and data protection.',
    icon: 'mdi:database',
  },
  {
    key: 'compliance',
    title: 'Compliance Reviewer',
    description: 'Ensures audit logging, immutable logs, data residency, and regulatory compliance.',
    icon: 'mdi:gavel',
  },
  {
    key: 'identity',
    title: 'Identity & Governance Reviewer',
    description: 'Configures Entra ID, RBAC, PIM, and identity governance controls.',
    icon: 'mdi:account-key',
  },
  {
    key: 'naming',
    title: 'Naming & Tagging Enforcer',
    description: 'Applies Azure naming conventions and enforces resource tagging standards.',
    icon: 'mdi:tag-multiple',
  },
];

const IntegrationMarketplace = ({
  open,
  onOpenChange,
  settings,
  onToggle,
  isSaving,
  disabled,
  projectId,
}: IntegrationMarketplaceProps) => {
  const [activeTab, setActiveTab] = useState<'agents' | 'mcp'>('agents');
  const activeMcp = settings?.mcp ?? {};
  const activeAgents = settings?.agents ?? {};
  
  const enabledMcpCount = useMemo(
    () => MCP_OPTIONS.filter((opt) => Boolean(activeMcp?.[opt.key])).length,
    [activeMcp]
  );

  const enabledAgentsCount = useMemo(
    () => AGENT_OPTIONS.filter((opt) => Boolean(activeAgents?.[opt.key])).length,
    [activeAgents]
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-lg overflow-y-auto">
        <SheetHeader className="space-y-2">
          <SheetTitle>Agents & Tools</SheetTitle>
          <SheetDescription>
            Configure which AI agents and tools are available for your architecture workflows.
          </SheetDescription>
        </SheetHeader>

        {!projectId && (
          <div className="mt-6 rounded-md border border-amber-500/60 bg-amber-500/10 px-4 py-3 text-sm">
            <div className="flex items-start gap-2">
              <Icon icon="mdi:information" className="text-amber-500 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-500">Session-only settings</p>
                <p className="text-amber-600/90 text-xs mt-1">
                  These settings are active for the current session. Save the project to persist your preferences.
                </p>
              </div>
            </div>
          </div>
        )}

        <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as 'agents' | 'mcp')} className="mt-6">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="agents">
              AI Agents
              {enabledAgentsCount > 0 && (
                <Badge variant="secondary" className="ml-2 bg-primary/20 text-primary text-[10px]">
                  {enabledAgentsCount}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="mcp">
              MCP Tools
              {enabledMcpCount > 0 && (
                <Badge variant="secondary" className="ml-2 bg-primary/20 text-primary text-[10px]">
                  {enabledMcpCount}
                </Badge>
              )}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="agents" className="mt-4 space-y-4">
            <div className="rounded-md border border-primary/30 bg-primary/5 px-4 py-3 text-sm">
              <div className="flex items-start gap-2">
                <Icon icon="mdi:information" className="text-primary mt-0.5" />
                <div>
                  <p className="font-semibold text-primary">Azure Architect is always enabled</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    The base Architect agent generates the initial architecture. Enable reviewers below to add security, reliability, cost optimization, and compliance enhancements.
                  </p>
                </div>
              </div>
            </div>

            {AGENT_OPTIONS.map((option) => {
              const enabled = Boolean(activeAgents?.[option.key]);
              return (
                <div
                  key={option.key}
                  role="button"
                  tabIndex={disabled ? -1 : 0}
                  aria-disabled={disabled || isSaving ? true : undefined}
                  className="w-full rounded-xl border border-border/60 bg-background/80 p-4 text-left transition hover:border-primary/50 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  onClick={(event) => {
                    event.preventDefault();
                    if (disabled || isSaving) return;
                    onToggle(option.key, !enabled, 'agent');
                  }}
                  onKeyDown={(event) => {
                    if (disabled || isSaving) return;
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onToggle(option.key, !enabled, 'agent');
                    }
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-primary/10 p-2 text-primary">
                      <Icon icon={option.icon} className="text-2xl" />
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold">{option.title}</p>
                        {option.badge ? <Badge variant="secondary">{option.badge}</Badge> : null}
                      </div>
                      <p className="text-sm text-muted-foreground">{option.description}</p>
                    </div>
                    <Switch
                      onClick={(event) => event.stopPropagation()}
                      checked={enabled}
                      onCheckedChange={(value) => onToggle(option.key, value, 'agent')}
                      disabled={disabled || isSaving}
                    />
                  </div>
                </div>
              );
            })}

            <div className="rounded-lg border border-border/60 bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <div className={`h-2 w-2 rounded-full ${enabledAgentsCount > 0 ? 'bg-green-500' : 'bg-stone-400'}`} />
                {enabledAgentsCount > 0
                  ? `${enabledAgentsCount} reviewer ${enabledAgentsCount === 1 ? 'agent is' : 'agents are'} enabled.`
                  : 'Only the base Architect agent is enabled. Enable reviewers to enhance your architectures.'}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="mcp" className="mt-4 space-y-4">
            {MCP_OPTIONS.map((option) => {
              const enabled = Boolean(activeMcp?.[option.key]);
              return (
                <div
                  key={option.key}
                  role="button"
                  tabIndex={disabled ? -1 : 0}
                  aria-disabled={disabled || isSaving ? true : undefined}
                  className="w-full rounded-xl border border-border/60 bg-background/80 p-4 text-left transition hover:border-primary/50 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                  onClick={(event) => {
                    event.preventDefault();
                    if (disabled || isSaving) return;
                    onToggle(option.key, !enabled, 'mcp');
                  }}
                  onKeyDown={(event) => {
                    if (disabled || isSaving) return;
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      onToggle(option.key, !enabled, 'mcp');
                    }
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className="rounded-lg bg-primary/10 p-2 text-primary">
                      <Icon icon={option.icon} className="text-2xl" />
                    </div>
                    <div className="flex-1 space-y-1">
                      <div className="flex items-center gap-2">
                        <p className="font-semibold">{option.title}</p>
                        {option.badge ? <Badge variant="secondary">{option.badge}</Badge> : null}
                      </div>
                      <p className="text-sm text-muted-foreground">{option.description}</p>
                    </div>
                    <Switch
                      onClick={(event) => event.stopPropagation()}
                      checked={enabled}
                      onCheckedChange={(value) => onToggle(option.key, value, 'mcp')}
                      disabled={disabled || isSaving}
                    />
                  </div>
                </div>
              );
            })}

            <div className="rounded-lg border border-border/60 bg-muted/30 px-4 py-3 text-xs text-muted-foreground">
              <div className="flex items-center gap-2">
                <div className={`h-2 w-2 rounded-full ${enabledMcpCount > 0 ? 'bg-green-500' : 'bg-stone-400'}`} />
                {enabledMcpCount > 0
                  ? `${enabledMcpCount} MCP ${enabledMcpCount === 1 ? 'integration is' : 'integrations are'} enabled.`
                  : 'All MCP integrations are disabled.'}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
};

export default memo(IntegrationMarketplace);
