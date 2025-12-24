/**
 * MigrationPanel Component
 * 
 * Displays migration plan from AWS/GCP to Azure:
 * - Service mappings with cost comparisons
 * - Overall cost savings summary
 * - Risk assessment and recommendations
 * - Bicep code snippets for migrated resources
 */

import React, { useState, useCallback, useMemo } from 'react';
import { useDiagramStore } from '@/store/diagramStore';
import { 
  ArrowRight, 
  DollarSign, 
  AlertTriangle, 
  CheckCircle, 
  ChevronDown, 
  ChevronRight,
  Code,
  Copy,
  Check,
  Loader2,
  Cloud,
  TrendingDown,
  TrendingUp,
  Minus,
  FileCode,
  X
} from 'lucide-react';
import type { MigrationResult, MigrationMapping, Severity } from '@/types/infra';
import { formatCurrency, formatSavingsPercent, getSeverityColor } from '@/types/infra';

interface MigrationPlanResponse {
  success: boolean;
  source_provider: string;
  target_provider: string;
  source_nodes: Array<{ id: string; service_type: string; label: string; category?: string }>;
  target_nodes: Array<{ id: string; service_type: string; label: string; category?: string; resource_type?: string }>;
  mappings: Array<{
    source_node_id: string;
    source_service: string;
    target_service: string;
    target_resource_type: string;
    source_monthly_cost?: number;
    target_monthly_cost?: number;
    cost_delta?: number;
    migration_complexity?: string;
    migration_notes?: string;
    risks?: string[];
  }>;
  source_monthly_total: number;
  target_monthly_total: number;
  total_savings: number;
  savings_percent?: number;
  cost_summary_markdown?: string;
  overall_complexity: string;
  key_risks: string[];
  recommendations: string[];
  unmapped_services: Array<{ node_id: string; aws_service?: string; gcp_service?: string; reason: string }>;
  bicep_snippets: Array<{ aws_service?: string; gcp_service?: string; azure_service: string; snippet: string }>;
}

interface MigrationPanelProps {
  isOpen: boolean;
  projectId?: string;
  onMigrationComplete?: (result: MigrationPlanResponse) => void;
  onClose?: () => void;
}

const PROVIDER_INFO = {
  aws: { label: 'Amazon Web Services', icon: '🔶', color: 'text-orange-400' },
  gcp: { label: 'Google Cloud Platform', icon: '🔴', color: 'text-red-400' },
  azure: { label: 'Microsoft Azure', icon: '☁️', color: 'text-blue-400' },
};

export function MigrationPanel({ 
  isOpen,
  projectId, 
  onMigrationComplete,
  onClose 
}: MigrationPanelProps) {
  const nodes = useDiagramStore((state) => state.nodes);
  const edges = useDiagramStore((state) => state.edges);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MigrationPlanResponse | null>(null);
  const [expandedMappings, setExpandedMappings] = useState<Set<string>>(new Set());
  const [expandedSnippets, setExpandedSnippets] = useState<Set<string>>(new Set());
  const [copiedSnippet, setCopiedSnippet] = useState<string | null>(null);
  const [sourceProvider, setSourceProvider] = useState<'aws' | 'gcp'>('aws');

  // Detect source provider from current diagram nodes
  const detectSourceProvider = useCallback((): 'aws' | 'gcp' => {
    for (const node of nodes) {
      const data = node.data as Record<string, unknown>;
      const label = (data?.label as string || '').toLowerCase();
      const serviceType = (data?.serviceType as string || '').toLowerCase();
      
      // Check for AWS patterns
      if (label.includes('ec2') || label.includes('s3') || label.includes('lambda') || 
          serviceType.includes('aws') || label.includes('rds') || label.includes('dynamodb')) {
        return 'aws';
      }
      // Check for GCP patterns
      if (label.includes('compute engine') || label.includes('cloud storage') || 
          label.includes('cloud functions') || serviceType.includes('gcp') || 
          label.includes('bigquery') || label.includes('gke')) {
        return 'gcp';
      }
    }
    return 'aws'; // Default to AWS
  }, [nodes]);

  // Build diagram from current store state
  const getDiagram = useCallback(() => {
    return { nodes, edges };
  }, [nodes, edges]);

  const runMigration = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const detectedProvider = detectSourceProvider();
      setSourceProvider(detectedProvider);
      const diagram = getDiagram();
      
      // Use AI-powered migration endpoint
      const response = await fetch('/api/migration/ai-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          source_provider: detectedProvider,
          target_provider: 'azure',
          diagram,
        }),
      });
      
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || response.statusText);
      }
      
      const data: MigrationPlanResponse = await response.json();
      setResult(data);
      onMigrationComplete?.(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Migration failed');
    } finally {
      setLoading(false);
    }
  }, [projectId, detectSourceProvider, getDiagram, onMigrationComplete]);

  const toggleMapping = useCallback((id: string) => {
    setExpandedMappings(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const toggleSnippet = useCallback((id: string) => {
    setExpandedSnippets(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const copySnippet = useCallback(async (id: string, code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedSnippet(id);
      setTimeout(() => setCopiedSnippet(null), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  }, []);

  const savingsDisplay = useMemo(() => {
    if (!result) return null;
    const savings = result.total_savings;
    if (savings > 0) {
      return { icon: TrendingDown, color: 'text-green-400', label: 'Savings' };
    } else if (savings < 0) {
      return { icon: TrendingUp, color: 'text-red-400', label: 'Additional Cost' };
    }
    return { icon: Minus, color: 'text-slate-400', label: 'No Change' };
  }, [result]);

  const sourceInfo = PROVIDER_INFO[sourceProvider];

  // Don't render if not open - must be after all hooks
  if (!isOpen) return null;

  return (
    <div className="bg-slate-800 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-slate-700 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Cloud className="w-6 h-6 text-blue-400" />
          <div>
            <h2 className="text-lg font-semibold text-white">Cloud Migration Planner</h2>
            <p className="text-sm text-slate-400">
              {sourceInfo.icon} {sourceInfo.label} → ☁️ Microsoft Azure
            </p>
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} className="p-2 hover:bg-slate-700 rounded-lg">
            <X className="w-5 h-5 text-slate-400" />
          </button>
        )}
      </div>

      <div className="p-4 space-y-4">
        {/* Run Migration Button (if no result yet) */}
        {!result && !loading && (
          <div className="text-center py-8">
            <p className="text-slate-400 mb-4">
              Analyze your {sourceInfo.label} architecture and generate a migration plan to Azure
            </p>
            <button
              onClick={runMigration}
              disabled={loading}
              className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors"
            >
              Generate Migration Plan
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="text-center py-8">
            <Loader2 className="w-8 h-8 text-blue-400 animate-spin mx-auto mb-4" />
            <p className="text-slate-300">Analyzing architecture and generating migration plan...</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <div>
              <p className="text-red-400 font-medium">Migration Failed</p>
              <p className="text-red-300/80 text-sm">{error}</p>
            </div>
          </div>
        )}

        {/* Results */}
        {result && (
          <>
            {/* Cost Summary */}
            <div className="bg-slate-700/50 rounded-lg p-4">
              <h3 className="text-white font-medium mb-3 flex items-center gap-2">
                <DollarSign className="w-5 h-5 text-green-400" />
                Cost Analysis
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 bg-slate-800 rounded-lg">
                  <p className="text-xs text-slate-400 mb-1">{sourceInfo.label}</p>
                  <p className="text-xl font-bold text-white">
                    {formatCurrency(result.source_monthly_total)}
                  </p>
                  <p className="text-xs text-slate-500">/month</p>
                </div>
                <div className="text-center p-3 bg-slate-800 rounded-lg">
                  <p className="text-xs text-slate-400 mb-1">Azure</p>
                  <p className="text-xl font-bold text-white">
                    {formatCurrency(result.target_monthly_total)}
                  </p>
                  <p className="text-xs text-slate-500">/month</p>
                </div>
                <div className="text-center p-3 bg-slate-800 rounded-lg">
                  <p className="text-xs text-slate-400 mb-1">{savingsDisplay?.label}</p>
                  <p className={`text-xl font-bold ${savingsDisplay?.color}`}>
                    {formatCurrency(Math.abs(result.total_savings))}
                  </p>
                  {result.savings_percent !== undefined && (
                    <p className={`text-xs ${savingsDisplay?.color}`}>
                      {formatSavingsPercent(result.savings_percent)}
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* Service Mappings */}
            <div className="bg-slate-700/50 rounded-lg p-4">
              <h3 className="text-white font-medium mb-3">
                Service Mappings ({result.mappings.length})
              </h3>
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {result.mappings.map((mapping, idx) => {
                  const isExpanded = expandedMappings.has(mapping.source_node_id);
                  return (
                    <div key={idx} className="bg-slate-800 rounded-lg overflow-hidden">
                      <button
                        onClick={() => toggleMapping(mapping.source_node_id)}
                        className="w-full p-3 flex items-center justify-between hover:bg-slate-700/50"
                      >
                        <div className="flex items-center gap-3">
                          <span className={sourceInfo.color}>{mapping.source_service}</span>
                          <ArrowRight className="w-4 h-4 text-slate-500" />
                          <span className="text-blue-400">{mapping.target_service}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          {mapping.cost_delta !== undefined && (
                            <span className={mapping.cost_delta <= 0 ? 'text-green-400' : 'text-red-400'}>
                              {mapping.cost_delta <= 0 ? '-' : '+'}${Math.abs(mapping.cost_delta).toFixed(0)}/mo
                            </span>
                          )}
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-slate-400" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-slate-400" />
                          )}
                        </div>
                      </button>
                      {isExpanded && (
                        <div className="px-3 pb-3 text-sm">
                          <div className="grid grid-cols-2 gap-2 text-slate-400">
                            <div>Resource Type: <span className="text-slate-300">{mapping.target_resource_type}</span></div>
                            <div>Complexity: <span className="text-slate-300">{mapping.migration_complexity || 'Medium'}</span></div>
                            {mapping.source_monthly_cost !== undefined && (
                              <div>Source Cost: <span className="text-slate-300">${mapping.source_monthly_cost}/mo</span></div>
                            )}
                            {mapping.target_monthly_cost !== undefined && (
                              <div>Target Cost: <span className="text-slate-300">${mapping.target_monthly_cost}/mo</span></div>
                            )}
                          </div>
                          {mapping.migration_notes && (
                            <p className="mt-2 text-slate-400">{mapping.migration_notes}</p>
                          )}
                          {mapping.risks && mapping.risks.length > 0 && (
                            <div className="mt-2">
                              <span className="text-yellow-400 text-xs font-medium">Risks:</span>
                              <ul className="text-xs text-slate-400 mt-1">
                                {mapping.risks.map((risk, i) => (
                                  <li key={i}>• {risk}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Unmapped Services */}
            {result.unmapped_services.length > 0 && (
              <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
                <h3 className="text-yellow-400 font-medium mb-2 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5" />
                  Unmapped Services ({result.unmapped_services.length})
                </h3>
                <ul className="text-sm text-yellow-300/80 space-y-1">
                  {result.unmapped_services.map((svc, idx) => (
                    <li key={idx}>
                      • {svc.aws_service || svc.gcp_service || svc.node_id}: {svc.reason}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Recommendations */}
            {result.recommendations.length > 0 && (
              <div className="bg-slate-700/50 rounded-lg p-4">
                <h3 className="text-white font-medium mb-2 flex items-center gap-2">
                  <CheckCircle className="w-5 h-5 text-green-400" />
                  Recommendations
                </h3>
                <ul className="text-sm text-slate-300 space-y-1">
                  {result.recommendations.map((rec, idx) => (
                    <li key={idx}>• {rec}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Bicep Snippets */}
            {result.bicep_snippets.length > 0 && (
              <div className="bg-slate-700/50 rounded-lg p-4">
                <h3 className="text-white font-medium mb-3 flex items-center gap-2">
                  <FileCode className="w-5 h-5 text-cyan-400" />
                  Bicep Templates ({result.bicep_snippets.length})
                </h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {result.bicep_snippets.map((snippet, idx) => {
                    const snippetId = `snippet-${idx}`;
                    const isExpanded = expandedSnippets.has(snippetId);
                    return (
                      <div key={idx} className="bg-slate-800 rounded-lg overflow-hidden">
                        <button
                          onClick={() => toggleSnippet(snippetId)}
                          className="w-full p-3 flex items-center justify-between hover:bg-slate-700/50"
                        >
                          <div className="flex items-center gap-2">
                            <Code className="w-4 h-4 text-cyan-400" />
                            <span className="text-white">{snippet.azure_service}</span>
                            <span className="text-xs text-slate-500">
                              (from {snippet.aws_service || snippet.gcp_service})
                            </span>
                          </div>
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-slate-400" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-slate-400" />
                          )}
                        </button>
                        {isExpanded && (
                          <div className="relative">
                            <button
                              onClick={() => copySnippet(snippetId, snippet.snippet)}
                              className="absolute top-2 right-2 p-1.5 bg-slate-700 hover:bg-slate-600 rounded"
                            >
                              {copiedSnippet === snippetId ? (
                                <Check className="w-4 h-4 text-green-400" />
                              ) : (
                                <Copy className="w-4 h-4 text-slate-400" />
                              )}
                            </button>
                            <pre className="p-3 text-xs text-slate-300 overflow-x-auto bg-slate-900">
                              <code>{snippet.snippet}</code>
                            </pre>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Re-run Button */}
            <div className="flex justify-end">
              <button
                onClick={runMigration}
                disabled={loading}
                className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors"
              >
                Regenerate Plan
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default MigrationPanel;
