import React, { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Icon } from '@iconify/react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useToast } from '@/hooks/use-toast';
import { useSupabase } from '@/context/SupabaseContext';
import { useChat, type TraceEventRecord } from '@/hooks/useChat';
import RunProgress from '@/components/RunProgress';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '@/components/ui/accordion';
import { useDiagramStore } from '@/store/diagramStore';
import { ArchitectureParser, ParsedArchitecture } from '@/services/architectureParser';
import { AzureService } from '@/data/azureServices';
import { ImageUpload } from '@/components/upload/ImageUpload';
import { saveProjectDiagramState, type ProjectDiagramState, type IntegrationSettings } from '@/services/projectService';
import { importDiagramImage, hasMeaningfulAwsCoverage, hasMeaningfulGcpCoverage, detectPrimaryProvider } from '@/services/diagramImport';
import { DiagramImagePayload } from '@/types/diagramUpload';
import type { Edge as RFEdge, Node as RFNode } from '@xyflow/react';
import TypewriterMarkdown from '@/components/ui/TypewriterMarkdown';

const dataUrlToFile = (dataUrl: string, fileName: string, mimeType?: string): File => {
  const [meta, base64 = ''] = dataUrl.split(',');
  const matchedType = mimeType || meta?.match(/data:(.*);base64/)?.[1] || 'image/png';
  const binary = atob(base64);
  const len = binary.length;
  const array = new Uint8Array(len);
  for (let i = 0; i < len; i += 1) {
    array[i] = binary.charCodeAt(i);
  }
  return new File([array], fileName || 'diagram.png', { type: matchedType });
};

interface ChatPanelProps {
  isOpen: boolean;
  onToggle: () => void;
  initialPrompt?: string;
  onInitialPromptConsumed?: () => void;
  projectId?: string;
  onIacGenerated?: (payload: {
    bicep?: { template: string; parameters?: Record<string, unknown> | null };
    terraform?: { template: string; parameters?: Record<string, unknown> | null };
  }) => void | Promise<void>;
  initialDiagramImage?: DiagramImagePayload | null;
  integrationSettings?: IntegrationSettings;
  onOpenIntegrations?: () => void;
}

const ChatPanel: React.FC<ChatPanelProps> = ({
  isOpen,
  onToggle,
  initialPrompt,
  onInitialPromptConsumed,
  projectId,
  onIacGenerated,
  initialDiagramImage,
  integrationSettings,
  onOpenIntegrations,
}) => {
  const [inputMessage, setInputMessage] = useState('');
  const [showImageUpload, setShowImageUpload] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { toast } = useToast();
  const addNodesFromArchitecture = useDiagramStore((state) => state.addNodesFromArchitecture);
  const replaceDiagram = useDiagramStore((state) => state.replaceDiagram);
  const setViewSnapshot = useDiagramStore((state) => state.setViewSnapshot);
  const setIsGenerating = useDiagramStore((state) => state.setIsGenerating);
  const initialPromptRef = useRef<string | null>(null);
  const processedDiagramMessages = useRef<Set<string>>(new Set());
  const azureDiagramSignatureRef = useRef<string | null>(null);
  const initialDiagramHandledRef = useRef(false);
  const initialDiagramImageRef = useRef<string | null>(null);
  const { client: supabaseClient } = useSupabase();
  const [panelView, setPanelView] = useState<'chat' | 'agents'>('chat');

  const {
    messages,
    isConnected,
    isTyping,
    sendMessage,
    connectWebSocket,
    disconnect,
    addAssistantMessage,
    runState,
    latestDiagram,
    traceEventsByRunId,
  } = useChat({
    onError: (error) => {
      toast({
        title: "Error",
        description: error.message,
        variant: "destructive",
      });
    },
    supabase: supabaseClient ?? undefined,
    projectId,
    integrationSettings,
  });

  const totalIntegrations = useMemo(
    () => {
      const mcpCount = integrationSettings?.mcp ? Object.values(integrationSettings.mcp).filter(Boolean).length : 0;
      const agentCount = integrationSettings?.agents ? Object.entries(integrationSettings.agents).filter(([key, value]) => key !== 'architect' && value).length : 0;
      return mcpCount + agentCount;
    },
    [integrationSettings]
  );

  const [highlightedRunId, setHighlightedRunId] = useState<string | null>(null);
  const [revealedPrompts, setRevealedPrompts] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (runState?.runId) {
      setHighlightedRunId(runState.runId);
    }
  }, [runState?.runId]);

  const latestRunId = useMemo(() => {
    const ids = Object.keys(traceEventsByRunId || {});
    if (ids.length === 0) {
      return highlightedRunId;
    }
    ids.sort();
    return ids[ids.length - 1];
  }, [traceEventsByRunId, highlightedRunId]);

  const agentRunSummaries = useMemo(() => {
    if (!latestRunId) {
      return [];
    }
    const events = traceEventsByRunId[latestRunId] ?? [];
    const grouped = new Map<
      string,
      { agent: string; deltas: string[]; summary?: string | null; error?: string | null; phase?: string; ts: number }
    >();

    for (const ev of events) {
      if (!ev.agent) continue;
      const bucket =
        grouped.get(ev.agent) ??
        { agent: ev.agent, deltas: [], summary: null, error: null, phase: ev.phase, ts: ev.ts };
      if (ev.messageDelta) {
        bucket.deltas.push(ev.messageDelta);
      }
      if (ev.summary) {
        bucket.summary = ev.summary;
      }
      if (ev.error) {
        bucket.error = ev.error;
      }
      bucket.phase = ev.phase;
      bucket.ts = ev.ts;
      grouped.set(ev.agent, bucket);
    }

    return Array.from(grouped.values())
      .map((entry) => ({
        ...entry,
        text: (entry.summary || entry.deltas.join(' ')).trim(),
      }))
      .sort((a, b) => a.ts - b.ts);
  }, [latestRunId, traceEventsByRunId]);

  const formatTraceTimestamp = useCallback((value: number) => {
    const ms = value > 1e12 ? value : value * 1000;
    return new Date(ms).toLocaleTimeString();
  }, []);

  // Format assistant text into readable paragraphs.
  // - Preserve code blocks (```...```) and JSON-like outputs
  // - Only insert paragraph breaks for plain prose
  const formatAssistantText = useCallback((text: string) => {
    if (!text || typeof text !== 'string') return text;
    
    // IMPORTANT: Don't apply complex formatting transformations
    // The text should be rendered as markdown directly to avoid breaking content
    // Just return the text as-is and let ReactMarkdown handle it
    return text;
  }, []);

  const resolveTraceDetail = useCallback((event: TraceEventRecord): string => {
    if (event.error) return event.error;
    if (event.messageDelta) return event.messageDelta;
    if (event.summary) return event.summary;
    const candidateKeys = ['note', 'goal', 'objective', 'details', 'hint'];
    for (const key of candidateKeys) {
      const raw = event.meta[key];
      if (typeof raw === 'string' && raw.trim()) {
        return raw;
      }
    }
    const telemetryNote = event.telemetry['note'];
    if (typeof telemetryNote === 'string' && telemetryNote.trim()) {
      return telemetryNote;
    }
    const asJson = Object.keys(event.meta ?? {}).length ? JSON.stringify(event.meta) : '';
    return asJson;
  }, []);
  

  // Function to check if a message contains architecture information
  const containsArchitecture = (content: string): boolean => {
    const architectureKeywords = [
      'architecture', 'azure app service', 'sql database', 'storage account',
      'azure functions', 'application gateway', 'virtual network', 'bicep',
      'terraform', 'resource', 'microsoft.web', 'microsoft.sql', 'microsoft.storage'
    ];
    
    const lowerContent = content.toLowerCase();
    return architectureKeywords.some(keyword => lowerContent.includes(keyword));
  };

  const persistDiagramState = useCallback(async () => {
    if (!projectId || !supabaseClient) {
      return;
    }
    try {
      const { nodes, edges } = useDiagramStore.getState();
      const payload: ProjectDiagramState = {
        nodes,
        edges,
        saved_at: new Date().toISOString(),
      };
      await saveProjectDiagramState(supabaseClient, projectId, payload);
    } catch (error) {
      console.error('[ChatPanel] Failed to persist diagram state', error);
    }
  }, [projectId, supabaseClient]);

  useEffect(() => {
    processedDiagramMessages.current.clear();
    azureDiagramSignatureRef.current = null;
    initialDiagramHandledRef.current = false;
  }, [projectId]);

  const applyAzureDiagramSnapshot = useCallback(
    (diagram: unknown) => {
      if (!diagram || typeof diagram !== 'object') {
        return;
      }
      const payload = diagram as { nodes?: RFNode[]; edges?: RFEdge[] };
      if (!Array.isArray(payload.nodes)) {
        return;
      }
      const signature = JSON.stringify(payload);
      if (azureDiagramSignatureRef.current === signature) {
        return;
      }
      azureDiagramSignatureRef.current = signature;
      const edges = Array.isArray(payload.edges) ? (payload.edges as RFEdge[]) : [];
      setViewSnapshot('azure', payload.nodes as RFNode[], edges);
    },
    [setViewSnapshot]
  );

  // Function to visualize architecture from AI response
  const visualizeArchitecture = useCallback(
    (messageContent: string, replaceExisting: boolean = false, structured?: ParsedArchitecture | null) => {
      try {
        const architecture = structured ?? ArchitectureParser.parseResponse(messageContent);
        // Parsed architecture for visualization

        if (architecture.services.length === 0) {
          toast({
            title: 'No Architecture Found',
            description: 'Could not extract Azure services from this message.',
            variant: 'destructive',
          });
          return;
        }

        const nodes = ArchitectureParser.generateNodes(architecture);
        // Generated nodes for visualization

        if (replaceExisting) {
          replaceDiagram(nodes, architecture.connections);
        } else {
          addNodesFromArchitecture(nodes, architecture.connections);
        }
        void persistDiagramState();

        toast({
          title: 'Architecture Visualized',
          description: `Applied ${architecture.services.length} Azure services from the assistant response.`,
        });
      } catch (error) {
        console.error('[ChatPanel] Error visualizing architecture', error);
        toast({
          title: 'Visualization Error',
          description: error instanceof Error ? error.message : 'Failed to process the architecture payload.',
          variant: 'destructive',
        });
      }
    },
    [addNodesFromArchitecture, persistDiagramState, replaceDiagram, toast]
  );
  
    // Validate a structured architecture payload before applying to canvas
    const validateStructuredArchitecture = useCallback((architecture: unknown): { valid: boolean; errors: string[] } => {
      const errors: string[] = [];
      if (!architecture || typeof architecture !== 'object') {
        errors.push('Architecture payload is not an object.');
        return { valid: false, errors };
      }

      const arch = architecture as Record<string, unknown>;
      const services = Array.isArray(arch.services) ? (arch.services as unknown[]) : [];
      const groups = Array.isArray(arch.groups) ? (arch.groups as unknown[]) : [];
      const connections = Array.isArray(arch.connections) ? (arch.connections as unknown[]) : [];

      if (services.length === 0) {
        errors.push('No services found in architecture.');
      }

      const serviceIds = new Set<string>();
      for (const sItem of services) {
        if (!sItem || typeof sItem !== 'object') {
          errors.push('One of the services is not an object.');
          continue;
        }
        const s = sItem as Record<string, unknown>;
        const sid = typeof s.id === 'string' ? s.id : undefined;
        if (!sid) {
          errors.push(`Service missing valid 'id': ${JSON.stringify(s).slice(0, 80)}`);
          continue;
        }
        const stitle = typeof s.title === 'string' ? s.title : undefined;
        if (!stitle) {
          errors.push(`Service '${sid}' missing valid 'title'.`);
        }
        serviceIds.add(sid);
      }

      // Validate groups reference known members
      // collect group ids first
      const groupIds = new Set<string>();
      for (const gItem of groups) {
        if (!gItem || typeof gItem !== 'object') continue;
        const gcast = gItem as Record<string, unknown>;
        if (typeof gcast.id === 'string') groupIds.add(gcast.id);
      }

      for (const gItem of groups) {
        if (!gItem || typeof gItem !== 'object') {
          errors.push('One of the groups is not an object.');
          continue;
        }
        const g = gItem as Record<string, unknown>;
        const gid = typeof g.id === 'string' ? g.id : '<unknown>';
        if (gid === '<unknown>') {
          errors.push(`Group missing valid 'id': ${JSON.stringify(g).slice(0, 80)}`);
        }
        const members = Array.isArray(g.members) ? g.members : [];
        for (const m of members) {
          if (typeof m !== 'string') {
            errors.push(`Group '${gid}' has non-string member: ${String(m)}`);
          } else if (!serviceIds.has(m) && !groupIds.has(m)) {
            // allow nested group reference but warn if neither service nor group
            errors.push(`Group '${gid}' references unknown member '${m}'.`);
          }
        }
      }

      // Validate connections reference known services
      for (const cItem of connections) {
        if (!cItem || typeof cItem !== 'object') {
          errors.push('One of the connections is not an object.');
          continue;
        }
        const c = cItem as Record<string, unknown>;
        const from = typeof c.from === 'string' ? c.from : undefined;
        const to = typeof c.to === 'string' ? c.to : undefined;
        if (!from) {
          errors.push(`Connection missing valid 'from': ${JSON.stringify(c).slice(0, 80)}`);
        } else if (!serviceIds.has(from)) {
          errors.push(`Connection 'from' references unknown service '${from}'.`);
        }
        if (!to) {
          errors.push(`Connection missing valid 'to': ${JSON.stringify(c).slice(0, 80)}`);
        } else if (!serviceIds.has(to)) {
          errors.push(`Connection 'to' references unknown service '${to}'.`);
        }
      }

      return { valid: errors.length === 0, errors };
    }, []);

  useEffect(() => {
    if (!initialDiagramImage || !initialDiagramImage.dataUrl) {
      return;
    }
    if (initialDiagramImageRef.current === initialDiagramImage.dataUrl) {
      return;
    }
    initialDiagramImageRef.current = initialDiagramImage.dataUrl;

    const run = async () => {
      try {
        setIsGenerating(true);
        toast({
          title: 'Analyzing diagram image',
          description: 'Extracting services from the uploaded architecture diagram...',
        });
        const file = dataUrlToFile(
          initialDiagramImage.dataUrl,
          initialDiagramImage.name || 'diagram.png',
          initialDiagramImage.type
        );
        const { architecture } = await importDiagramImage(file);
        visualizeArchitecture('Diagram imported from landing page', true, architecture);
        toast({
          title: 'Diagram Imported',
          description: `Detected ${architecture.services.length} services.`,
        });
        // Surface a chat message so the user sees the outcome
        addAssistantMessage(
          `Imported diagram from image. Detected ${architecture.services.length} services and applied to canvas.`,
          { visionOnly: true, diagram: { structured: architecture, raw: null, runId: undefined } }
        );
      } catch (error) {
        console.error('[ChatPanel] Failed to auto-import diagram image', error);
        toast({
          title: 'Diagram Import Failed',
          description: error instanceof Error ? error.message : 'Unable to process the uploaded diagram.',
          variant: 'destructive',
        });
      }
    };

    void run();
  }, [initialDiagramImage, toast, visualizeArchitecture]);

  // WebSocket connection management - DISABLED for stability, using REST API
  useEffect(() => {
    // Disabled WebSocket auto-connection to avoid unnecessary connection attempts
    // The chat uses REST API which is working perfectly with OpenAI
    // Chat panel ready; team streaming will connect on demand
  }, [isOpen]);

  const handleSendMessage = useCallback(async (content: string) => {
    if (!content.trim()) {
      return;
    }
    setIsGenerating(true); // Show loading overlay when sending message
    await sendMessage(content);
    setInputMessage('');
    // Reset textarea height after sending
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }
  }, [sendMessage, setIsGenerating]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSendMessage(inputMessage);
  };

  useEffect(() => {
    if (!initialDiagramImage || !initialDiagramImage.dataUrl) {
      return;
    }
    if (initialDiagramHandledRef.current) {
      return;
    }
    initialDiagramHandledRef.current = true;

    const run = async () => {
      try {
        toast({
          title: 'Analyzing diagram image',
          description: 'Extracting services from the uploaded architecture diagram...',
        });
        const file = dataUrlToFile(
          initialDiagramImage.dataUrl,
          initialDiagramImage.name || 'diagram.png',
          initialDiagramImage.type
        );
        const { architecture } = await importDiagramImage(file);
        visualizeArchitecture('Diagram imported from landing page', true, architecture);
        toast({
          title: 'Diagram Imported',
          description: `Detected ${architecture.services.length} services from the uploaded diagram.`,
        });
      } catch (error) {
        console.error('[ChatPanel] Failed to auto-import diagram image', error);
        toast({
          title: 'Diagram Import Failed',
          description: error instanceof Error ? error.message : 'Unable to process the uploaded diagram.',
          variant: 'destructive',
        });
      } finally {
        setIsGenerating(false);
      }
    };

    void run();
  }, [initialDiagramImage, toast, visualizeArchitecture]);

  useEffect(() => {
    if (!latestDiagram) {
      return;
    }
    if (processedDiagramMessages.current.has(latestDiagram.messageId)) {
      console.log('[ChatPanel] ⏭️ Already processed diagram', { messageId: latestDiagram.messageId });
      return;
    }
    processedDiagramMessages.current.add(latestDiagram.messageId);
    console.log('[ChatPanel] 🎨 Processing diagram update', { messageId: latestDiagram.messageId });
    try {
      let architecture = latestDiagram.architecture;
      let usedFallback = false;

      // If we have a structured architecture, validate it first
      if (architecture) {
        const { valid, errors } = validateStructuredArchitecture(architecture);
        if (!valid) {
          console.warn('[ChatPanel] Structured architecture failed validation', { errors });
          // Try fallback to parsing the message text if available
          if (latestDiagram.messageText) {
            architecture = ArchitectureParser.parseResponse(latestDiagram.messageText);
            usedFallback = true;
          } else {
            setIsGenerating(false);
            toast({
              title: 'Diagram Rejected',
              description: `Agent returned a structured diagram, but it failed validation: ${errors.slice(0,3).join('; ')}`,
              variant: 'destructive',
            });
            return;
          }
        }
      }

      // If there was no structured architecture or we fell back, parse the message text
      if (!architecture || (usedFallback && !architecture)) {
        if (latestDiagram.messageText) {
          architecture = ArchitectureParser.parseResponse(latestDiagram.messageText);
        }
      }

      if (!architecture) {
        throw new Error('No architecture data was returned by the agent.');
      }

      // Validate the final architecture before applying
      const { valid, errors } = validateStructuredArchitecture(architecture as unknown);
      if (!valid) {
        console.warn('[ChatPanel] Final architecture failed validation', { errors });
        setIsGenerating(false);
        toast({
          title: 'Diagram Rejected',
          description: `Generated architecture failed validation: ${errors.slice(0,3).join('; ')}`,
          variant: 'destructive',
        });
        return;
      }

      const nodes = ArchitectureParser.generateNodes(architecture);
      replaceDiagram(nodes, architecture.connections);
      setIsGenerating(false); // Diagram applied, hide loading
      void persistDiagramState();
      // Diagram applied to canvas successfully
      toast({
        title: 'Diagram Updated',
        description: `Applied ${architecture.services.length} services from the latest agent run.`,
      });
    } catch (error) {
      console.error('[ChatPanel] Failed to apply structured diagram payload', error);
      setIsGenerating(false); // Hide loading even on error
      toast({
        title: 'Diagram Update Failed',
        description: error instanceof Error ? error.message : 'Unable to apply the generated architecture.',
        variant: 'destructive',
      });
    }

    const iac = latestDiagram.iac;
    if (iac && onIacGenerated) {
      const { bicep, terraform } = iac;
      const bicepTemplate =
        bicep && typeof bicep.bicep_code === 'string' ? bicep.bicep_code : undefined;
      const terraformTemplate =
        terraform && typeof terraform.terraform_code === 'string' ? terraform.terraform_code : undefined;
      const resolveAwsMigration = (artifact: unknown): Record<string, unknown> | null => {
        if (!artifact || typeof artifact !== 'object') {
          return null;
        }
        const params = (artifact as Record<string, unknown>).parameters;
        if (!params || typeof params !== 'object') {
          return null;
        }
        const migration = (params as Record<string, unknown>).aws_migration;
        return migration && typeof migration === 'object' ? (migration as Record<string, unknown>) : null;
      };

      const resolveGcpMigration = (artifact: unknown): Record<string, unknown> | null => {
        if (!artifact || typeof artifact !== 'object') {
          return null;
        }
        const params = (artifact as Record<string, unknown>).parameters;
        if (!params || typeof params !== 'object') {
          return null;
        }
        const migration = (params as Record<string, unknown>).gcp_migration;
        return migration && typeof migration === 'object' ? (migration as Record<string, unknown>) : null;
      };

      const migrationPayload = resolveAwsMigration(bicep) || resolveAwsMigration(terraform) || 
                               resolveGcpMigration(bicep) || resolveGcpMigration(terraform);
      if (migrationPayload && 'azure_diagram' in migrationPayload) {
        applyAzureDiagramSnapshot((migrationPayload as Record<string, unknown>).azure_diagram);
      }

      if (bicepTemplate || terraformTemplate) {
        onIacGenerated({
          bicep: bicepTemplate
            ? {
                template: bicepTemplate,
                parameters:
                  bicep &&
                  typeof bicep === 'object' &&
                  'parameters' in bicep &&
                  bicep.parameters &&
                  typeof bicep.parameters === 'object'
                    ? (bicep.parameters as Record<string, unknown>)
                    : null,
              }
            : undefined,
          terraform: terraformTemplate
            ? {
                template: terraformTemplate,
                parameters:
                  terraform &&
                  typeof terraform === 'object' &&
                  'parameters' in terraform &&
                  terraform.parameters &&
                  typeof terraform.parameters === 'object'
                    ? (terraform.parameters as Record<string, unknown>)
                    : null,
              }
            : undefined,
        });
      }
    }
  }, [applyAzureDiagramSnapshot, latestDiagram, onIacGenerated, persistDiagramState, replaceDiagram, setIsGenerating, toast, validateStructuredArchitecture]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    const viewport = scrollAreaRef.current?.querySelector<HTMLElement>('[data-radix-scroll-area-viewport]');
    if (!viewport) {
      return;
    }
    // Use a small delay to ensure content is rendered
    const scrollTimeout = setTimeout(() => {
      viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' });
    }, 50);
    return () => clearTimeout(scrollTimeout);
  }, [messages, runState, isTyping]);

  useEffect(() => {
    if (!initialPrompt) {
      return;
    }
    if (initialPromptRef.current === initialPrompt) {
      return;
    }
    initialPromptRef.current = initialPrompt;
    setInputMessage(initialPrompt);
    handleSendMessage(initialPrompt);
    onInitialPromptConsumed?.();
  }, [handleSendMessage, initialPrompt, onInitialPromptConsumed]);
  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  const formatTimestamp = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'sending':
        return <Icon icon="mdi:clock-outline" className="text-yellow-500 animate-pulse" />;
      case 'sent':
        return <Icon icon="mdi:check" className="text-green-500" />;
      case 'error':
        return <Icon icon="mdi:alert-circle" className="text-red-500" />;
      default:
        return null;
    }
  };

  if (!isOpen) return null;

  return (
    <Sheet open={isOpen} onOpenChange={onToggle}>
      <SheetContent side="right" className="w-full sm:w-[720px] sm:max-w-[55vw] flex flex-col p-0 overflow-hidden">
        <SheetHeader className="px-6 pt-6 pb-4 border-b border-border/50 bg-muted/30 shrink-0">
          <div className="flex items-center justify-between">
            <SheetTitle className="text-lg font-semibold">Azure Architect Chat</SheetTitle>
            <div className="flex items-center gap-2">
              {onOpenIntegrations ? (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2 text-xs h-8"
                  onClick={onOpenIntegrations}
                >
                  <Icon icon="mdi:puzzle" className="text-base" />
                  <span>Agents & Tools</span>
                  <Badge variant={totalIntegrations > 0 ? 'default' : 'secondary'} className="text-[10px]">
                    {totalIntegrations > 0 ? `${totalIntegrations} on` : 'off'}
                  </Badge>
                </Button>
              ) : null}
              <div className="flex rounded-full border border-border/60 overflow-hidden h-8">
                <Button
                  type="button"
                  variant={panelView === 'chat' ? 'default' : 'ghost'}
                  size="sm"
                  className="rounded-none text-xs px-3"
                  onClick={() => setPanelView('chat')}
                >
                  Chat
                </Button>
                <Button
                  type="button"
                  variant={panelView === 'agents' ? 'default' : 'ghost'}
                  size="sm"
                  className="rounded-none text-xs px-3"
                  onClick={() => setPanelView('agents')}
                >
                  Workflow
                </Button>
              </div>
            </div>
          </div>
        </SheetHeader>

      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {panelView === 'agents' ? (
          <ScrollArea className="flex-1 px-6 py-4 overflow-y-auto">
            <div className="space-y-3">
              {agentRunSummaries.length === 0 ? (
                <div className="text-xs text-muted-foreground text-center py-12 px-4">
                  <Icon icon="mdi:robot-outline" className="text-4xl mb-3 opacity-40 mx-auto" />
                  <p className="font-medium">No workflow activity yet</p>
                  <p className="text-[10px] mt-1 opacity-75">Launch a run to see agent reasoning here</p>
                </div>
              ) : (
                <Accordion type="multiple" defaultValue={agentRunSummaries.map((entry) => `${latestRunId}-${entry.agent}`)}>
                  {agentRunSummaries.map((entry) => (
                    <AccordionItem key={`${latestRunId}-${entry.agent}`} value={`${latestRunId}-${entry.agent}`} className="border-0 mb-2">
                      <AccordionTrigger className="px-4 py-3 border border-border/40 rounded-xl bg-background/80 hover:bg-background text-sm font-semibold hover:no-underline shadow-sm">
                        <div className="flex items-center justify-between gap-2">
                          <span className="flex items-center gap-2">
                            <Icon icon="mdi:account-tie" className="text-primary text-base" /> 
                            <span className="truncate">{entry.agent}</span>
                          </span>
                          <Badge variant="outline" className="text-[10px] ml-auto mr-2">{formatTraceTimestamp(entry.ts)}</Badge>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="px-2 pt-2 pb-3">
                        <div className="rounded-xl border border-border/40 bg-muted/20 p-4 text-xs whitespace-pre-wrap leading-relaxed">
                          {entry.text || <span className="italic text-muted-foreground">Awaiting output...</span>}
                        </div>
                        {entry.error ? (
                          <div className="mt-2 text-xs text-red-400 flex items-center gap-1 px-2">
                            <Icon icon="mdi:alert-circle" className="text-sm" /> {entry.error}
                          </div>
                        ) : null}
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              )}
            </div>
          </ScrollArea>
        ) : (
          <ScrollArea ref={scrollAreaRef} className="flex-1 px-6 py-4 overflow-y-auto">
            <div className="space-y-4 pb-4">
            {messages.map((message, messageIndex) => {
            const structuredDiagram = message.meta?.diagram?.structured ?? null;
            const runId = message.meta?.diagram?.runId;
            const reasoningEvents = runId ? traceEventsByRunId[runId] : undefined;
            const showArchitectureActions =
              message.role === 'assistant' &&
              (structuredDiagram || message.meta?.analysisResult || containsArchitecture(message.content));

            // Show agent workflow reasoning between user message and assistant response
            const showAgentWorkflow = message.role === 'user' && 
              messageIndex < messages.length - 1 && 
              messages[messageIndex + 1]?.meta?.diagram?.runId;
            const workflowRunId = showAgentWorkflow ? messages[messageIndex + 1]?.meta?.diagram?.runId : null;
            const workflowEvents = workflowRunId ? traceEventsByRunId[workflowRunId] : undefined;

            return (
              <React.Fragment key={message.id}>
              {/* User messages - keep as-is */}
              {message.role === 'user' && (
                <div className="flex justify-end mb-3">
                  <Card className="max-w-[36%] ml-auto p-4 shadow-sm bg-primary text-primary-foreground rounded-2xl rounded-tr-sm min-w-0">
                    <div className="prose prose-sm dark:prose-invert max-w-[62ch] w-auto whitespace-pre-wrap break-words overflow-x-auto [&_*]:max-w-[62ch] [&_*]:break-words mx-0">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                    </div>
                    <div className="flex items-center justify-between mt-2 text-xs text-primary-foreground/70">
                      <span>{formatTimestamp(message.timestamp)}</span>
                      {getStatusIcon(message.status)}
                    </div>
                  </Card>
                </div>
              )}
              
              {/* Agent messages - show in collapsible accordion */}
              {message.role === 'assistant' && message.meta?.agentName && (
                <div className="flex justify-start mb-3 min-w-0">
                  <Accordion type="single" collapsible defaultValue={message.meta.agentName === 'FinalEditor' ? 'agent-content' : undefined} className="w-full">
                    <AccordionItem value="agent-content" className="border-0">
                      <AccordionTrigger className="px-4 py-3 border border-border/40 rounded-xl bg-muted/40 hover:bg-muted/60 text-sm font-semibold hover:no-underline shadow-sm">
                        <div className="flex items-center justify-between w-full gap-2">
                          <span className="flex items-center gap-2">
                            <Icon icon={message.status === 'sent' ? 'mdi:check-circle' : 'mdi:loading'} className={`text-primary text-base ${message.status === 'streaming' ? 'animate-spin' : ''}`} />
                            <span className="truncate">{message.meta.agentName}</span>
                          </span>
                          <Badge variant="outline" className="text-[10px] ml-auto mr-2">
                            {message.status === 'sent' ? 'completed' : 'streaming'}
                          </Badge>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent className="px-2 pt-2 pb-3 min-w-0">
                        <Card className="p-4 shadow-sm bg-muted/20 rounded-xl min-w-0 ml-0">
                          {/** Collapse very long/system-like prompts by default to avoid exposing full agent guidance in the UI */}
                          {(() => {
                            const content = String(message.content ?? '');
                            const looksLikeSystemPrompt =
                              content.length > 600 && (content.startsWith('You are') || /INSTRUCT|GUIDANCE|STRUCTURED_DIAGRAM|positioning_rules|positioning|SYSTEM PROMPT/i.test(content));
                            const revealed = !!revealedPrompts[message.id];
                            if (looksLikeSystemPrompt && !revealed) {
                              return (
                                <div className="space-y-2">
                                  <div className="rounded-md border border-border/40 bg-muted/10 p-3 text-xs text-muted-foreground max-h-40 overflow-hidden">
                                    {/* Show short excerpt */}
                                    {content.slice(0, 400)}{content.length > 400 ? '...' : ''}
                                  </div>
                                  <div className="flex gap-2">
                                    <Button size="sm" variant="ghost" onClick={() => setRevealedPrompts((s) => ({ ...s, [message.id]: true }))}>
                                      Show full prompt
                                    </Button>
                                    <Button size="sm" variant="outline" onClick={() => {
                                      try { void navigator.clipboard.writeText(content); toast({ title: 'Copied', description: 'Prompt copied to clipboard.' }); } catch (e) { /* ignore */ }
                                    }}>
                                      Copy
                                    </Button>
                                  </div>
                                </div>
                              );
                            }

                            return (
                              <div className="prose prose-sm dark:prose-invert max-w-[62ch] w-auto whitespace-pre-wrap break-words overflow-x-auto [&_*]:max-w-[62ch] [&_*]:break-words mx-0">
                                <TypewriterMarkdown
                                  text={message.content}
                                  speed={8}
                                  className="text-sm text-foreground"
                                  startImmediately={false}
                                />
                              </div>
                            );
                          })()}
                          
                          {/* Visualization buttons for assistant messages with architecture */}
                          {(structuredDiagram || message.meta?.analysisResult || containsArchitecture(message.content)) && (
                            <div className="flex gap-2 mt-3 pt-3 border-t border-border/50">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  const analysis = message.meta?.analysisResult;
                                  if (structuredDiagram) {
                                    visualizeArchitecture(message.content, false, structuredDiagram);
                                    return;
                                  }
                                  if (!analysis) {
                                    visualizeArchitecture(message.content, false);
                                    return;
                                  }

                                  const nameSet = new Set<string>();
                                  (analysis.services || []).forEach((s: string) => nameSet.add(s));
                                  (analysis.connections || []).forEach((c: { from_service?: string; to_service?: string; label?: string }) => {
                                    if (c.from_service) nameSet.add(c.from_service);
                                    if (c.to_service) nameSet.add(c.to_service);
                                  });

                                  const allNames = Array.from(nameSet);
                                  const unmapped: string[] = [];
                                  const servicesArr: AzureService[] = [];
                                  const nameToId = new Map<string, string>();

                                  for (const name of allNames) {
                                    const found = ArchitectureParser.findAzureServiceByName(name);
                                    if (found) {
                                      servicesArr.push(found);
                                      nameToId.set(name, found.id);
                                    } else {
                                      const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
                                      const stub: AzureService = {
                                        id: `ai:${slug}`,
                                        type: `ai.detected/${slug}`,
                                        category: 'AI Detected',
                                        categoryId: 'ai-detected',
                                        title: name,
                                        iconPath: '',
                                        description: 'Detected by AI from diagram',
                                      } as AzureService;
                                      servicesArr.push(stub);
                                      nameToId.set(name, stub.id);
                                      unmapped.push(name);
                                    }
                                  }

                                  const connections = (analysis.connections || []).map((c: { from_service?: string; to_service?: string; label?: string }) => ({
                                    from: nameToId.get(c.from_service || '') || `ai:${(c.from_service || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
                                    to: nameToId.get(c.to_service || '') || `ai:${(c.to_service || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
                                    label: c.label,
                                  }));

                                  const architecture: ParsedArchitecture = {
                                    services: servicesArr,
                                    connections,
                                    layout: servicesArr.length <= 3 ? 'horizontal' : servicesArr.length <= 6 ? 'vertical' : 'grid'
                                  };

                                  const nodes = ArchitectureParser.generateNodes(architecture);
                                  addNodesFromArchitecture(nodes, architecture.connections);
                                  void persistDiagramState();

                                  if (unmapped.length) {
                                    toast({ title: 'Some detected services were unmapped', description: unmapped.slice(0,10).join(', ') });
                                  }
                                }}
                                className="text-xs"
                              >
                                <Icon icon="mdi:diagram-outline" className="mr-1" />
                                Add to<br />Diagram
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  const analysis = message.meta?.analysisResult;
                                  if (structuredDiagram) {
                                    visualizeArchitecture(message.content, true, structuredDiagram);
                                    return;
                                  }
                                  if (!analysis) {
                                    visualizeArchitecture(message.content, true);
                                    return;
                                  }

                                  const nameSet = new Set<string>();
                                  (analysis.services || []).forEach((s: string) => nameSet.add(s));
                                  (analysis.connections || []).forEach((c: { from_service?: string; to_service?: string; label?: string }) => {
                                    if (c.from_service) nameSet.add(c.from_service);
                                    if (c.to_service) nameSet.add(c.to_service);
                                  });

                                  const allNames = Array.from(nameSet);
                                  const unmapped: string[] = [];
                                  const servicesArr: AzureService[] = [];
                                  const nameToId = new Map<string, string>();

                                  for (const name of allNames) {
                                    const found = ArchitectureParser.findAzureServiceByName(name);
                                    if (found) {
                                      servicesArr.push(found);
                                      nameToId.set(name, found.id);
                                    } else {
                                      const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
                                      const stub: AzureService = {
                                        id: `ai:${slug}`,
                                        type: `ai.detected/${slug}`,
                                        category: 'AI Detected',
                                        categoryId: 'ai-detected',
                                        title: name,
                                        iconPath: '',
                                        description: 'Detected by AI from diagram',
                                      } as AzureService;
                                      servicesArr.push(stub);
                                      nameToId.set(name, stub.id);
                                      unmapped.push(name);
                                    }
                                  }

                                  const connections = (analysis.connections || []).map((c: { from_service?: string; to_service?: string; label?: string }) => ({
                                    from: nameToId.get(c.from_service || '') || `ai:${(c.from_service || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
                                    to: nameToId.get(c.to_service || '') || `ai:${(c.to_service || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
                                    label: c.label,
                                  }));

                                  const architecture: ParsedArchitecture = {
                                    services: servicesArr,
                                    connections,
                                    layout: servicesArr.length <= 3 ? 'horizontal' : servicesArr.length <= 6 ? 'vertical' : 'grid'
                                  };

                                  const nodes = ArchitectureParser.generateNodes(architecture);
                                  replaceDiagram(nodes, architecture.connections);
                                  void persistDiagramState();

                                  if (unmapped.length) {
                                    toast({ title: 'Some detected services were unmapped', description: unmapped.slice(0,10).join(', ') });
                                  }
                                }}
                                className="text-xs"
                              >
                                <Icon icon="mdi:refresh" className="mr-1" />
                                Replace<br />Diagram
                              </Button>
                            </div>
                          )}
                        </Card>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                </div>
              )}
              
              {/* Legacy assistant messages without agent name - keep old format */}
              {message.role === 'assistant' && !message.meta?.agentName && (
              <div
                className="flex justify-start mb-3"
              >
                <Card className="w-full p-4 shadow-sm overflow-visible bg-muted/80 rounded-2xl rounded-tl-sm min-w-0">
                  <div className="prose prose-sm dark:prose-invert max-w-[62ch] w-auto whitespace-pre-wrap break-words overflow-x-auto [&_*]:max-w-[62ch] [&_*]:break-words mx-0">
                    <TypewriterMarkdown
                      text={message.content}
                      speed={8}
                      className="text-sm text-foreground"
                      startImmediately={false}
                    />
                  </div>
                  
                          {/* Visualization buttons for assistant messages with architecture */}
                          {(structuredDiagram || message.meta?.analysisResult || containsArchitecture(message.content)) && (
                            <div className="flex gap-2 mt-3 pt-3 border-t border-border/50">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  const analysis = message.meta?.analysisResult;
                                  if (structuredDiagram) {
                                    visualizeArchitecture(message.content, false, structuredDiagram);
                                    return;
                                  }
                                  if (!analysis) {
                                    visualizeArchitecture(message.content, false);
                                    return;
                                  }

                                  const nameSet = new Set<string>();
                                  (analysis.services || []).forEach((s: string) => nameSet.add(s));
                                  (analysis.connections || []).forEach((c: { from_service?: string; to_service?: string; label?: string }) => {
                                    if (c.from_service) nameSet.add(c.from_service);
                                    if (c.to_service) nameSet.add(c.to_service);
                                  });

                                  const allNames = Array.from(nameSet);
                                  const unmapped: string[] = [];
                                  const servicesArr: AzureService[] = [];
                                  const nameToId = new Map<string, string>();

                                  for (const name of allNames) {
                                    const found = ArchitectureParser.findAzureServiceByName(name);
                                    if (found) {
                                      servicesArr.push(found);
                                      nameToId.set(name, found.id);
                                    } else {
                                      const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
                                      const stub: AzureService = {
                                        id: `ai:${slug}`,
                                        type: `ai.detected/${slug}`,
                                        category: 'AI Detected',
                                        categoryId: 'ai-detected',
                                        title: name,
                                        iconPath: '',
                                        description: 'Detected by AI from diagram',
                                      } as AzureService;
                                      servicesArr.push(stub);
                                      nameToId.set(name, stub.id);
                                      unmapped.push(name);
                                    }
                                  }

                                  const connections = (analysis.connections || []).map((c: { from_service?: string; to_service?: string; label?: string }) => ({
                                    from: nameToId.get(c.from_service || '') || `ai:${(c.from_service || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
                                    to: nameToId.get(c.to_service || '') || `ai:${(c.to_service || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
                                    label: c.label,
                                  }));

                                  const architecture: ParsedArchitecture = {
                                    services: servicesArr,
                                    connections,
                                    layout: servicesArr.length <= 3 ? 'horizontal' : servicesArr.length <= 6 ? 'vertical' : 'grid'
                                  };

                                  const nodes = ArchitectureParser.generateNodes(architecture);
                                  addNodesFromArchitecture(nodes, architecture.connections);
                                  void persistDiagramState();

                                  if (unmapped.length) {
                                    toast({ title: 'Some detected services were unmapped', description: unmapped.slice(0,10).join(', ') });
                                  }
                                }}
                                className="text-xs"
                              >
                                <Icon icon="mdi:diagram-outline" className="mr-1" />
                                Add to<br />Diagram
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  const analysis = message.meta?.analysisResult;
                                  if (structuredDiagram) {
                                    visualizeArchitecture(message.content, true, structuredDiagram);
                                    return;
                                  }
                                  if (!analysis) {
                                    visualizeArchitecture(message.content, true);
                                    return;
                                  }

                                  const nameSet = new Set<string>();
                                  (analysis.services || []).forEach((s: string) => nameSet.add(s));
                                  (analysis.connections || []).forEach((c: { from_service?: string; to_service?: string; label?: string }) => {
                                    if (c.from_service) nameSet.add(c.from_service);
                                    if (c.to_service) nameSet.add(c.to_service);
                                  });

                                  const allNames = Array.from(nameSet);
                                  const unmapped: string[] = [];
                                  const servicesArr: AzureService[] = [];
                                  const nameToId = new Map<string, string>();

                                  for (const name of allNames) {
                                    const found = ArchitectureParser.findAzureServiceByName(name);
                                    if (found) {
                                      servicesArr.push(found);
                                      nameToId.set(name, found.id);
                                    } else {
                                      const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
                                      const stub: AzureService = {
                                        id: `ai:${slug}`,
                                        type: `ai.detected/${slug}`,
                                        category: 'AI Detected',
                                        categoryId: 'ai-detected',
                                        title: name,
                                        iconPath: '',
                                        description: 'Detected by AI from diagram',
                                      } as AzureService;
                                      servicesArr.push(stub);
                                      nameToId.set(name, stub.id);
                                      unmapped.push(name);
                                    }
                                  }

                                  const connections = (analysis.connections || []).map((c: { from_service?: string; to_service?: string; label?: string }) => ({
                                    from: nameToId.get(c.from_service || '') || `ai:${(c.from_service || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
                                    to: nameToId.get(c.to_service || '') || `ai:${(c.to_service || '').toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
                                    label: c.label,
                                  }));

                                  const architecture: ParsedArchitecture = {
                                    services: servicesArr,
                                    connections,
                                    layout: servicesArr.length <= 3 ? 'horizontal' : servicesArr.length <= 6 ? 'vertical' : 'grid'
                                  };

                                  const nodes = ArchitectureParser.generateNodes(architecture);
                                  replaceDiagram(nodes, architecture.connections);
                                  void persistDiagramState();

                                  if (unmapped.length) {
                                    toast({ title: 'Some detected services were unmapped', description: unmapped.slice(0,10).join(', ') });
                                  }
                                }}
                                className="text-xs"
                              >
                                <Icon icon="mdi:refresh" className="mr-1" />
                                Replace<br />Diagram
                              </Button>
                            </div>
                          )}
                  
                  <div className="flex items-center justify-between mt-2 text-xs text-muted-foreground">
                    <span>{formatTimestamp(message.timestamp)}</span>
                  </div>
                </Card>
              </div>
              )}
            
            {/* Show agent workflow reasoning inline after user message */}
            {showAgentWorkflow && workflowEvents && workflowEvents.length > 0 && (
              <div className="mb-3 space-y-2">
                <div className="flex items-center gap-2 px-2 py-1 text-[10px] text-muted-foreground uppercase tracking-wide">
                  <Icon icon="mdi:cog-outline" className="text-xs animate-spin" />
                  <span>Agent Workflow</span>
                </div>
                {agentRunSummaries
                  .filter(summary => workflowEvents.some(e => e.agent === summary.agent))
                  .map((summary) => (
                  <div key={`workflow-${workflowRunId}-${summary.agent}`} className="flex justify-start">
                    <Card className="max-w-[85%] p-3 bg-blue-950/20 border-blue-500/30 rounded-xl shadow-sm">
                      <div className="flex items-center gap-2 mb-2">
                        <Icon icon="mdi:account-tie" className="text-blue-400 text-sm" />
                        <span className="text-xs font-semibold text-blue-300">{summary.agent}</span>
                        <Badge variant="outline" className="text-[9px] ml-auto">
                          {summary.phase === 'end' ? 'completed' : summary.phase}
                        </Badge>
                      </div>
                      <div className="text-[11px] text-muted-foreground/80 leading-relaxed">
                        {summary.text ? (
                          <div className="max-h-32 overflow-y-auto">
                            {summary.text.slice(0, 300)}{summary.text.length > 300 ? '...' : ''}
                          </div>
                        ) : (
                          <span className="italic">Processing...</span>
                        )}
                      </div>
                      {summary.error && (
                        <div className="mt-2 text-[10px] text-red-400 flex items-center gap-1">
                          <Icon icon="mdi:alert-circle" className="text-xs" /> {summary.error}
                        </div>
                      )}
                    </Card>
                  </div>
                ))}
              </div>
            )}
            </React.Fragment>
          );
        })}
          
          {isTyping && (
            <div className="flex justify-start mb-3">
              <Card className="bg-muted/80 p-4 rounded-2xl rounded-tl-sm shadow-sm max-w-[85%]">
                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                  <div className="flex gap-1.5">
                    <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '0.15s' }} />
                    <div className="w-2 h-2 bg-primary/60 rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
                  </div>
                  <span className="font-medium">Assistant is thinking...</span>
                </div>
              </Card>
            </div>
          )}
          
          {/* Show active agent workflow when run is in progress */}
          {runState?.status === 'running' && latestRunId && agentRunSummaries.length > 0 && (
            <div className="mb-3">
              <Accordion type="single" collapsible defaultValue="agent-progress" className="w-full max-w-[85%]">
                <AccordionItem value="agent-progress" className="border-0">
                  <AccordionTrigger className="flex items-center gap-2 px-3 py-2 text-[11px] text-blue-400/90 uppercase tracking-wide font-semibold bg-blue-950/20 rounded-lg border border-blue-500/30 hover:bg-blue-950/30 transition-colors">
                    <div className="flex items-center gap-2">
                      <Icon icon="mdi:cog-outline" className="text-sm animate-spin" />
                      <span>Well-Architected Review in Progress</span>
                      <Badge variant="outline" className="text-[9px] ml-2">{agentRunSummaries.length} agents</Badge>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="px-0 pt-2 space-y-2">
                    {agentRunSummaries.map((summary, idx) => {
                      const isActive = summary.phase === 'start' || summary.phase === 'thinking' || summary.phase === 'delta';
                      const isCompleted = summary.phase === 'end';
                      
                      return (
                        <div key={`active-${summary.agent}-${idx}`} className="flex justify-start">
                          <Card className={`max-w-full w-full p-3 rounded-xl shadow-sm transition-all ${
                            isCompleted 
                              ? 'bg-green-950/20 border-green-500/30' 
                              : 'bg-blue-950/30 border-blue-500/40'
                          }`}>
                            <div className="flex items-center gap-2 mb-1">
                              {isActive ? (
                                <Icon icon="mdi:loading" className="text-blue-400 text-sm animate-spin" />
                              ) : isCompleted ? (
                                <Icon icon="mdi:check-circle" className="text-green-400 text-sm" />
                              ) : (
                                <Icon icon="mdi:clock-outline" className="text-muted-foreground text-sm" />
                              )}
                              <span className={`text-xs font-semibold ${
                                isCompleted ? 'text-green-300' : 'text-blue-300'
                              }`}>{summary.agent}</span>
                              <Badge variant="outline" className={`text-[9px] ml-auto ${
                                isActive ? 'animate-pulse' : ''
                              }`}>
                                {isCompleted ? 'completed' : summary.phase}
                              </Badge>
                            </div>
                            {summary.text && (
                              <div className="text-[10px] text-muted-foreground/70 leading-relaxed mt-1.5 line-clamp-2">
                                {summary.text.slice(0, 120)}{summary.text.length > 120 ? '...' : ''}
                              </div>
                            )}
                          </Card>
                        </div>
                      );
                    })}
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </div>
          )}
          </div>
        </ScrollArea>

        )}
      </div>

      <Separator />

      {/* Image Upload Section */}
      {showImageUpload && (
        <div className="px-6 py-4 border-t shrink-0">
                <ImageUpload
                onAnalysisComplete={(result) => {
                  toast({
                    title: "Diagram Analyzed",
                    description: `Found ${result.services.length} services in your diagram!`,
                  });
                  // Push the assistant's analysis description into the chat so users see it
                  // Image analysis completed
                  if (typeof addAssistantMessage === 'function') {
                      // Mark this assistant message as originating from the vision-only image analysis
                      // so the UI can avoid launching agent/team workflows for it.
                      const meta = { analysisResult: result, visionOnly: true };
                      if (result.description) {
                        addAssistantMessage(result.description, meta);
                        toast({ title: 'Assistant message added', description: result.description.slice(0, 200) });
                      } else {
                        const summary = `Analyzed diagram: found ${result.services.length} services.`;
                        addAssistantMessage(summary, meta);
                        toast({ title: 'Assistant message added', description: summary });
                      }
                  } else {
                    console.error('addAssistantMessage is not available on useChat hook');
                  }
                  setShowImageUpload(false);
                }}
                onDiagramUpdated={() => void persistDiagramState()}
          />
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="px-6 py-4 border-t border-border/50 bg-muted/20 shrink-0">
        <div className="flex gap-2 items-end">
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => setShowImageUpload(!showImageUpload)}
            className="shrink-0 h-10 w-10 rounded-full"
            title="Upload diagram image"
          >
            <Icon icon={showImageUpload ? "mdi:close" : "mdi:image-plus"} className="text-lg" />
          </Button>
          <Textarea
            ref={inputRef}
            value={inputMessage}
            onChange={(e) => {
              setInputMessage(e.target.value);
              // Auto-resize textarea
              e.target.style.height = 'auto';
              e.target.style.height = Math.min(e.target.scrollHeight, 200) + 'px';
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage(inputMessage);
              }
            }}
            placeholder="Ask about Azure architecture..."
            className="flex-1 rounded-2xl bg-background/60 border-border/60 focus:border-primary/60 min-h-[80px] max-h-[200px] resize-none py-3 overflow-y-auto custom-scroll"
            disabled={isTyping}
            rows={3}
          />
          <Button
            type="submit"
            size="icon"
            disabled={!inputMessage.trim() || isTyping}
            className="shrink-0 h-10 w-10 rounded-full"
            title="Send message"
          >
            <Icon icon="mdi:send" className="text-lg" />
          </Button>
        </div>
        <div className="text-[10px] text-muted-foreground mt-2 px-1">
          Press Enter to send • Shift+Enter for new line
        </div>
      </form>
      </SheetContent>
    </Sheet>
  );
};

export default ChatPanel;
