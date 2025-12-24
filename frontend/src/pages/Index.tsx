import { useEffect, useMemo, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '@iconify/react';
import ParticleBackground from '@/components/ParticleBackground';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useSupabase } from '@/context/SupabaseContext';
import { supabaseClient } from '@/lib/supabaseClient';
import {
  createProjectWithPrompt,
  listRecentProjects,
  ProjectRecord,
  DEFAULT_INTEGRATION_SETTINGS,
  type IntegrationSettings,
} from '@/services/projectService';
import { DiagramImagePayload } from '@/types/diagramUpload';
import IntegrationMarketplace from '@/components/layout/IntegrationMarketplace';

const gradientBackground =
  'bg-[radial-gradient(circle_at_20%_-10%,rgba(76,106,255,0.45),transparent_55%),radial-gradient(circle_at_80%_0,rgba(236,72,153,0.35),transparent_60%),radial-gradient(circle_at_50%_80%,rgba(14,165,233,0.35),transparent_70%)]';

const featurePrompts = [
  'Design a secure Azure landing zone for a fintech startup',
  'Generate an event-driven architecture with Event Grid and Functions',
  'Create a real-time analytics pipeline using Synapse and Stream Analytics',
];

type McpKey = 'bicep' | 'terraform' | 'docs';

const Index = () => {
  const navigate = useNavigate();
  const { user, signInWithProvider, signOut, isReady, supabaseAvailable } = useSupabase();
  const supabaseEnabled = supabaseAvailable;
  const [prompt, setPrompt] = useState('');
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState<string | null>(null);
  const [diagramImagePayload, setDiagramImagePayload] = useState<DiagramImagePayload | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [isLoadingProjects, setIsLoadingProjects] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [displayPlaceholder, setDisplayPlaceholder] = useState("");
  const placeholderText = "Ask the agent to design your Azure architecture...";
  const [integrationSettings, setIntegrationSettings] = useState<IntegrationSettings>(DEFAULT_INTEGRATION_SETTINGS);
  const [isIntegrationModalOpen, setIsIntegrationModalOpen] = useState(false);

  const integrationSnapshot = useMemo<IntegrationSettings>(() => ({
    mcp: {
      bicep: Boolean(integrationSettings.mcp?.bicep),
      terraform: Boolean(integrationSettings.mcp?.terraform),
      docs: Boolean(integrationSettings.mcp?.docs),
    },
    agents: {
      architect: Boolean(integrationSettings.agents?.architect ?? true),
      security: Boolean(integrationSettings.agents?.security),
      reliability: Boolean(integrationSettings.agents?.reliability),
      cost: Boolean(integrationSettings.agents?.cost),
      networking: Boolean(integrationSettings.agents?.networking),
      observability: Boolean(integrationSettings.agents?.observability),
      dataStorage: Boolean(integrationSettings.agents?.dataStorage),
      compliance: Boolean(integrationSettings.agents?.compliance),
      identity: Boolean(integrationSettings.agents?.identity),
      naming: Boolean(integrationSettings.agents?.naming),
    },
  }), [integrationSettings]);

  const enabledMcpCount = useMemo(
    () => Object.values(integrationSnapshot.mcp ?? {}).filter(Boolean).length,
    [integrationSnapshot]
  );

  const enabledAgentsCount = useMemo(
    () => {
      const agents = integrationSnapshot.agents ?? {};
      // Don't count architect since it's always enabled
      return Object.entries(agents).filter(([key, value]) => key !== 'architect' && value).length;
    },
    [integrationSnapshot]
  );

  const totalIntegrations = enabledMcpCount + enabledAgentsCount;


  useEffect(() => {
    if (!coverPreview) {
      return;
    }
    return () => {
      URL.revokeObjectURL(coverPreview);
    };
  }, [coverPreview]);

  useEffect(() => {
    if (!supabaseClient || !isReady || !supabaseAvailable) {
      return;
    }
    setIsLoadingProjects(true);
    listRecentProjects(supabaseClient, user?.id ?? null)
      .then((data) => {
        setProjects(data);
        setErrorMessage(null);
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : 'Failed to load projects';
        setErrorMessage(msg);
      })
      .finally(() => setIsLoadingProjects(false));
  }, [isReady, supabaseAvailable, user?.id]);

  const handleSelectFile = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setCoverFile(file);
    setCoverPreview(URL.createObjectURL(file));
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = typeof reader.result === 'string' ? reader.result : '';
      setDiagramImagePayload({
        name: file.name,
        type: file.type,
        dataUrl: result,
      });
    };
    reader.readAsDataURL(file);
  };

  const handlePromptSelect = (value: string) => {
    setPrompt(value);
  };

  const startWorkspace = async () => {
    const trimmedPrompt = prompt.trim();
    const hasPrompt = trimmedPrompt.length > 0;
    const hasDiagram = Boolean(diagramImagePayload);
    if (!hasPrompt && !hasDiagram) {
      setErrorMessage('Please provide a prompt or attach a diagram image to analyze.');
      return;
    }
    const shouldDefaultPrompt = hasPrompt;
    // When only an image is provided, avoid auto-sending a prompt that triggers agents; let vision handle it.
    const effectivePrompt = shouldDefaultPrompt ? trimmedPrompt : '';
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      let createdProjectId: string | undefined;

      if (supabaseClient && isReady && supabaseAvailable) {
        const record = await createProjectWithPrompt(supabaseClient, {
          prompt: effectivePrompt,
          userId: user?.id ?? null,
          title: effectivePrompt.slice(0, 80),
          coverFile,
          integrationSettings: integrationSnapshot,
        });
        createdProjectId = record.id;
      }

      let diagramImageKey: string | undefined;
      if (diagramImagePayload) {
        const key = `diagram-upload:${crypto.randomUUID()}`;
        try {
          sessionStorage.setItem(key, JSON.stringify(diagramImagePayload));
          diagramImageKey = key;
        } catch (err) {
          console.warn('[Index] Failed to buffer diagram image payload', err);
        }
      }

      navigate(createdProjectId ? `/app/${createdProjectId}` : '/app', {
        state: {
          initialPrompt: effectivePrompt,
          projectId: createdProjectId,
          openChat: hasPrompt || hasDiagram,
          diagramImageKey,
          integrationSettings: integrationSnapshot,
        },
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start project';
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const startBlankWorkspace = () => {
    // Navigate to the app workspace without an initial prompt so users can start drawing
    navigate('/app', {
      state: {
        initialPrompt: '',
        projectId: undefined,
        openChat: false,
        integrationSettings: integrationSnapshot,
      },
    });
  };

  const handleIntegrationToggle = useCallback((key: string, value: boolean, type?: 'mcp' | 'agent') => {
    setIntegrationSettings((prev) => {
      if (type === 'agent') {
        const nextAgents = {
          architect: prev.agents?.architect ?? DEFAULT_INTEGRATION_SETTINGS.agents?.architect ?? true,
          security: prev.agents?.security ?? DEFAULT_INTEGRATION_SETTINGS.agents?.security ?? false,
          reliability: prev.agents?.reliability ?? DEFAULT_INTEGRATION_SETTINGS.agents?.reliability ?? false,
          cost: prev.agents?.cost ?? DEFAULT_INTEGRATION_SETTINGS.agents?.cost ?? false,
          networking: prev.agents?.networking ?? DEFAULT_INTEGRATION_SETTINGS.agents?.networking ?? false,
          observability: prev.agents?.observability ?? DEFAULT_INTEGRATION_SETTINGS.agents?.observability ?? false,
          dataStorage: prev.agents?.dataStorage ?? DEFAULT_INTEGRATION_SETTINGS.agents?.dataStorage ?? false,
          compliance: prev.agents?.compliance ?? DEFAULT_INTEGRATION_SETTINGS.agents?.compliance ?? false,
          identity: prev.agents?.identity ?? DEFAULT_INTEGRATION_SETTINGS.agents?.identity ?? false,
          naming: prev.agents?.naming ?? DEFAULT_INTEGRATION_SETTINGS.agents?.naming ?? false,
        };
        (nextAgents as Record<string, boolean>)[key] = value;
        return { ...prev, agents: nextAgents };
      } else {
        const nextMcp = {
          bicep: prev.mcp?.bicep ?? DEFAULT_INTEGRATION_SETTINGS.mcp?.bicep ?? false,
          terraform: prev.mcp?.terraform ?? DEFAULT_INTEGRATION_SETTINGS.mcp?.terraform ?? false,
          docs: prev.mcp?.docs ?? DEFAULT_INTEGRATION_SETTINGS.mcp?.docs ?? false,
        };
        (nextMcp as Record<string, boolean>)[key] = value;
        return { ...prev, mcp: nextMcp };
      }
    });
  }, []);
  useEffect(() => {
    const text = placeholderText;
    let active = true;
    let index = 0;
    const timers: number[] = [];

    const type = () => {
      if (!active) return;
      setDisplayPlaceholder(text.slice(0, index));
      if (index >= text.length) {
        timers.push(
          window.setTimeout(() => {
            index = 0;
            type();
          }, 1800)
        );
      } else {
        index += 1;
        timers.push(window.setTimeout(type, 55));
      }
    };

    type();

    return () => {
      active = false;
      timers.forEach((id) => window.clearTimeout(id));
    };
  }, [placeholderText]);
  const projectCards = useMemo(() => {
    if (isLoadingProjects) {
      return (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, idx) => (
            <Card key={`skeleton-${idx}`} className="p-4 bg-white/5 border-white/10 backdrop-blur-sm">
              <Skeleton className="h-40 w-full rounded-lg" />
              <Skeleton className="h-4 w-3/4 mt-4" />
              <Skeleton className="h-3 w-1/2 mt-2" />
            </Card>
          ))}
        </div>
      );
    }

    if (!projects.length) {
      return (
        <div className="rounded-3xl border border-white/10 bg-black/40 p-10 text-center text-sm text-white/70">
          {supabaseEnabled
            ? 'Projects you start will appear here — sign in and prompt the architect to begin.'
            : 'Configure Supabase to see saved projects, or start prompting to open the workspace instantly.'}
        </div>
      );
    }

    return (
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {projects.map((project) => (
          <Card
            key={project.id}
            className="group cursor-pointer overflow-hidden border border-white/10 bg-white/5 backdrop-blur transition hover:border-white/40 hover:bg-white/10"
            onClick={() =>
              navigate(`/app/${project.id}`, {
                state: { projectId: project.id, openChat: true },
              })
            }
          >
            <div className="relative h-40 overflow-hidden">
              {project.cover_url ? (
                <img
                  src={project.cover_url}
                  alt={project.title}
                  className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
                />
              ) : (
                <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-blue-500/30 to-purple-500/30 text-white/60">
                  <Icon icon="mdi:vector-polyline-edit" className="text-4xl" />
                </div>
              )}
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-4">
                <p className="text-sm font-semibold text-white">{project.title}</p>
                <p className="text-xs text-white/70">
                  {new Date(project.updated_at).toLocaleString()}
                </p>
              </div>
            </div>
          </Card>
        ))}
      </div>
    );
  }, [isLoadingProjects, navigate, projects, supabaseEnabled]);

  return (
    <div className={`relative min-h-screen overflow-hidden bg-[#070b19] text-white ${gradientBackground}`}>
      <ParticleBackground />
      <div className="absolute inset-0 bg-gradient-to-b from-[#080b19]/95 via-[#0f1732]/85 to-[#03040c]/95" />
      <div className="absolute inset-0 mix-blend-screen opacity-80 bg-[radial-gradient(circle_at_0%_0%,rgba(90,128,255,0.35),transparent_55%)]" />
      <div className="absolute inset-0 mix-blend-overlay opacity-70 bg-[radial-gradient(circle_at_80%_100%,rgba(236,72,153,0.25),transparent_65%)]" />

      <div className="relative z-10">
        <header className="flex items-center justify-between px-8 py-6">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="Cloud Visualizer Pro" className="h-9 w-9 rounded-xl border border-white/20 bg-white/10 p-1" />
            <div>
              <p className="text-lg font-semibold tracking-tight">Cloud Visualizer Pro</p>
              <p className="text-xs uppercase tracking-[0.28em] text-white/50">Prompt-first architecture</p>
            </div>
          </div>

          <nav className="hidden gap-6 text-sm text-white/70 lg:flex">
            <button type="button" className="transition hover:text-white">
              Community
            </button>
            <button type="button" className="transition hover:text-white">
              Docs
            </button>
            <button type="button" className="transition hover:text-white">
              Pricing
            </button>
            <button type="button" className="transition hover:text-white">
              Enterprise
            </button>
          </nav>

          <div className="flex items-center gap-3">
            {supabaseEnabled ? (
              isReady && user ? (
                <>
                  <div className="hidden items-center gap-2 rounded-full border border-white/10 bg-white/10 px-4 py-1 text-sm text-white/80 md:flex">
                    <Icon icon="mdi:account" />
                    <span>{user.email ?? 'Signed in'}</span>
                  </div>
                  <Button variant="ghost" className="text-white" onClick={() => signOut()}>
                    Sign out
                  </Button>
                </>
              ) : (
                <Button
                  variant="secondary"
                  className="bg-white text-black hover:bg-white/90"
                  onClick={() => signInWithProvider('github')}
                >
                  <Icon icon="mdi:github" className="mr-2 text-lg" />
                  Sign in with GitHub
                </Button>
              )
            ) : (
              <Badge variant="secondary" className="bg-white/20 text-white/80">
                Supabase disabled
              </Badge>
            )}
            <Button variant="ghost" className="hidden text-white/70 hover:text-white md:inline-flex">
              Product Updates
            </Button>
          </div>
        </header>

        <main className="px-6 pb-24 pt-16 sm:px-10">
          <div className="mx-auto max-w-4xl text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-4 py-1 text-sm text-white/80 backdrop-blur">
              <Icon icon="mdi:rocket-launch" className="text-lg text-blue-300" />
              Introducing Agent-native drafting
            </div>
            <h2 className="text-4xl md:text-6xl font-semibold tracking-tight">
              Build something           
              <img
                src="/logo.png"
                alt="Agent Canvas logo"
                className="inline-block h-16 w-16 rounded-2xl  p-1 object-contain mb-2"
              />
              <span className="text-primary">smart</span>
            </h2>
            <p className="mt-4 text-lg text-white/70 sm:text-xl">
              Create Azure Architectures and IaC only by chatting with AI
            </p>
          </div>

          <section className="mx-auto mt-12 max-w-3xl">
            <div className="mx-auto mt-10 w-full max-w-3xl rounded-3xl bg-black/40 backdrop-blur border border-white/10 px-6 py-6 shadow-[0_40px_120px_-40px_rgba(56,189,248,.3)]">
              <div className="flex items-center justify-between gap-4 border-b border-white/10 pb-4">
                <div className="flex items-center gap-2 text-sm text-white/60">
                  <Icon icon="mdi:pen" />
                  Prompt the architect
                </div>
                <div className="flex items-center gap-2 text-xs text-white/50">
                  <Badge variant="secondary" className="bg-green-400/20 text-green-200">
                    {supabaseEnabled ? (
                      <span className="inline-flex items-center gap-2">
                        <img src="/supabase-logo.svg" alt="Supabase" className="h-4 w-4" />
                        <span>Supabase synced</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        <img src="/supabase.svg" alt="Local session" className="h-4 w-4 opacity-50" />
                        <span>Local session</span>
                      </span>
                    )}
                  </Badge>
                  <Badge variant="secondary" className="bg-white/20 text-white/70">
                    {user ? 'Workspace linked' : 'Guest mode'}
                  </Badge>
                </div>
              </div>

              <Textarea
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                placeholder={displayPlaceholder}
                className="mt-4 h-28 resize-none border-none bg-white/5 text-base text-white placeholder:text-white/40 focus-visible:ring-0"
              />

              {/* <div className="mt-3 flex flex-wrap gap-2">
                {featurePrompts.map((sample) => (
                  <Button
                    key={sample}
                    type="button"
                    variant="secondary"
                    className="rounded-full bg-white/10 px-4 py-2 text-xs text-white/80 hover:bg-white/20"
                    onClick={() => handlePromptSelect(sample)}
                  >
                    {sample}
                  </Button>
                ))}
              </div> */}

              {errorMessage && (
                <div className="mt-3 text-sm text-red-300">
                  <Icon icon="mdi:alert" className="mr-1 inline text-base align-text-bottom" />
                  {errorMessage}
                </div>
              )}

              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-wrap items-center gap-2 text-sm text-white/60">
                  <Button variant="outline" className="border-white/30 bg-white/10 text-white hover:bg-white/30" onClick={handleSelectFile}>
                    <Icon icon="mdi:image-plus" className="mr-2" />
                    {coverFile ? 'Change diagram' : 'Attach diagram'}
                  </Button>
                  <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChange} />
                  {coverPreview && (
                    <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-white/70">
                      <Icon icon="mdi:check-circle" className="text-green-300" />
                      Diagram attached
                    </div>
                  )}
                  {/* <Badge variant="secondary" className="bg-white/15 text-white/70">
                      <span className="inline-flex items-center gap-2">
                        <img src="/supabase-logo.svg" alt="Supabase" className="h-4 w-4" />
                        <span>Supabase</span>
                      </span>
                  </Badge> */}
                  <Button
                    variant="ghost"
                    className="hidden md:inline-flex text-white/80 hover:text-white"
                    onClick={startBlankWorkspace}
                    disabled={isSubmitting}
                  >
                    Start blank canvas
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    className="flex items-center gap-2 text-white/70 hover:text-white"
                    onClick={() => setIsIntegrationModalOpen(true)}
                  >
                    <Icon icon="mdi:puzzle" className="text-lg" />
                    Agents & Tools
                    {totalIntegrations > 0 ? (
                      <Badge variant="secondary" className="bg-primary/20 text-primary">
                        {totalIntegrations}
                      </Badge>
                    ) : null}
                  </Button>
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    size="lg"
                    className="flex items-center gap-2 rounded-full bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 px-6 py-2 text-white shadow-lg shadow-purple-500/30 transition hover:shadow-purple-500/60"
                    onClick={startWorkspace}
                    disabled={isSubmitting}
                  >
                  {isSubmitting ? (
                    <>
                      <Icon icon="mdi:loading" className="animate-spin text-lg" />
                      Generating workspace...
                    </>
                  ) : (
                    <>
                      <Icon icon="mdi:send" className="text-lg" />
                      Open canvas
                    </>
                  )}
                </Button>
              </div>

              <IntegrationMarketplace
                open={isIntegrationModalOpen}
                onOpenChange={setIsIntegrationModalOpen}
                settings={integrationSnapshot}
                onToggle={(key, value, type) => handleIntegrationToggle(key, value, type)}
                isSaving={false}
                disabled={false}
                projectId={undefined}
              />
            </div>
          </div>
          </section>

          <section className="mx-auto mt-16 max-w-6xl">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-semibold text-white">Your recent projects</h2>
              <Button variant="ghost" className="text-sm text-white/70 hover:text-white">
                View all
              </Button>
            </div>
            <p className="mt-1 text-sm text-white/60">
              Projects persist to Supabase with conversation history so you can resume designing anytime.
            </p>

            <div className="mt-6">{projectCards}</div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default Index;
