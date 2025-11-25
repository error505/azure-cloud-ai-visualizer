import { Icon } from '@iconify/react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useDiagramStore } from '@/store/diagramStore';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Slider } from '@/components/ui/slider';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useIacStore } from '@/store/iacStore';
import type { BicepResourceSnippet } from '@/store/iacStore';
import { Textarea } from '../ui/textarea';

interface InspectorPanelProps {
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  isChatOpen?: boolean;
  isIacOpen?: boolean;
}

// Small helper components for editing tags and endpoints as JSON text
type SelectedNodeLike = { id: string; data?: Record<string, unknown> };
const TagsEditor = ({ selectedNode, updateNodeData }: { selectedNode: SelectedNodeLike; updateNodeData: (id: string, patch: Record<string, unknown>) => void }) => {
  const initial = selectedNode.data?.tags ? JSON.stringify(selectedNode.data.tags, null, 2) : '{}';
  const [text, setText] = useState(initial);

  useEffect(() => {
    setText(selectedNode.data?.tags ? JSON.stringify(selectedNode.data.tags, null, 2) : '{}');
  }, [selectedNode]);

  return (
    <textarea
      className="w-full h-24 p-2 bg-muted/10 rounded border border-muted/20 text-sm overflow-auto"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        try {
          const parsed = JSON.parse(text || '{}');
          updateNodeData(selectedNode.id, { tags: parsed });
        } catch (err) {
          // ignore parse errors for now
        }
      }}
    />
  );
};

const EndpointsEditor = ({ selectedNode, updateNodeData }: { selectedNode: SelectedNodeLike; updateNodeData: (id: string, patch: Record<string, unknown>) => void }) => {
  const initial = selectedNode.data?.endpoints ? JSON.stringify(selectedNode.data.endpoints, null, 2) : '[]';
  const [text, setText] = useState(initial);

  useEffect(() => {
    setText(selectedNode.data?.endpoints ? JSON.stringify(selectedNode.data.endpoints, null, 2) : '[]');
  }, [selectedNode]);

  return (
    <textarea
      className="w-full h-28 p-2 bg-muted/10 rounded border border-muted/20 text-sm overflow-auto"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        try {
          const parsed = JSON.parse(text || '[]');
          if (Array.isArray(parsed)) {
            updateNodeData(selectedNode.id, { endpoints: parsed });
          }
        } catch (err) {
          // ignore parse errors
        }
      }}
    />
  );
};

const MetadataEditor = ({ selectedNode, updateNodeData }: { selectedNode: SelectedNodeLike; updateNodeData: (id: string, patch: Record<string, unknown>) => void }) => {
  const initial = selectedNode.data?.metadata ? JSON.stringify(selectedNode.data.metadata, null, 2) : '{}';
  const [text, setText] = useState(initial);

  useEffect(() => {
    setText(selectedNode.data?.metadata ? JSON.stringify(selectedNode.data.metadata, null, 2) : '{}');
  }, [selectedNode]);

  return (
    <textarea
      className="w-full h-32 p-2 bg-muted/10 rounded border border-muted/20 text-sm overflow-auto"
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={() => {
        try {
          const parsed = JSON.parse(text || '{}');
          updateNodeData(selectedNode.id, { metadata: parsed });
        } catch (err) {
          // ignore parse errors
        }
      }}
    />
  );
};

const derivePropertyEntries = (body: string) => {
  const entries: { name: string; value: string }[] = [];
  if (!body) {
    return entries;
  }

  const propertyRegex = /^\s*([a-zA-Z0-9_]+)\s*:\s*(.+)$/;
  const lines = body.split('\n');
  let depth = 0;

  for (const rawLine of lines) {
    const currentDepth = depth;
    const match = currentDepth === 1 ? propertyRegex.exec(rawLine) : null;
    if (match) {
      const name = match[1];
      let value = match[2].trim();

      if (!value || value === '{' || value === '[') {
        value = '...';
      } else if (value.endsWith('{')) {
        value = value.replace(/\{$/, '{ ... }');
      } else if (value.endsWith('[')) {
        value = value.replace(/\[$/, '[ ... ]');
      }

      entries.push({ name, value });
    }

    const openCount = (rawLine.match(/{/g) || []).length;
    const closeCount = (rawLine.match(/}/g) || []).length;
    depth = depth + openCount - closeCount;
    if (depth < 0) {
      depth = 0;
    }
  }

  return entries;
};

const GROUP_BICEP_KEYWORDS: Record<string, string[]> = {
  resourcegroup: ['resource group', 'resource groups'],
  managementgroup: ['management group', 'management groups'],
  subscription: ['subscription', 'subscriptions'],
};

const InspectorPanel = ({ isCollapsed = false, onToggleCollapse, isChatOpen = false, isIacOpen = false }: InspectorPanelProps = {}) => {
  const { selectedNode, updateNodeData } = useDiagramStore();

  const nodeData = (selectedNode?.data || {}) as any;

  const candidates = useMemo(() => {
    const baseCandidates: string[] = [
      String(nodeData.service?.title ?? ''),
      String(nodeData.title ?? ''),
      String(nodeData.service?.category ?? ''),
      String(nodeData.resourceType ?? ''),
    ];

    if (selectedNode?.type === 'azure.group') {
      const groupType = String(nodeData.groupType ?? '').toLowerCase();
      baseCandidates.push(groupType);
      baseCandidates.push(String(nodeData.label ?? ''));
      const groupKeywords = GROUP_BICEP_KEYWORDS[groupType];
      if (groupKeywords?.length) {
        baseCandidates.push(...groupKeywords);
      }
    }

    return baseCandidates
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean);
  }, [
    nodeData.groupType,
    nodeData.label,
    nodeData.resourceType,
    nodeData.service?.category,
    nodeData.service?.title,
    nodeData.title,
    selectedNode?.type,
  ]);

  const bicepResourceMap = useIacStore((state) => state.bicepResourcesByService);
  const emptyResourcesRef = useRef<BicepResourceSnippet[]>([]);

  const bicepResources = useMemo(() => {
    for (const key of candidates) {
      const match = bicepResourceMap[key];
      if (match?.length) {
        return match;
      }
    }
    return emptyResourcesRef.current;
  }, [bicepResourceMap, candidates]);

  const updateBicepResource = useIacStore((state) => state.updateBicepResource);
  const applyFullBicepTemplateEdit = useIacStore((state) => state.applyBicepTemplateEdit);
  const fullBicepTemplate = useIacStore((state) => state.currentBicepTemplate);

  const [selectedResourceIndex, setSelectedResourceIndex] = useState(0);
  const selectedBicepResource = bicepResources[selectedResourceIndex];
  const hasBicepResources = bicepResources.length > 0;

  const propertyEntries = useMemo(
    () => (selectedBicepResource ? derivePropertyEntries(selectedBicepResource.body) : []),
    [selectedBicepResource]
  );
  const tabsColumnClass = hasBicepResources ? 'grid-cols-3' : 'grid-cols-2';

  const [editedSnippet, setEditedSnippet] = useState(selectedBicepResource?.fullText ?? '');
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const saveTimerRef = useRef<number | null>(null);
  const baselineSnippetRef = useRef<string>(selectedBicepResource?.fullText ?? '');
  const [showFullTemplate, setShowFullTemplate] = useState(false);
  const [fullTemplateText, setFullTemplateText] = useState(fullBicepTemplate ?? '');
  const [fullTemplateSaving, setFullTemplateSaving] = useState(false);
  const [fullTemplateError, setFullTemplateError] = useState<string | null>(null);
  const fullTemplateTimerRef = useRef<number | null>(null);
  const fullTemplateBaselineRef = useRef<string>(fullBicepTemplate ?? '');

  useEffect(() => {
    setSelectedResourceIndex(0);
  }, [selectedNode?.id]);

  useEffect(() => {
    if (!hasBicepResources && selectedResourceIndex !== 0) {
      setSelectedResourceIndex(0);
    } else if (selectedResourceIndex >= bicepResources.length && bicepResources.length > 0) {
      setSelectedResourceIndex(0);
    }
  }, [bicepResources.length, hasBicepResources, selectedResourceIndex]);

  useEffect(() => {
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
  }, [selectedBicepResource]);

  useEffect(() => {
    if (!selectedBicepResource) {
      setEditedSnippet('');
      baselineSnippetRef.current = '';
      setShowFullTemplate(false);
      return;
    }

    const snippet = selectedBicepResource.fullText;
    baselineSnippetRef.current = snippet;
    setEditedSnippet(snippet);
    setSaveError(null);
  }, [selectedBicepResource]);

  useEffect(() => {
    if (fullTemplateTimerRef.current) {
      window.clearTimeout(fullTemplateTimerRef.current);
      fullTemplateTimerRef.current = null;
    }
    setShowFullTemplate(false);
    fullTemplateBaselineRef.current = fullBicepTemplate ?? '';
    setFullTemplateText(fullBicepTemplate ?? '');
    setFullTemplateSaving(false);
    setFullTemplateError(null);
  }, [fullBicepTemplate]);

  useEffect(() => {
    if (!selectedBicepResource) {
      return;
    }

    if (editedSnippet === baselineSnippetRef.current) {
      setIsSaving(false);
      return;
    }

    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
    }

    setIsSaving(true);
    saveTimerRef.current = window.setTimeout(() => {
      const result = updateBicepResource(
        selectedBicepResource.name,
        baselineSnippetRef.current,
        editedSnippet
      );
      if (result) {
        baselineSnippetRef.current = editedSnippet;
        setSaveError(null);
      } else {
        setSaveError('Unable to save changes. Please try again.');
      }
      setIsSaving(false);
      saveTimerRef.current = null;
    }, 800);

    return () => {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
    };
  }, [editedSnippet, selectedBicepResource, updateBicepResource]);

  useEffect(() => {
    if (fullTemplateText === fullTemplateBaselineRef.current) {
      setFullTemplateSaving(false);
      return;
    }

    if (fullTemplateTimerRef.current) {
      window.clearTimeout(fullTemplateTimerRef.current);
    }

    setFullTemplateSaving(true);
    fullTemplateTimerRef.current = window.setTimeout(() => {
      applyFullBicepTemplateEdit(fullTemplateText);
      fullTemplateBaselineRef.current = fullTemplateText;
      setFullTemplateSaving(false);
      setFullTemplateError(null);
      fullTemplateTimerRef.current = null;
    }, 800);

    return () => {
      if (fullTemplateTimerRef.current) {
        window.clearTimeout(fullTemplateTimerRef.current);
        fullTemplateTimerRef.current = null;
      }
    };
  }, [applyFullBicepTemplateEdit, fullTemplateText]);

  const update = (patch: Record<string, unknown>) => updateNodeData(selectedNode!.id, patch);

  // Helpers for conditional rendering based on resource type substrings
  const rt = (nodeData.resourceType || '').toLowerCase();
  const isAppServicePlan = rt.includes('serverfarms');
  const isWebApp = rt.includes('sites');
  const isCosmos = rt.includes('documentdb') || rt.includes('databaseaccounts');
  const isKeyVault = rt.includes('keyvault');
  const isSearch = rt.includes('search/searchservices');
  const hasIdentity = !!nodeData.identity || isWebApp;
  const isGroupNode = selectedNode?.type === 'azure.group';
  const groupType = (nodeData.groupType || '') as string;

  // Collapsed state - just show toggle button
  if (isCollapsed) {
    // Use fixed positioning when no side panels are open, absolute when they are
    const hasSidePanels = isChatOpen || isIacOpen;
    const buttonClassName = hasSidePanels
      ? "absolute -left-12 top-1/2 -translate-y-1/2 z-50 p-3 rounded-l-lg bg-primary/90 border border-r-0 border-primary/50 hover:bg-primary hover:border-primary transition-all shadow-2xl backdrop-blur-sm text-primary-foreground"
      : "fixed right-0 top-1/2 -translate-y-1/2 z-50 p-3 rounded-l-lg bg-primary/90 border border-r-0 border-primary/50 hover:bg-primary hover:border-primary transition-all shadow-2xl backdrop-blur-sm text-primary-foreground";
    
    return (
      <aside className="relative h-full w-0 flex-shrink-0 overflow-visible">
        <button
          onClick={onToggleCollapse}
          className={buttonClassName}
          title="Expand inspector panel"
          aria-label="Expand inspector panel"
          style={{ marginRight: 0 }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
      </aside>
    );
  }

  if (!selectedNode) {
    return (
      <aside className="glass-panel border-l border-border/50 w-96 p-6 flex flex-col relative">
        {/* Collapse button */}
        {onToggleCollapse && (
          <button
            onClick={onToggleCollapse}
            className="absolute right-2 top-2 p-2 rounded-md bg-background/80 border border-border/50 hover:bg-primary/10 hover:border-primary transition-all"
            title="Collapse inspector panel"
            aria-label="Collapse inspector panel"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18l6-6-6-6" />
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
        )}
        
        <div className="flex-1 flex flex-col items-center justify-center text-center">
          <Icon icon="mdi:information-outline" className="text-4xl text-muted-foreground mb-3" />
          <h3 className="font-semibold text-sm mb-1">No Node Selected</h3>
          <p className="text-xs text-muted-foreground">
            Select a node from the canvas to view and edit its properties
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="glass-panel border-l border-border/50 w-96 flex flex-col h-full min-h-0 relative">
      {/* Collapse button */}
      {onToggleCollapse && (
        <button
          onClick={onToggleCollapse}
          className="absolute right-2 top-2 z-20 p-2 rounded-md bg-background/80 border border-border/50 hover:bg-primary/10 hover:border-primary transition-all"
          title="Collapse inspector panel"
          aria-label="Collapse inspector panel"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 18l6-6-6-6" />
            <path d="M9 18l6-6-6-6" />
          </svg>
        </button>
      )}
      
      <div className="p-4 border-b border-border/50">
        <h2 className="text-sm font-semibold flex items-center gap-2">
          <Icon icon="mdi:tune" className="text-primary" />
          Inspector
        </h2>
      </div>

      <Tabs defaultValue="properties" className="flex-1 flex flex-col min-h-0">
        <TabsList className={`mx-4 mt-4 grid w-[calc(100%-2rem)] ${tabsColumnClass}`}>
          <TabsTrigger value="properties">Properties</TabsTrigger>
          {hasBicepResources && <TabsTrigger value="iac">Bicep</TabsTrigger>}
          <TabsTrigger value="animation">Animation</TabsTrigger>
        </TabsList>
        <ScrollArea className="flex-1 p-2 space-y-2 min-h-0">
          <TabsContent value="properties" className="flex-1 p-0 min-h-0">

            <div className="space-y-2">
              <Label htmlFor="node-title">Title</Label>
              <Input
                id="node-title"
                value={nodeData.title || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { title: e.target.value })}
                className="bg-muted/30"
              />
            </div>

            {isGroupNode && (
              <div className="space-y-4 glass-panel border border-border/40 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold">Group Type</span>
                  <Badge variant="outline" className="uppercase">{groupType || 'group'}</Badge>
                </div>
                <div className="space-y-2">
                  <Label>Metadata</Label>
                  <MetadataEditor selectedNode={selectedNode} updateNodeData={updateNodeData} />
                  <p className="text-xs text-muted-foreground">
                    Metadata is exported into IaC scopes. Provide values such as <code>subscriptionId</code>, <code>managementGroupId</code>, <code>policyDefinitionId</code>, or <code>roleDefinitionId</code>.
                  </p>
                </div>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="node-subtitle">Subtitle</Label>
              <Input
                id="node-subtitle"
                value={nodeData.subtitle || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { subtitle: e.target.value })}
                className="bg-muted/30"
                placeholder="Optional"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-region">Region</Label>
              <Input
                id="node-region"
                value={nodeData.region || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { region: e.target.value })}
                className="bg-muted/30"
                placeholder="e.g., westeurope"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-resourceType">Resource Type</Label>
              <Input
                id="node-resourceType"
                value={nodeData.resourceType || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { resourceType: e.target.value })}
                className="bg-muted/30"
                placeholder="e.g., Microsoft.Storage/storageAccounts"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-resourceGroup">Resource Group</Label>
              <Input
                id="node-resourceGroup"
                value={nodeData.resourceGroup || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { resourceGroup: e.target.value })}
                className="bg-muted/30"
                placeholder="e.g., rg-myapp-prod"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-subscription">Subscription ID</Label>
              <Input
                id="node-subscription"
                value={nodeData.subscriptionId || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { subscriptionId: e.target.value })}
                className="bg-muted/30"
                placeholder="Subscription ID"
              />
            </div>

            <div className="space-y-2">
              <Label>Status</Label>
              <div className="flex gap-2">
                {['inactive', 'active', 'warning', 'error'].map((status) => (
                  <button
                    key={status}
                    onClick={() => updateNodeData(selectedNode.id, { status })}
                    className={`flex-1 py-2 px-3 rounded text-xs font-medium transition-colors ${nodeData.status === status
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-muted/30 hover:bg-muted/50'
                      }`}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label>Badges</Label>
              <div className="flex flex-wrap gap-2">
                {nodeData.badges?.map((badge: string, i: number) => (
                  <Badge key={i} variant="secondary">
                    {badge}
                  </Badge>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">Badge editing coming soon</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-provisioning">Provisioning State</Label>
              <Input
                id="node-provisioning"
                value={nodeData.provisioningState || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { provisioningState: e.target.value })}
                className="bg-muted/30"
                placeholder="Succeeded | Creating | Failed | Deleting"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-sku">SKU</Label>
              <Input
                id="node-sku"
                value={nodeData.sku || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { sku: e.target.value })}
                className="bg-muted/30"
                placeholder="Optional SKU"
              />
            </div>

            {/* Structured SKU */}
            <div className="space-y-2">
              <Label>Structured SKU</Label>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  placeholder="tier"
                  value={nodeData.skuObject?.tier || ''}
                  onChange={(e) => update({ skuObject: { ...(nodeData.skuObject || {}), tier: e.target.value } })}
                  className="bg-muted/30"
                />
                <Input
                  placeholder="name"
                  value={nodeData.skuObject?.name || ''}
                  onChange={(e) => update({ skuObject: { ...(nodeData.skuObject || {}), name: e.target.value } })}
                  className="bg-muted/30"
                />
                <Input
                  placeholder="size"
                  value={nodeData.skuObject?.size || ''}
                  onChange={(e) => update({ skuObject: { ...(nodeData.skuObject || {}), size: e.target.value } })}
                  className="bg-muted/30"
                />
                <Input
                  placeholder="capacity"
                  value={nodeData.skuObject?.capacity?.toString() || ''}
                  onChange={(e) => {
                    const val = e.target.value.trim();
                    update({ skuObject: { ...(nodeData.skuObject || {}), capacity: val ? Number(val) : undefined } });
                  }}
                  className="bg-muted/30"
                />
              </div>
              <p className="text-xs text-muted-foreground">Use structured SKU when generating Bicep for plans or search services.</p>
            </div>

            {/* Identity */}
            {hasIdentity && (
              <div className="space-y-2">
                <Label>Identity</Label>
                <div className="grid grid-cols-2 gap-2">
                  <Select
                    value={nodeData.identity?.type || 'None'}
                    onValueChange={(v) => update({ identity: { ...(nodeData.identity || {}), type: v as 'None' | 'SystemAssigned' | 'UserAssigned' | 'SystemAssigned,UserAssigned' } })}
                  >
                    <SelectTrigger className="bg-muted/30"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="None">None</SelectItem>
                      <SelectItem value="SystemAssigned">SystemAssigned</SelectItem>
                      <SelectItem value="UserAssigned">UserAssigned</SelectItem>
                      <SelectItem value="SystemAssigned,UserAssigned">Both</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder="User Assigned IDs (comma)"
                    value={Object.keys(nodeData.identity?.userAssignedIdentities || {}).join(', ')}
                    onChange={(e) => {
                      const ids = e.target.value.split(',').map(s => s.trim()).filter(Boolean);
                      const map: Record<string, object> = {};
                      ids.forEach(id => { map[id] = {}; });
                      update({ identity: { ...(nodeData.identity || {}), userAssignedIdentities: map } });
                    }}
                    className="bg-muted/30"
                  />
                </div>
                <p className="text-xs text-muted-foreground">Configure managed identities for Web Apps or other resources.</p>
              </div>
            )}

            {/* App Service Config */}
            {(isWebApp) && (
              <div className="space-y-2">
                <Label>App Service Config</Label>
                <Input
                  placeholder="linuxFxVersion (e.g. NODE|18-lts)"
                  value={nodeData.appServiceConfig?.linuxFxVersion || ''}
                  onChange={(e) => update({ appServiceConfig: { ...(nodeData.appServiceConfig || {}), linuxFxVersion: e.target.value } })}
                  className="bg-muted/30"
                />
                <Input
                  placeholder="httpsOnly true/false"
                  value={nodeData.appServiceConfig?.httpsOnly ? 'true' : 'false'}
                  onChange={(e) => update({ appServiceConfig: { ...(nodeData.appServiceConfig || {}), httpsOnly: e.target.value === 'true' } })}
                  className="bg-muted/30"
                />
                <textarea
                  placeholder='App Settings JSON array [{"name":"KEY","value":"VAL"}]'
                  className="w-full h-24 p-2 bg-muted/30 rounded text-xs"
                  value={JSON.stringify(nodeData.appServiceConfig?.appSettings || [], null, 2)}
                  onChange={(e) => {
                    try {
                      const parsed = JSON.parse(e.target.value || '[]');
                      if (Array.isArray(parsed)) {
                        update({ appServiceConfig: { ...(nodeData.appServiceConfig || {}), appSettings: parsed as { name: string; value: string }[] } });
                      }
                    } catch (err) {
                      // ignore parse error
                    }
                  }}
                />
              </div>
            )}

            {/* Cosmos DB */}
            {isCosmos && (
              <div className="space-y-2">
                <Label>Cosmos DB</Label>
                <Select
                  value={nodeData.cosmosConfig?.consistencyLevel || 'Session'}
                  onValueChange={(v) => update({ cosmosConfig: { ...(nodeData.cosmosConfig || {}), consistencyLevel: v as 'Strong' | 'BoundedStaleness' | 'Session' | 'ConsistentPrefix' | 'Eventual' } })}
                >
                  <SelectTrigger className="bg-muted/30"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Strong">Strong</SelectItem>
                    <SelectItem value="BoundedStaleness">BoundedStaleness</SelectItem>
                    <SelectItem value="Session">Session</SelectItem>
                    <SelectItem value="ConsistentPrefix">ConsistentPrefix</SelectItem>
                    <SelectItem value="Eventual">Eventual</SelectItem>
                  </SelectContent>
                </Select>
                <textarea
                  placeholder='Locations JSON [{"locationName":"westeurope","failoverPriority":0}]'
                  className="w-full h-20 p-2 bg-muted/30 rounded text-xs"
                  value={JSON.stringify(nodeData.cosmosConfig?.locations || [], null, 2)}
                  onChange={(e) => { try { const p = JSON.parse(e.target.value || '[]'); if (Array.isArray(p)) update({ cosmosConfig: { ...(nodeData.cosmosConfig || {}), locations: p as { locationName: string; failoverPriority: number; isZoneRedundant?: boolean }[] } }); } catch (err) { /* ignore */ } }}
                />
                <Input
                  placeholder='Capabilities comma separated'
                  value={(nodeData.cosmosConfig?.capabilities || []).join(', ')}
                  onChange={(e) => update({ cosmosConfig: { ...(nodeData.cosmosConfig || {}), capabilities: e.target.value.split(',').map(s => s.trim()).filter(Boolean) } })}
                  className="bg-muted/30"
                />
              </div>
            )}

            {/* Key Vault */}
            {isKeyVault && (
              <div className="space-y-2">
                <Label>Key Vault</Label>
                <Select
                  value={nodeData.keyVaultConfig?.skuName || 'standard'}
                  onValueChange={(v) => update({ keyVaultConfig: { ...(nodeData.keyVaultConfig || {}), skuName: v as 'standard' | 'premium' } })}
                >
                  <SelectTrigger className="bg-muted/30"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="standard">standard</SelectItem>
                    <SelectItem value="premium">premium</SelectItem>
                  </SelectContent>
                </Select>
                <textarea
                  placeholder='Access Policies JSON'
                  className="w-full h-24 p-2 bg-muted/30 rounded text-xs"
                  value={JSON.stringify(nodeData.keyVaultConfig?.accessPolicies || [], null, 2)}
                  onChange={(e) => { try { const p = JSON.parse(e.target.value || '[]'); if (Array.isArray(p)) update({ keyVaultConfig: { ...(nodeData.keyVaultConfig || {}), accessPolicies: p as { tenantId: string; objectId: string; permissions: { secrets?: string[]; keys?: string[]; certificates?: string[] } }[] } }); } catch (err) { /* ignore */ } }}
                />
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {['enabledForDeployment', 'enabledForTemplateDeployment', 'enabledForDiskEncryption', 'enablePurgeProtection', 'enableSoftDelete'].map(flag => (
                    <button
                      key={flag}
                      onClick={() => {
                        const current = nodeData.keyVaultConfig || {};
                        const currentVal = (current as Record<string, unknown>)[flag];
                        const newVal = !currentVal;
                        update({ keyVaultConfig: { ...current, [flag]: newVal as boolean } });
                      }}
                      className={`py-1 px-2 rounded border text-left ${nodeData.keyVaultConfig && (nodeData.keyVaultConfig as Record<string, unknown>)[flag] ? 'bg-primary text-primary-foreground' : 'bg-muted/30'}`}
                    >{flag}</button>
                  ))}
                </div>
              </div>
            )}

            {/* Search Service */}
            {isSearch && (
              <div className="space-y-2">
                <Label>Search Service</Label>
                <Input
                  placeholder='replicaCount'
                  value={nodeData.searchConfig?.replicaCount?.toString() || ''}
                  onChange={(e) => update({ searchConfig: { ...(nodeData.searchConfig || {}), replicaCount: e.target.value ? Number(e.target.value) : undefined } })}
                  className="bg-muted/30"
                />
                <Input
                  placeholder='partitionCount'
                  value={nodeData.searchConfig?.partitionCount?.toString() || ''}
                  onChange={(e) => update({ searchConfig: { ...(nodeData.searchConfig || {}), partitionCount: e.target.value ? Number(e.target.value) : undefined } })}
                  className="bg-muted/30"
                />
                <Select
                  value={nodeData.searchConfig?.hostingMode || 'default'}
                  onValueChange={(v) => update({ searchConfig: { ...(nodeData.searchConfig || {}), hostingMode: v as 'default' | 'highDensity' } })}
                >
                  <SelectTrigger className="bg-muted/30"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">default</SelectItem>
                    <SelectItem value="highDensity">highDensity</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="node-tags">Tags (JSON)</Label>
              {/* tags edited as JSON text */}
              <TagsEditor selectedNode={selectedNode} updateNodeData={updateNodeData} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-endpoints">Endpoints (JSON)</Label>
              <EndpointsEditor selectedNode={selectedNode} updateNodeData={updateNodeData} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-publicip">Public IP</Label>
              <Input
                id="node-publicip"
                value={nodeData.publicIp || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { publicIp: e.target.value || null })}
                className="bg-muted/30"
                placeholder="x.x.x.x"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-privateip">Private IP</Label>
              <Input
                id="node-privateip"
                value={nodeData.privateIp || ''}
                onChange={(e) => updateNodeData(selectedNode.id, { privateIp: e.target.value || null })}
                className="bg-muted/30"
                placeholder="10.x.x.x"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="node-dependson">Depends On (comma separated IDs)</Label>
              <Input
                id="node-dependson"
                value={((nodeData.dependsOn || []) as string[]).join(', ')}
                onChange={(e) => updateNodeData(selectedNode.id, { dependsOn: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                className="bg-muted/30"
                placeholder="service-id-1, service-id-2"
              />
            </div>

            <div className="space-y-2">
              <Label>Timestamps</Label>
              <div className="text-xs text-muted-foreground">
                <div>Created: {nodeData.createdAt || '—'}</div>
                <div>Updated: {nodeData.updatedAt || '—'}</div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="iac" className="flex-1 p-0 min-h-0">

            {hasBicepResources ? (
              <div className="p-4 space-y-4">
                {bicepResources.length > 1 && (
                  <div className="space-y-2">
                    <Label>Resource</Label>
                    <Select
                      value={selectedResourceIndex.toString()}
                      onValueChange={(value) => setSelectedResourceIndex(Number(value))}
                    >
                      <SelectTrigger className="bg-muted/30">
                        <SelectValue placeholder="Select resource" />
                      </SelectTrigger>
                      <SelectContent>
                        {bicepResources.map((resource, index) => (
                          <SelectItem key={`${resource.name}-${index}`} value={index.toString()}>
                            {resource.name} ({resource.type})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}

                {selectedBicepResource ? (
                  <>
                    <div className="space-y-2">
                      <div className="text-xs uppercase text-muted-foreground flex items-center justify-between">
                        <span>Template</span>
                        <span className="text-[10px] text-muted-foreground/80">
                          {isSaving ? 'Saving…' : saveError ? 'Save failed' : 'Saved'}
                        </span>
                      </div>

                      <textarea
                        className="w-full h-48 font-mono text-[11px] leading-5 bg-muted/15 border border-border/40 rounded p-3 resize-vertical focus:outline-none focus:ring-2 focus:ring-primary/60"
                        value={editedSnippet}
                        onChange={(e) => setEditedSnippet(e.target.value)}
                        spellCheck={false}
                      />

                      {saveError && (
                        <p className="text-[11px] text-destructive">{saveError}</p>
                      )}
                    </div>
                    <div className="space-y-2">
                      <div className="text-xs uppercase text-muted-foreground">Properties</div>
                      {propertyEntries.length ? (
                        <ul className="text-xs text-muted-foreground space-y-1">
                          {propertyEntries.map((prop, index) => (
                            <li
                              key={`${prop.name}-${index}`}
                              className="flex items-start justify-between gap-2"
                            >
                              <span className="text-foreground font-medium">{prop.name}</span>
                              <span className="text-muted-foreground text-right break-words">
                                {prop.value}
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-muted-foreground">
                          No top-level properties detected in this resource block.
                        </p>
                      )}
                    </div>
                    <ScrollArea className="box-border max-h-28 w-full rounded-lg border border-input bg-background ring-offset-background focus-within:ring-1 focus-within:ring-ring 2xl:max-h-40">
                      {fullBicepTemplate !== null && (

                        <div className="space-y-2 border border-border/20 rounded-md p-3 bg-muted/10">
                          <div className="flex items-center justify-between text-xs uppercase text-muted-foreground">
                            <span>Full Bicep Template</span>
                            <div className="flex items-center gap-2">
                              <span className="text-[10px] text-muted-foreground/70">
                                {fullTemplateSaving ? 'Saving…' : fullTemplateError ? 'Save failed' : 'Saved'}
                              </span>
                              <button
                                type="button"
                                className="text-foreground bg-muted/40 border border-border/30 rounded px-2 py-1 hover:bg-muted/60 transition text-[11px]"
                                onClick={() => setShowFullTemplate((prev) => !prev)}
                              >
                                {showFullTemplate ? 'Hide' : 'Show'}
                              </button>
                            </div>
                          </div>

                          {showFullTemplate && (
                            <>

                              <Textarea
                                className="resize-none border-none w-full min-h-[240px] font-mono text-[11px] leading-5 bg-transparent p-3 focus:outline-none focus:ring-2 focus:ring-primary/60"
                                value={fullTemplateText}
                                onChange={(e) => setFullTemplateText(e.target.value)}
                                spellCheck={false}
                              />

                              {fullTemplateError && (
                                <p className="text-[11px] text-destructive">{fullTemplateError}</p>
                              )}
                            </>

                          )}

                        </div>

                      )}
                    </ScrollArea>
                  </>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Select a resource to view its generated Bicep block.
                  </p>
                )}
              </div>
            ) : (
              <div className="p-4 text-xs text-muted-foreground">
                Generated Bicep code is not yet available for this node. Trigger IaC generation to populate this
                panel.
              </div>
            )}

          </TabsContent>

          <TabsContent value="animation" className="flex-1 p-0 min-h-0">
            <div className="space-y-2">
              <Label>Animation Effect</Label>
              <Select
                value={nodeData.animationProfile?.effect || 'none'}
                onValueChange={(value) =>
                  updateNodeData(selectedNode.id, {
                    animationProfile: {
                      ...(nodeData.animationProfile || {}),
                      effect: value,
                    },
                  })
                }
              >
                <SelectTrigger className="bg-muted/30">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">None</SelectItem>
                  <SelectItem value="pulse">Pulse</SelectItem>
                  <SelectItem value="glow">Glow</SelectItem>
                  <SelectItem value="rotate">Rotate</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Animation Speed</Label>
              <div className="flex items-center gap-4">
                <Slider
                  value={[nodeData.animationProfile?.speed || 1]}
                  onValueChange={(value) =>
                    updateNodeData(selectedNode.id, {
                      animationProfile: {
                        ...(nodeData.animationProfile || {}),
                        speed: value[0],
                      },
                    })
                  }
                  min={0.5}
                  max={3}
                  step={0.1}
                  className="flex-1"
                />
                <span className="text-sm text-muted-foreground w-12 text-right">
                  {(nodeData.animationProfile?.speed || 1).toFixed(1)}x
                </span>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Preview</Label>
              <div className="glass-panel p-6 rounded-lg flex items-center justify-center">
                <div
                  className={`
                  p-4 rounded-xl bg-primary/20 transition-all
                  ${nodeData.animationProfile?.effect === 'pulse' ? 'animate-pulse' : ''}
                  ${nodeData.animationProfile?.effect === 'glow' ? 'glow-primary' : ''}
                  ${nodeData.animationProfile?.effect === 'rotate' ? 'animate-spin-slow' : ''}
                `}
                >
                  {nodeData.iconPath ? (
                    <img
                      src={nodeData.iconPath}
                      alt={nodeData.title as string}
                      className="h-10 w-10 object-contain"
                    />
                  ) : nodeData.icon ? (
                    <Icon icon={nodeData.icon as string} className="text-3xl text-primary" />
                  ) : (
                    <Icon icon="mdi:cube-outline" className="text-3xl text-primary" />
                  )}
                </div>
              </div>
            </div>

            <div className="glass-panel p-4 rounded-lg space-y-2">
              <div className="flex items-center gap-2">
                <Icon icon="mdi:information-outline" className="text-accent" />
                <h4 className="text-xs font-semibold">Animation Tips</h4>
              </div>
              <ul className="text-xs text-muted-foreground space-y-1 list-disc list-inside">
                <li>Use pulse for emphasis</li>
                <li>Glow for active services</li>
                <li>Rotate for processing/loading states</li>
              </ul>
            </div>
          </TabsContent>
        </ScrollArea>
      </Tabs>
    </aside>
  );
};

export default InspectorPanel;
