import { Icon } from '@iconify/react';
import { Card } from '@/components/ui/card';

interface CanvasLoadingOverlayProps {
  isLoading: boolean;
  message?: string;
}

const agentSteps = [
  'Parsing requirements',
  'Drafting architecture',
  'Running validations',
  'Refining diagram',
];

export const CanvasLoadingOverlay: React.FC<CanvasLoadingOverlayProps> = ({
  isLoading,
  message = 'Generating architecture diagram...',
}) => {
  if (!isLoading) return null;

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <Card className="p-6 sm:p-8 bg-card/95 border border-primary/30 shadow-2xl max-w-lg w-[90%]">
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-3">
            <div className="relative">
              <Icon icon="mdi:cloud-outline" className="text-4xl text-primary/70 animate-pulse" />
              <Icon
                icon="mdi:progress-clock"
                className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-lg text-primary/80 animate-spin-slow"
              />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-foreground">{message}</h3>
              <p className="text-sm text-muted-foreground">
                Agents are collaborating. We’ll apply the diagram automatically when ready.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            {agentSteps.map((step, idx) => (
              <div
                key={step}
                className="flex items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 border border-border/40"
              >
                <div className="w-2.5 h-2.5 rounded-full bg-primary/70 animate-pulse" style={{ animationDelay: `${idx * 0.15}s` }} />
                <span className="text-sm text-foreground">{step}</span>
                <div className="flex-1 h-1 rounded-full bg-primary/15 relative overflow-hidden">
                  <div
                    className="absolute inset-y-0 left-0 bg-primary/50 animate-[shimmer_1.2s_ease_infinite]"
                    style={{ width: '45%' }}
                  />
                </div>
              </div>
            ))}
          </div>

          <style>{`
            @keyframes shimmer {
              0% { transform: translateX(-80%); }
              100% { transform: translateX(220%); }
            }
            .animate-spin-slow { animation: spin 2s linear infinite; }
          `}</style>
        </div>
      </Card>
    </div>
  );
};
