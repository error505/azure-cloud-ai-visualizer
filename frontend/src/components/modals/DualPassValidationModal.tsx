import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Info, 
  Sparkles, 
  Bug,
  Shield,
  DollarSign,
  Activity,
  FileCheck,
  Zap,
  ThumbsUp,
  ThumbsDown
} from 'lucide-react';
import { toast } from 'sonner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';

interface ValidationIssue {
  severity: 'critical' | 'high' | 'medium' | 'low';
  category: 'security' | 'cost' | 'reliability' | 'compliance' | 'performance';
  title: string;
  description: string;
  affected_services: string[];
  recommendation: string;
  auto_fixable: boolean;
}

interface ArchitectProposal {
  diagram: any;
  rationale: string;
  services_count: number;
  estimated_monthly_cost?: number;
  compliance_frameworks: string[];
}

interface CriticReview {
  overall_score: number;
  issues: ValidationIssue[];
  strengths: string[];
  summary: string;
  recommended_changes: any;
}

interface ValidationResult {
  architect_proposal: ArchitectProposal;
  critic_review: CriticReview;
  conflicts: any[];
  final_recommendation: string;
  auto_fix_available: boolean;
}

interface DualPassValidationModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  validationResult: ValidationResult | null;
  onApplyFixes?: (fixes: any) => void;
  onAcceptProposal?: (diagram: any) => void;
}

const severityConfig = {
  critical: { color: 'bg-red-500', icon: XCircle, label: 'Critical' },
  high: { color: 'bg-orange-500', icon: AlertTriangle, label: 'High' },
  medium: { color: 'bg-yellow-500', icon: Info, label: 'Medium' },
  low: { color: 'bg-blue-500', icon: Info, label: 'Low' },
};

const categoryConfig = {
  security: { icon: Shield, label: 'Security', color: 'text-red-400' },
  cost: { icon: DollarSign, label: 'Cost', color: 'text-green-400' },
  reliability: { icon: Activity, label: 'Reliability', color: 'text-blue-400' },
  compliance: { icon: FileCheck, label: 'Compliance', color: 'text-purple-400' },
  performance: { icon: Zap, label: 'Performance', color: 'text-yellow-400' },
};

export const DualPassValidationModal = ({
  open,
  onOpenChange,
  validationResult,
  onApplyFixes,
  onAcceptProposal
}: DualPassValidationModalProps) => {
  const [selectedIssues, setSelectedIssues] = useState<Set<number>>(new Set());
  const [activeTab, setActiveTab] = useState('overview');

  if (!validationResult) return null;

  const { architect_proposal, critic_review, final_recommendation, auto_fix_available } = validationResult;

  const severityCounts = {
    critical: critic_review.issues.filter(i => i.severity === 'critical').length,
    high: critic_review.issues.filter(i => i.severity === 'high').length,
    medium: critic_review.issues.filter(i => i.severity === 'medium').length,
    low: critic_review.issues.filter(i => i.severity === 'low').length,
  };

  const autoFixableCount = critic_review.issues.filter(i => i.auto_fixable).length;

  const handleApplyFixes = () => {
    if (!onApplyFixes) return;
    
    const issuesToFix = Array.from(selectedIssues).map(idx => critic_review.issues[idx]);
    const fixableIssues = issuesToFix.filter(i => i.auto_fixable);
    
    if (fixableIssues.length === 0) {
      toast.error('No fixable issues selected');
      return;
    }

    onApplyFixes(fixableIssues);
    toast.success(`Applying ${fixableIssues.length} automatic fixes...`);
  };

  const handleAcceptProposal = () => {
    if (!onAcceptProposal) return;
    onAcceptProposal(architect_proposal.diagram);
    toast.success('Architecture proposal accepted');
    onOpenChange(false);
  };

  const toggleIssueSelection = (index: number) => {
    const newSelection = new Set(selectedIssues);
    if (newSelection.has(index)) {
      newSelection.delete(index);
    } else {
      newSelection.add(index);
    }
    setSelectedIssues(newSelection);
  };

  const selectAllAutoFixable = () => {
    const autoFixableIndices = new Set(
      critic_review.issues
        .map((issue, idx) => issue.auto_fixable ? idx : -1)
        .filter(idx => idx !== -1)
    );
    setSelectedIssues(autoFixableIndices);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-400" />
            AI Dual-Pass Validation
            <Badge variant={critic_review.overall_score >= 90 ? 'default' : critic_review.overall_score >= 70 ? 'secondary' : 'destructive'}>
              Score: {critic_review.overall_score}/100
            </Badge>
          </DialogTitle>
          <DialogDescription>
            Architecture validated by Architect + Critic agents
          </DialogDescription>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="architect">
              <ThumbsUp className="h-4 w-4 mr-1" />
              Architect
            </TabsTrigger>
            <TabsTrigger value="critic">
              <Bug className="h-4 w-4 mr-1" />
              Critic ({critic_review.issues.length})
            </TabsTrigger>
            <TabsTrigger value="conflicts">
              Conflicts ({validationResult.conflicts.length})
            </TabsTrigger>
          </TabsList>

          <ScrollArea className="flex-1 mt-4">
            <TabsContent value="overview" className="space-y-4 mt-0">
              {/* Score Card */}
              <div className="bg-secondary/20 p-4 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium">Overall Architecture Score</span>
                  <span className="text-2xl font-bold">{critic_review.overall_score}/100</span>
                </div>
                <Progress value={critic_review.overall_score} className="h-2" />
              </div>

              {/* Severity Breakdown */}
              <div className="grid grid-cols-4 gap-3">
                {Object.entries(severityCounts).map(([severity, count]) => {
                  const config = severityConfig[severity as keyof typeof severityConfig];
                  const Icon = config.icon;
                  return (
                    <div key={severity} className="bg-secondary/20 p-3 rounded-lg text-center">
                      <Icon className={`h-5 w-5 mx-auto mb-1 ${config.color}`} />
                      <div className="text-2xl font-bold">{count}</div>
                      <div className="text-xs text-slate-700 dark:text-slate-300">{config.label}</div>
                    </div>
                  );
                })}
              </div>

              {/* Recommendation */}
              <div className="bg-secondary/20 p-4 rounded-lg">
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  {critic_review.overall_score >= 90 ? (
                    <CheckCircle2 className="h-5 w-5 text-green-400" />
                  ) : critic_review.overall_score >= 70 ? (
                    <AlertTriangle className="h-5 w-5 text-yellow-400" />
                  ) : (
                    <XCircle className="h-5 w-5 text-red-400" />
                  )}
                  Final Recommendation
                </h3>
                <div className="text-sm whitespace-pre-wrap">{final_recommendation}</div>
              </div>

              {/* Quick Actions */}
              {auto_fix_available && (
                <div className="bg-purple-500/10 border border-purple-500/20 p-4 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="font-semibold flex items-center gap-2">
                        <Sparkles className="h-4 w-4 text-purple-400" />
                        Auto-Fix Available
                      </h4>
                      <p className="text-sm text-slate-700 dark:text-slate-300 mt-1">
                        {autoFixableCount} issues can be automatically resolved
                      </p>
                    </div>
                    <Button onClick={selectAllAutoFixable} variant="outline" size="sm">
                      Select All Fixable
                    </Button>
                  </div>
                </div>
              )}
            </TabsContent>

            <TabsContent value="architect" className="space-y-4 mt-0">
              <div className="bg-secondary/20 p-4 rounded-lg">
                <h3 className="font-semibold mb-2 flex items-center gap-2">
                  <ThumbsUp className="h-5 w-5 text-blue-400" />
                  Architect's Proposal
                </h3>
                <div className="space-y-3 text-sm">
                  <div>
                    <span className="font-medium">Services:</span> {architect_proposal.services_count}
                  </div>
                  {architect_proposal.estimated_monthly_cost && (
                    <div>
                      <span className="font-medium">Estimated Cost:</span> ${architect_proposal.estimated_monthly_cost.toFixed(2)}/month
                    </div>
                  )}
                  {architect_proposal.compliance_frameworks.length > 0 && (
                    <div>
                      <span className="font-medium">Compliance:</span>{' '}
                      {architect_proposal.compliance_frameworks.map((fw, idx) => (
                        <Badge key={idx} variant="outline" className="ml-1">
                          {fw}
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="bg-secondary/20 p-4 rounded-lg">
                <h4 className="font-semibold mb-2">Design Rationale</h4>
                <p className="text-sm whitespace-pre-wrap">{architect_proposal.rationale}</p>
              </div>
            </TabsContent>

            <TabsContent value="critic" className="space-y-4 mt-0">
              {/* Strengths */}
              {critic_review.strengths.length > 0 && (
                <div className="bg-green-500/10 border border-green-500/20 p-4 rounded-lg">
                  <h4 className="font-semibold mb-2 flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-green-400" />
                    Strengths
                  </h4>
                  <ul className="text-sm space-y-1 list-disc list-inside">
                    {critic_review.strengths.map((strength, idx) => (
                      <li key={idx}>{strength}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Summary */}
              <div className="bg-secondary/20 p-4 rounded-lg">
                <h4 className="font-semibold mb-2">Critic's Summary</h4>
                <p className="text-sm whitespace-pre-wrap">{critic_review.summary}</p>
              </div>

              {/* Issues */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold">Issues Found ({critic_review.issues.length})</h4>
                  {selectedIssues.size > 0 && (
                    <span className="text-sm text-slate-700 dark:text-slate-300">
                      {selectedIssues.size} selected
                    </span>
                  )}
                </div>
                
                {critic_review.issues.map((issue, idx) => {
                  const SeverityIcon = severityConfig[issue.severity].icon;
                  const CategoryIcon = categoryConfig[issue.category].icon;
                  const isSelected = selectedIssues.has(idx);

                  return (
                    <div
                      key={idx}
                      className={`p-4 rounded-lg border-2 transition-all cursor-pointer ${
                        isSelected 
                          ? 'border-purple-500 bg-purple-500/10' 
                          : 'border-secondary bg-secondary/20 hover:border-secondary/60'
                      }`}
                      onClick={() => issue.auto_fixable && toggleIssueSelection(idx)}
                    >
                      <div className="flex items-start gap-3">
                        <SeverityIcon className={`h-5 w-5 ${severityConfig[issue.severity].color} flex-shrink-0 mt-0.5`} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2 mb-1">
                            <h5 className="font-semibold text-sm">{issue.title}</h5>
                            <div className="flex items-center gap-2 flex-shrink-0">
                              <Badge variant="outline" className="text-xs">
                                {severityConfig[issue.severity].label}
                              </Badge>
                              {issue.auto_fixable && (
                                <Badge variant="secondary" className="text-xs">
                                  <Sparkles className="h-3 w-3 mr-1" />
                                  Auto-Fix
                                </Badge>
                              )}
                            </div>
                          </div>
                          
                          <div className="flex items-center gap-2 mb-2">
                            <CategoryIcon className={`h-4 w-4 ${categoryConfig[issue.category].color}`} />
                            <span className="text-xs text-slate-700 dark:text-slate-300">
                              {categoryConfig[issue.category].label}
                            </span>
                          </div>

                          <p className="text-sm mb-2">{issue.description}</p>
                          
                          {issue.affected_services.length > 0 && (
                            <div className="text-xs text-slate-700 dark:text-slate-300 mb-2">
                              Affects: {issue.affected_services.join(', ')}
                            </div>
                          )}

                          <div className="bg-secondary/40 p-2 rounded text-sm">
                            <span className="font-medium">Recommendation:</span> {issue.recommendation}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </TabsContent>

            <TabsContent value="conflicts" className="space-y-4 mt-0">
              {validationResult.conflicts.length === 0 ? (
                <div className="text-center py-8 text-slate-700 dark:text-slate-300">
                  <CheckCircle2 className="h-12 w-12 mx-auto mb-2 text-green-400" />
                  <p>No major conflicts detected</p>
                </div>
              ) : (
                validationResult.conflicts.map((conflict, idx) => (
                  <div key={idx} className="bg-orange-500/10 border border-orange-500/20 p-4 rounded-lg">
                    <h4 className="font-semibold mb-2 flex items-center gap-2">
                      <AlertTriangle className="h-4 w-4 text-orange-400" />
                      {conflict.type?.replace(/_/g, ' ').toUpperCase()}
                    </h4>
                    <pre className="text-sm whitespace-pre-wrap">{JSON.stringify(conflict, null, 2)}</pre>
                  </div>
                ))
              )}
            </TabsContent>
          </ScrollArea>
        </Tabs>

        <Separator className="my-4" />

        <div className="flex items-center justify-between gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          
          <div className="flex items-center gap-3">
            {auto_fix_available && selectedIssues.size > 0 && (
              <Button onClick={handleApplyFixes} variant="default">
                <Sparkles className="h-4 w-4 mr-2" />
                Fix {selectedIssues.size} Issues
              </Button>
            )}
            
            {critic_review.overall_score >= 70 && onAcceptProposal && (
              <Button onClick={handleAcceptProposal} variant="default">
                <CheckCircle2 className="h-4 w-4 mr-2" />
                Accept Proposal
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
