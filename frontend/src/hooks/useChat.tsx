import { useState, useCallback, useRef, useEffect } from 'react';
import type { SupabaseClient } from '@supabase/supabase-js';
import type { IntegrationSettings } from '@/services/projectService';
import {
  getProjectById,
  updateProjectAzureConversationId,
  upsertConversationMessage,
  getConversationHistory,
} from '@/services/projectService';
import { ArchitectureParser, type ParsedArchitecture } from '@/services/architectureParser';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  status?: 'sending' | 'sent' | 'error' | 'streaming';
  meta?: ChatMeta;
}

export type ChatMeta = {
  analysisResult?: {
    services?: string[];
    connections?: { from_service: string; to_service: string; label?: string }[];
    description?: string;
  };
  diagram?: {
    structured?: ParsedArchitecture | null;
    raw?: string | null;
    runId?: string;
  };
  iac?: {
    bicep?: {
      bicep_code?: string;
      parameters?: Record<string, unknown> | null;
      [key: string]: unknown;
    } | null;
    terraform?: {
      terraform_code?: string;
      parameters?: Record<string, unknown> | null;
      [key: string]: unknown;
    } | null;
  };
  agentName?: string; // Track which agent produced this message
  visionOnly?: boolean; // Indicates the message came from vision-only image analysis and should not trigger agent workflows
};

export interface UseChatOptions {
  onError?: (error: Error) => void;
  apiUrl?: string;
  wsUrl?: string;
  supabase?: SupabaseClient;
  projectId?: string;
  teamMode?: boolean;
  integrationSettings?: IntegrationSettings;
}

type RunStatus = 'running' | 'completed';

export interface RunState {
  runId: string;
  status: RunStatus;
  startedAt: Date;
  completedAt?: Date;
}

interface DiagramUpdate {
  messageId: string;
  runId?: string;
  architecture: ParsedArchitecture | null;
  raw?: string | null;
  messageText: string;
  receivedAt: Date;
  iac?: ChatMeta['iac'];
}

export interface TraceEventRecord {
  runId: string;
  stepId: string;
  agent: string;
  phase: string;
  ts: number;
  meta: Record<string, unknown>;
  progress: Record<string, unknown>;
  telemetry: Record<string, unknown>;
  messageDelta?: string | null;
  summary?: string | null;
  error?: string | null;
}

const GREETING_MESSAGE =
  "Hello! I'm your Azure Architect AI assistant. I can help you design cloud architectures, generate Infrastructure as Code, and analyze your diagrams. How can I assist you today?";
const RECENT_CONTEXT_LIMIT = 8;

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const buildSummary = (history: ChatMessage[]) => {
  const recent = history.slice(-RECENT_CONTEXT_LIMIT);
  const summary = recent
    .map((msg) => {
      const speaker = msg.role === 'assistant' ? 'Assistant' : msg.role === 'user' ? 'User' : 'System';
      return `${speaker}: ${msg.content}`;
    })
    .join('\n');

  return {
    summary,
    recent_messages: recent.map((msg) => ({
      role: msg.role,
      content: msg.content,
    })),
  };
};

export const useChat = (options: UseChatOptions = {}) => {
  const {
    onError,
    apiUrl = 'http://localhost:8000/api/chat',
    wsUrl = 'ws://localhost:8000/ws/chat',
    supabase,
    projectId,
    teamMode = true,
    integrationSettings,
  } = options;

  const createGreetingMessage = useCallback(
    (): ChatMessage => ({
      id: 'greeting',
      role: 'assistant',
      content: GREETING_MESSAGE,
      timestamp: new Date(),
      status: 'sent',
    }),
    []
  );

  const [messages, setMessages] = useState<ChatMessage[]>([createGreetingMessage()]);
  const [isConnected, setIsConnected] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const connectingRef = useRef<Promise<void> | null>(null);
  const [azureConversationId, setAzureConversationId] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState | null>(null);
  const [latestDiagram, setLatestDiagram] = useState<DiagramUpdate | null>(null);
  const [traceEventsByRunId, setTraceEventsByRunId] = useState<Record<string, TraceEventRecord[]>>({});
  const streamingMessageIdsRef = useRef<Map<string, string>>(new Map());
  const lastUserMessageRef = useRef<string | null>(null);

  const persistMessage = useCallback(
    async (message: ChatMessage, explicitConversationId?: string | null) => {
      if (!supabase || !projectId) {
        return;
      }
      try {
        const runId = message.meta?.diagram?.runId ?? null;
        const traceEvents = runId ? traceEventsByRunId[runId] : null;
        const agentName = message.meta?.agentName ?? null;
        
        await upsertConversationMessage(supabase, {
          projectId,
          role: message.role,
          content: message.content,
          azureConversationId: explicitConversationId ?? azureConversationId,
          runId,
          traceEvents: traceEvents as unknown as Record<string, unknown>[] ?? null,
          agentName,
        });
      } catch (error) {
        console.error('Failed to persist conversation message', error);
      }
    },
    [azureConversationId, projectId, supabase, traceEventsByRunId]
  );

  const syncAzureConversationId = useCallback(
    async (incomingId: string) => {
      if (!supabase || !projectId) {
        return;
      }
      try {
        await updateProjectAzureConversationId(supabase, projectId, incomingId);
        await supabase
          .from('conversations')
          .update({ azure_conversation_id: incomingId })
          .eq('project_id', projectId)
          .is('azure_conversation_id', null);
      } catch (error) {
        console.error('Failed to sync Azure conversation id', error);
      }
    },
    [projectId, supabase]
  );

  const handleSocketMessage = useCallback(
    (event: MessageEvent<string>) => {
      try {
        const data = JSON.parse(event.data) as Record<string, unknown>;
        const type = typeof data.type === 'string' ? data.type : undefined;

        if (type === 'message') {
          const content = typeof data.content === 'string' ? data.content : '';
          const assistantMessage: ChatMessage = {
            id: Date.now().toString(),
            role: 'assistant',
            content,
            timestamp: new Date(),
            status: 'sent',
          };
          setMessages((prev) => [...prev, assistantMessage]);
          void persistMessage(assistantMessage, azureConversationId);
          setIsTyping(false);

          // Heuristic: if the assistant content contains a Diagram JSON block, surface it for the canvas.
          if (content.includes('"services"') && content.includes('"groups"')) {
            try {
              const jsonMatch = content.match(/```json\\s*({[\\s\\S]*?})\\s*```/i);
              const rawJson = jsonMatch ? jsonMatch[1] : content;
              const parsed = JSON.parse(rawJson);
              setLatestDiagram({
                messageId: assistantMessage.id,
                architecture: ArchitectureParser.parseStructuredDiagram(parsed),
                raw: rawJson,
                messageText: content,
                receivedAt: new Date(),
              });
            } catch (err) {
              console.warn('[useChat] Failed to parse inline diagram JSON', err);
            }
          }
          return;
        }

        if (type === 'typing') {
          setIsTyping(Boolean(data.typing));
          return;
        }

        if (type === 'run_started') {
          const runId = typeof data.run_id === 'string' ? data.run_id : undefined;
          if (runId) {
            setRunState({ runId, status: 'running', startedAt: new Date() });
            setIsTyping(true);
            setTraceEventsByRunId((prev) => ({ ...prev, [runId]: [] }));
          }
          return;
        }

        if (type === 'trace_event') {
          const runId = typeof data.run_id === 'string' ? data.run_id : undefined;
          if (runId) {
            setRunState((prev) => {
              if (!prev || prev.runId !== runId) {
                return { runId, status: 'running', startedAt: new Date() };
              }
              return prev;
            });
            const tsValue =
              typeof data.ts === 'number'
                ? data.ts
                : typeof data.ts === 'string'
                  ? Number(data.ts) || Date.now() / 1000
                  : Date.now() / 1000;
            const eventPayload: TraceEventRecord = {
              runId,
              stepId:
                typeof data.step_id === 'string'
                  ? data.step_id
                  : data.step_id !== undefined
                    ? String(data.step_id)
                    : '0',
              agent: typeof data.agent === 'string' ? data.agent : 'Agent',
              phase: typeof data.phase === 'string' ? data.phase : 'delta',
              ts: tsValue,
              meta: isPlainObject(data.meta) ? (data.meta as Record<string, unknown>) : {},
              progress: isPlainObject(data.progress) ? (data.progress as Record<string, unknown>) : {},
              telemetry: isPlainObject(data.telemetry)
                ? (data.telemetry as Record<string, unknown>)
                : {},
              messageDelta: typeof data.message_delta === 'string' ? data.message_delta : undefined,
              summary: typeof data.summary === 'string' ? data.summary : undefined,
              error: typeof data.error === 'string' ? data.error : undefined,
            };
            setTraceEventsByRunId((prev) => {
              const nextEvents = [...(prev[runId] ?? [])];
              const duplicate = nextEvents.find(
                (entry) => entry.stepId === eventPayload.stepId && entry.phase === eventPayload.phase && entry.ts === eventPayload.ts
              );
              if (!duplicate) {
                nextEvents.push(eventPayload);
                nextEvents.sort((a, b) => a.ts - b.ts);
              }
              return { ...prev, [runId]: nextEvents };
            });
          }
          return;
        }

        if (type === 'agent_stream') {
          const runId = typeof data.run_id === 'string' ? data.run_id : undefined;
          const agent = typeof data.agent === 'string' ? data.agent : undefined;
          const chunk = typeof data.message_delta === 'string' ? data.message_delta : '';
          const phase = typeof data.phase === 'string' ? data.phase : 'delta';
          if (!runId || !agent) {
            return;
          }
          
          // Don't accumulate "thinking" messages into content - they're just progress indicators
          const isThinkingMessage = phase === 'thinking' || chunk.includes('[') && chunk.includes('is analyzing and reasoning');
          
          // Show typing indicator when agent is working
          if (phase === 'start' || phase === 'thinking' || (phase === 'delta' && chunk)) {
            setIsTyping(true);
          }
          
          setMessages((prev) => {
            // Use runId + agent name to track individual agent messages
            const agentKey = `${runId}-${agent}`;
            const existingId = streamingMessageIdsRef.current.get(agentKey);
            
            // Start a new streaming message for this agent if none exists
            if (!existingId) {
              const newId = `agent-${agentKey}-${Date.now()}`;
              streamingMessageIdsRef.current.set(agentKey, newId);
              const newMsg: ChatMessage = {
                id: newId,
                role: 'assistant',
                content: isThinkingMessage ? '' : chunk,
                timestamp: new Date(),
                status: 'streaming',
                meta: {
                  diagram: {
                    structured: null,
                    raw: null,
                    runId,
                  },
                  agentName: agent, // Store agent name in metadata
                },
              };
              return [...prev, newMsg];
            }
            
            // Accumulate deltas in this agent's message (skip thinking messages)
            return prev.map((msg) => {
              if (msg.id !== existingId) {
                return msg;
              }
              const updatedContent = (chunk && !isThinkingMessage) ? `${msg.content || ''}${chunk}` : msg.content;
              
              const updated: ChatMessage = {
                ...msg,
                content: updatedContent,
                // Mark as 'sent' when this agent finishes
                status: phase === 'end' ? 'sent' : phase === 'error' ? 'error' : 'streaming',
                timestamp: new Date(),
              };
              
              // Persist when this agent completes
              if (phase === 'end') {
                streamingMessageIdsRef.current.delete(agentKey);
                void persistMessage(updated);
              }
              return updated;
            });
          });
          
          // Clear on error
          if (phase === 'error') {
            streamingMessageIdsRef.current.delete(`${runId}-${agent}`);
            setIsTyping(false);
          }
          
          // Turn off typing when any agent ends (will turn back on when next agent starts)
          if (phase === 'end') {
            setIsTyping(false);
          }
          return;
        }

        if (type === 'team_final') {
          const messageText = typeof data.message === 'string' ? data.message : '';
          const runId = typeof data.run_id === 'string' ? data.run_id : undefined;
          const rawDiagram = typeof data.diagram_raw === 'string' ? data.diagram_raw : undefined;
          const diagramPayload = data.diagram;
          const iacPayloadRaw = data.iac;

          let structuredDiagram: ParsedArchitecture | null = null;
          if (diagramPayload && typeof diagramPayload === 'object') {
            try {
              structuredDiagram = ArchitectureParser.parseStructuredDiagram(diagramPayload) ?? null;
            } catch (error) {
              console.warn('[useChat] Failed to interpret structured diagram payload object', error);
            }
          }

          if (!structuredDiagram && rawDiagram) {
            try {
              const parsedRaw = JSON.parse(rawDiagram);
              structuredDiagram = ArchitectureParser.parseStructuredDiagram(parsedRaw) ?? null;
            } catch (error) {
              console.warn('[useChat] Failed to parse raw diagram JSON string', error);
            }
          }

          if (!structuredDiagram && diagramPayload && typeof diagramPayload === 'string') {
            try {
              const parsedPayload = JSON.parse(diagramPayload);
              structuredDiagram = ArchitectureParser.parseStructuredDiagram(parsedPayload) ?? null;
            } catch (error) {
              console.warn('[useChat] Failed to parse string diagram payload', error);
            }
          }

          let iacPayload: ChatMeta['iac'] | undefined;
          if (iacPayloadRaw && typeof iacPayloadRaw === 'object') {
            const rawBicep = (iacPayloadRaw as Record<string, unknown>).bicep;
            const rawTerraform = (iacPayloadRaw as Record<string, unknown>).terraform;
            const bicep =
              rawBicep && typeof rawBicep === 'object'
                ? (rawBicep as Record<string, unknown>)
                : undefined;
            const terraform =
              rawTerraform && typeof rawTerraform === 'object'
                ? (rawTerraform as Record<string, unknown>)
                : undefined;
            if (bicep || terraform) {
              iacPayload = {
                bicep: bicep as ChatMeta['iac']['bicep'],
                terraform: terraform as ChatMeta['iac']['terraform'],
              };
            }
          }

          const metaPayload =
            structuredDiagram || rawDiagram || iacPayload
              ? {
                  diagram: {
                    structured: structuredDiagram,
                    raw: rawDiagram ?? null,
                    runId,
                  },
                  iac: iacPayload,
                }
              : undefined;
          
          // Check if we have agent messages from streaming - if so, don't create a new message
          const hasAgentMessages = runId && Array.from(streamingMessageIdsRef.current.keys()).some(key => 
            key.startsWith(`${runId}-`)
          );
          
          const existingStreamId = runId ? streamingMessageIdsRef.current.get(runId) : undefined;
          const fallbackMessageId = (Date.now() + 1).toString();
          const targetMessageId = existingStreamId ?? fallbackMessageId;
          let finalAssistantMessage: ChatMessage | null = null;

          setMessages((prev) => {
            const patched = prev.map((msg) =>
              msg.id === lastUserMessageRef.current ? { ...msg, status: 'sent' as const } : msg
            );
            
            // If we have agent messages from streaming, don't create a duplicate team_final message
            if (hasAgentMessages) {
              // Just mark the user message as sent
              return patched;
            }
            
            if (existingStreamId) {
              return patched.map((msg) => {
                if (msg.id !== existingStreamId) {
                  return msg;
                }
                // Preserve accumulated content from streaming; only update metadata
                const updated: ChatMessage = {
                  ...msg,
                  content: msg.content || messageText,
                  status: 'sent',
                  timestamp: new Date(),
                  meta: metaPayload ?? msg.meta,
                };
                finalAssistantMessage = updated;
                return updated;
              });
            }
            const assistantMessage: ChatMessage = {
              id: fallbackMessageId,
              role: 'assistant',
              content: messageText || 'No response received',
              timestamp: new Date(),
              status: 'sent',
              meta: metaPayload,
            };
            finalAssistantMessage = assistantMessage;
            return [...patched, assistantMessage];
          });
          if (runId) {
            streamingMessageIdsRef.current.delete(runId);
          }
          if (finalAssistantMessage) {
            void persistMessage(finalAssistantMessage);
          }
          lastUserMessageRef.current = null;
          setIsTyping(false);
          if (runId) {
            setRunState((prev) =>
              prev && prev.runId === runId ? { ...prev, status: 'completed', completedAt: new Date() } : prev
            );
          }
          if (!structuredDiagram) {
            console.warn('[team_final] ⚠️ No structured diagram in team_final', { hasRaw: !!rawDiagram, hasPayload: !!diagramPayload });
          }
          setLatestDiagram({
            messageId: targetMessageId,
            runId,
            architecture: structuredDiagram,
            raw: rawDiagram ?? null,
            messageText,
            receivedAt: new Date(),
            iac: iacPayload,
          });
          return;
        }

        if (type === 'run_completed') {
          const runId = typeof data.run_id === 'string' ? data.run_id : undefined;
          if (runId) {
            setRunState((prev) =>
              prev && prev.runId === runId ? { ...prev, status: 'completed', completedAt: new Date() } : prev
            );
            streamingMessageIdsRef.current.delete(runId);
          }
          setIsTyping(false);
          return;
        }

        if (type === 'error') {
          const errorMessage = typeof data.message === 'string' ? data.message : 'Unknown error';
          console.error('WebSocket error message:', errorMessage);
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === lastUserMessageRef.current ? { ...msg, status: 'error' as const } : msg
            )
          );
          setIsTyping(false);
          onError?.(new Error(errorMessage));
          lastUserMessageRef.current = null;
          setRunState((prev) => (prev ? { ...prev, status: 'completed', completedAt: new Date() } : prev));
        }
      } catch (err) {
        console.error('Failed to parse WebSocket message:', err);
      }
    },
    [onError, persistMessage, azureConversationId]
  );

  const connectWebSocket = useCallback(async () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      setIsConnected(true);
      return;
    }

    if (connectingRef.current) {
      return connectingRef.current;
    }

    // Attempting to connect to WebSocket
    connectingRef.current = new Promise<void>((resolve, reject) => {
      try {
        const socket = new WebSocket(wsUrl);
        wsRef.current = socket;

        socket.onopen = () => {
          setIsConnected(true);
          connectingRef.current = null;
          resolve();
        };

        socket.onmessage = (event) => handleSocketMessage(event as MessageEvent<string>);

        socket.onerror = (error) => {
          console.error('⚠ WebSocket error details:', {
            error,
            readyState: socket.readyState,
            url: wsUrl,
            protocols: socket.protocol,
          });
          setIsConnected(false);
          if (socket.readyState !== WebSocket.OPEN) {
            connectingRef.current = null;
            reject(new Error('WebSocket connection failed'));
          }
        };

        socket.onclose = (event) => {
          setIsConnected(false);
          connectingRef.current = null;
        };
      } catch (error) {
        console.error('⚠ Failed to create WebSocket:', error);
        connectingRef.current = null;
        setIsConnected(false);
        reject(error as Error);
      }
    });

    return connectingRef.current;
  }, [handleSocketMessage, wsUrl]);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    connectingRef.current = null;
    setIsConnected(false);
    setRunState(null);
    streamingMessageIdsRef.current.clear();
  }, []);

  const sendMessage = useCallback(
    async (content: string, opts?: { useTeam?: boolean }) => {
      if (!content.trim()) {
        return;
      }

      const trimmed = content.trim();
      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: trimmed,
        timestamp: new Date(),
        status: 'sending',
      };

      setMessages((prev) => [...prev, userMessage]);
      void persistMessage(userMessage, azureConversationId);
      setIsTyping(true);
      lastUserMessageRef.current = userMessage.id;

      const contextSummary = buildSummary([...messages, userMessage]);
      const enrichedContext = {
        ...contextSummary,
        azure_conversation_id: azureConversationId ?? undefined,
        integration_settings: integrationSettings ?? undefined,
      };

      const useTeamPath = opts?.useTeam ?? teamMode;
      if (useTeamPath) {
        try {
          await connectWebSocket();
          const payload: Record<string, unknown> = {
            type: 'team_stream_chat',
            message: trimmed,
            conversation_id: azureConversationId ?? undefined,
            context: enrichedContext,
          };
          wsRef.current?.send(JSON.stringify(payload));
          return;
        } catch (error) {
          console.warn('Falling back to REST API after WebSocket failure', error);
        }
      }

        try {
        const targetUrl = projectId ? `${apiUrl}?project_id=${encodeURIComponent(projectId)}` : apiUrl;
        const conversationHistory = [...messages, userMessage].map((msg) => ({
          role: msg.role,
          content: msg.content,
        }));
        setRunState(null);

        const response = await fetch(targetUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            message: trimmed,
            conversation_id: azureConversationId ?? undefined,
            conversation_history: conversationHistory,
            context: enrichedContext,
          }),
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.error('API Error:', response.status, errorText);
          throw new Error('Failed to send message');
        }

        const data = await response.json();

        const resolvedConversationId =
          (typeof data.conversation_id === 'string' && data.conversation_id) || azureConversationId;

        if (resolvedConversationId && resolvedConversationId !== azureConversationId) {
          setAzureConversationId(resolvedConversationId);
          void syncAzureConversationId(resolvedConversationId);
        }

        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: data.message?.content || data.response || data.message || 'No response received',
          timestamp: new Date(),
          status: 'sent',
        };

        setMessages((prev) => [
          ...prev.map((msg) => (msg.id === userMessage.id ? { ...msg, status: 'sent' as const } : msg)),
          assistantMessage,
        ]);
        void persistMessage(assistantMessage, resolvedConversationId);
        setIsTyping(false);
        lastUserMessageRef.current = null;
      } catch (error) {
        console.error('Error sending message:', error);
        setMessages((prev) =>
          prev.map((msg) => (msg.id === userMessage.id ? { ...msg, status: 'error' } : msg))
        );
        setIsTyping(false);
        onError?.(error as Error);
        lastUserMessageRef.current = null;
      }
    },
    [
      apiUrl,
      azureConversationId,
      connectWebSocket,
      messages,
      onError,
      persistMessage,
      projectId,
      syncAzureConversationId,
      teamMode,
      integrationSettings,
    ]
  );

  const clearMessages = useCallback(() => {
    setMessages([createGreetingMessage()]);
    setAzureConversationId(null);
    setLatestDiagram(null);
    streamingMessageIdsRef.current.clear();
  }, [createGreetingMessage]);

  const addAssistantMessage = useCallback(
    (content: string, meta?: ChatMeta) => {
      if (!content) return;
      const msg: ChatMessage = {
        id: Date.now().toString(),
        role: 'assistant',
        content,
        timestamp: new Date(),
        status: 'sent',
        meta,
      };
      setMessages((prev) => [...prev, msg]);
      // If this assistant message is from vision-only analysis, do NOT persist
      // it to the backend conversation store. Persisting can trigger downstream
      // automation (agent/team runs) based on DB events; avoid that for image
      // uploads which should remain vision-only.
      if (!meta || !meta.visionOnly) {
        void persistMessage(msg, azureConversationId);
      }
    },
    [persistMessage, azureConversationId]
  );

  useEffect(() => {
    if (!supabase || !projectId) {
      setAzureConversationId(null);
      setMessages([createGreetingMessage()]);
      return;
    }

    let isCurrent = true;
    const loadConversation = async () => {
      try {
        const [projectResult, conversationRows] = await Promise.all([
          getProjectById(supabase, projectId).catch((error) => {
            console.error('Failed to load project for chat', error);
            return null;
          }),
          getConversationHistory(supabase, projectId).catch((error) => {
            console.error('Failed to load conversation history', error);
            return [];
          }),
        ]);

        if (!isCurrent) return;

        if (projectResult?.azure_conversation_id) {
          setAzureConversationId(projectResult.azure_conversation_id);
        }

        const rows = conversationRows as Array<{
          id: string;
          role: 'user' | 'assistant' | 'system';
          content: string;
          created_at: string;
          run_id: string | null;
          trace_events: Record<string, unknown>[] | null;
          agent_name: string | null;
        }>;

        // Load trace events into state (grouped by runId)
        const tracesByRun: Record<string, TraceEventRecord[]> = {};
        for (const row of rows) {
          if (row.run_id && row.trace_events && Array.isArray(row.trace_events)) {
            tracesByRun[row.run_id] = row.trace_events as unknown as TraceEventRecord[];
          }
        }
        if (Object.keys(tracesByRun).length > 0) {
          setTraceEventsByRunId(tracesByRun);
        }

        if (rows.length === 0) {
          setMessages([createGreetingMessage()]);
          return;
        }

        // Restore messages with agentName from database
        const restored = rows.map((row) => {
          const base: ChatMessage = {
            id: row.id ?? crypto.randomUUID(),
            role: row.role,
            content: row.content ?? '',
            timestamp: row.created_at ? new Date(row.created_at) : new Date(),
            status: 'sent' as const,
            meta: row.run_id
              ? {
                  diagram: {
                    structured: null,
                    raw: null,
                    runId: row.run_id,
                  },
                  agentName: row.agent_name ?? undefined,
                }
              : undefined,
          };

          return base;
        });

        setMessages(restored);
      } catch (error) {
        console.error('Unexpected error loading conversation history', error);
        setMessages([createGreetingMessage()]);
      }
    };

    void loadConversation();

    return () => {
      isCurrent = false;
    };
  }, [createGreetingMessage, projectId, supabase]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      connectingRef.current = null;
    };
  }, []);

  return {
    messages,
    isConnected,
    isTyping,
    sendMessage,
    connectWebSocket,
    disconnect,
    clearMessages,
    addAssistantMessage,
    runState,
    latestDiagram,
    traceEventsByRunId,
  };
};
