// src/components/RunProgress.tsx
import React, { useEffect, useMemo, useState } from "react";
import { Icon } from "@iconify/react";
import { ScrollArea } from "@/components/ui/scroll-area";
import TypewriterMarkdown from "@/components/ui/TypewriterMarkdown";

type TracePhase = "start" | "delta" | "end" | "error";

type TraceEventPayload = {
  run_id: string;
  step_id: string;
  agent: string;
  phase: TracePhase;
  ts: number;
  progress: { current: number; total: number };
  meta?: Record<string, unknown>;
  message_delta?: string;
  summary?: string;
  error?: string;
};

type StepStatus = "pending" | "running" | "done" | "error";

type StepState = {
  agent: string;
  status: StepStatus;
  text: string[];
  summary?: string;
  lastUpdated?: number;
};

const STATUS_META: Record<StepStatus, { icon: string; color: string; dot: string; label: string }> = {
  pending: {
    icon: "mdi:clock-outline",
    color: "text-muted-foreground",
    dot: "bg-muted-foreground/30",
    label: "waiting",
  },
  running: {
    icon: "mdi:progress-clock",
    color: "text-sky-400",
    dot: "bg-sky-400",
    label: "running",
  },
  done: {
    icon: "mdi:check-circle-outline",
    color: "text-emerald-500",
    dot: "bg-emerald-500",
    label: "complete",
  },
  error: {
    icon: "mdi:alert-circle",
    color: "text-red-500",
    dot: "bg-red-500",
    label: "error",
  },
};

export default function RunProgress({ runId }: { runId: string }) {
  const [events, setEvents] = useState<TraceEventPayload[]>([]);
  const [steps, setSteps] = useState<Record<string, StepState>>({});

  useEffect(() => {
    setEvents([]);
    setSteps({});
    const es = new EventSource(`/api/runs/${runId}/events`);
    es.onmessage = (event) => {
      const payload: TraceEventPayload = JSON.parse(event.data);
      setEvents((prev) => [...prev, payload]);
      setSteps((previous) => {
        const next = { ...previous };
        const key = payload.step_id;
        const existing =
          next[key] ?? { agent: payload.agent, status: "pending" as StepStatus, text: [], summary: undefined };
        const text = payload.message_delta
          ? [...existing.text, payload.message_delta]
          : payload.error
          ? [...existing.text, payload.error]
          : existing.text;
        let status = existing.status;
        if (payload.phase === "start") status = "running";
        if (payload.phase === "delta") status = status === "pending" ? "running" : status;
        if (payload.phase === "end") status = "done";
        if (payload.phase === "error") status = "error";
        next[key] = {
          agent: payload.agent,
          status,
          text,
          summary: payload.summary ?? existing.summary,
          lastUpdated: payload.ts ?? existing.lastUpdated,
        };
        return next;
      });
    };
    es.onerror = () => es.close();
    return () => es.close();
  }, [runId]);

  const stepOrder = useMemo(() => {
    const order: string[] = [];
    for (const event of events) {
      if (!order.includes(event.step_id)) {
        order.push(event.step_id);
      }
    }
    return order;
  }, [events]);

  const groupedEvents = useMemo(() => {
    const map: Record<string, TraceEventPayload[]> = {};
    events.forEach((event) => {
      if (!map[event.step_id]) {
        map[event.step_id] = [];
      }
      map[event.step_id].push(event);
    });
    return map;
  }, [events]);

  const progressPercent = useMemo(() => {
    const lastEvent = events.at(-1);
    if (!lastEvent || !lastEvent.progress?.total) {
      return 0;
    }
    const { current, total } = lastEvent.progress;
    if (!total) {
      return 0;
    }
    return Math.min(100, Math.max(0, Math.round((current / total) * 100)));
  }, [events]);

  return (
    <div className="p-4 space-y-3">
      <div>
        <div className="flex items-center justify-between text-xs uppercase tracking-wide text-muted-foreground mb-1">
          <span>Agent Workflow</span>
          <span>{progressPercent}%</span>
        </div>
        <div className="w-full rounded bg-muted/40">
          <div
            className="h-2 rounded bg-gradient-to-r from-sky-300 via-sky-400 to-blue-500 transition-all"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
      </div>
      <ScrollArea className="relative max-h-[28rem] pr-3">
        <div className="relative pl-4">
          <div className="absolute left-1 top-2 bottom-2 w-px bg-border/60" aria-hidden />
          {stepOrder.map((id) => {
          const state = steps[id];
          if (!state) {
            return null;
          }
          const statusMeta = STATUS_META[state.status];
          const eventsForStep = groupedEvents[id] ?? [];
          const combinedText = state.text.join("").trim();
          const hasDetails = combinedText.length > 0;
          const timestamp =
            state.lastUpdated !== undefined
              ? new Date(state.lastUpdated).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : null;

          return (
            <div key={id} className="relative pl-6 pb-4 last:pb-0">
              <div className={`absolute left-[-4px] top-3 h-2 w-2 rounded-full ${statusMeta.dot}`} aria-hidden />
              <div className="rounded-xl border border-border/40 bg-background/60 p-3 shadow-sm transition-shadow hover:shadow-md hover:shadow-primary/10">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                      <Icon icon={statusMeta.icon} className={`${statusMeta.color} text-lg`} />
                      <span>
                        Step {id}: {state.agent}
                      </span>
                    </div>
                    <div className="mt-1 text-xs uppercase tracking-wide text-muted-foreground">
                      {statusMeta.label}
                      {timestamp ? ` • ${timestamp}` : ""}
                    </div>
                  </div>
                  {state.summary && (
                    <div className="text-xs text-muted-foreground max-w-[55%] text-right whitespace-pre-wrap">
                      {state.summary}
                    </div>
                  )}
                </div>

                {hasDetails && (
                  <details className="mt-3 group text-sm text-muted-foreground">
                    <summary className="cursor-pointer select-none text-xs uppercase tracking-wide text-muted-foreground/80 group-open:text-foreground/80">
                      View agent output
                    </summary>
                    <ScrollArea className="mt-2 max-h-48 rounded-md bg-muted/30 p-3 text-xs leading-relaxed text-muted-foreground">
                      <TypewriterMarkdown text={combinedText} speed={6} />
                    </ScrollArea>
                  </details>
                )}

                {eventsForStep.length > 0 && (
                  <ScrollArea className="mt-3 max-h-40 pr-1">
                    <div className="space-y-1 text-xs text-muted-foreground/90">
                      {eventsForStep.map((event, idx) => (
                        <div key={`${event.step_id}-${idx}`} className="flex items-start gap-2">
                          <span className="mt-[2px] h-1.5 w-1.5 rounded-full bg-primary/40 flex-shrink-0" />
                          <div className="flex-1 leading-relaxed">
                            <span className="font-medium text-foreground/80">{event.phase}</span>
                            {event.summary ? ` – ${event.summary}` : ""}
                            {event.message_delta && (
                              <TypewriterMarkdown
                                text={event.message_delta.trim()}
                                speed={8}
                                className="text-muted-foreground text-[13px]"
                              />
                            )}
                            {event.error && (
                              <span className="block text-destructive whitespace-pre-wrap">{event.error.trim()}</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                )}
              </div>
            </div>
          );
        })}
        </div>
      </ScrollArea>
    </div>
  );
}
