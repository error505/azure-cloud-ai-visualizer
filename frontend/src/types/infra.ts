/**
 * InfraGraph TypeScript Types
 * 
 * TypeScript equivalents of the backend Pydantic models for:
 * - Multi-cloud infrastructure representation
 * - Migration planning
 * - Compliance analysis
 * - Cost optimization
 */

// -----------------------------------------------------------------------------
// Enums
// -----------------------------------------------------------------------------

export type CloudProvider = 'azure' | 'aws' | 'gcp' | 'mixed';

export type EdgeType = 'network' | 'data' | 'dependency' | 'identity' | 'contains';

export type FixType = 'compliance' | 'cost' | 'security' | 'performance' | 'migration';

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

// -----------------------------------------------------------------------------
// Core InfraGraph Types
// -----------------------------------------------------------------------------

export interface InfraNode {
  id: string;
  provider: CloudProvider;
  service_type: string;
  label: string;
  
  // Resource identification
  resource_id?: string;
  resource_type?: string;
  
  // Hierarchy
  parent_id?: string;
  region?: string;
  
  // Metadata
  tags: Record<string, string>;
  properties: Record<string, unknown>;
  
  // Visual properties
  icon_path?: string;
  category?: string;
  
  // Original data
  raw_data?: Record<string, unknown>;
}

export interface InfraEdge {
  id?: string;
  source: string;
  target: string;
  edge_type: EdgeType;
  label?: string;
  properties: Record<string, unknown>;
  source_handle?: string;
  target_handle?: string;
}

export interface InfraGraph {
  provider: CloudProvider;
  nodes: InfraNode[];
  edges: InfraEdge[];
  metadata: Record<string, unknown>;
  source?: string;
  created_at?: string;
  updated_at?: string;
}

// -----------------------------------------------------------------------------
// Reverse Engineering Types
// -----------------------------------------------------------------------------

export interface ReverseEngineeringResult {
  success: boolean;
  graph: InfraGraph;
  nodes_imported: number;
  edges_inferred: number;
  warnings: string[];
  errors: string[];
  source_provider: CloudProvider;
  import_timestamp: string;
}

// -----------------------------------------------------------------------------
// Migration Types
// -----------------------------------------------------------------------------

export interface MigrationMapping {
  source_node_id: string;
  source_service: string;
  target_service: string;
  target_resource_type: string;
  
  source_monthly_cost?: number;
  target_monthly_cost?: number;
  cost_delta?: number;
  
  migration_complexity: Severity;
  migration_notes?: string;
  modernization_options: string[];
  
  risks: string[];
  prerequisites: string[];
}

export interface MigrationResult {
  success: boolean;
  source_provider: CloudProvider;
  target_provider: CloudProvider;
  
  source_graph: InfraGraph;
  target_graph: InfraGraph;
  
  mappings: MigrationMapping[];
  
  source_monthly_total: number;
  target_monthly_total: number;
  total_savings: number;
  savings_percent?: number;
  cost_summary_markdown?: string;
  
  overall_complexity: Severity;
  estimated_duration_days?: number;
  key_risks: string[];
  recommendations: string[];
  
  unmapped_services: Record<string, unknown>[];
  bicep_snippets: Record<string, unknown>[];
  
  created_at: string;
}

// -----------------------------------------------------------------------------
// Compliance Types
// -----------------------------------------------------------------------------

export interface ComplianceViolation {
  id: string;
  framework: string;
  requirement_id: string;
  title: string;
  description: string;
  
  affected_nodes: string[];
  severity: Severity;
  
  remediation: string;
  auto_fixable: boolean;
  fix_id?: string;
}

export interface ComplianceReport {
  frameworks: string[];
  overall_score: number;
  
  violations: ComplianceViolation[];
  compliant_controls: string[];
  
  recommendations: string[];
  
  total_checks: number;
  passed_checks: number;
  failed_checks: number;
  
  nodes_analyzed: number;
  generated_at: string;
}

// -----------------------------------------------------------------------------
// Cost Optimization Types
// -----------------------------------------------------------------------------

export interface NodeCost {
  node_id: string;
  service_name: string;
  
  current_sku?: string;
  current_monthly_cost: number;
  
  recommended_sku?: string;
  recommended_monthly_cost?: number;
  
  potential_savings: number;
  savings_percent?: number;
  
  cost_drivers: string[];
  assumptions?: string;
}

export interface CostRecommendation {
  id: string;
  title: string;
  description: string;
  
  affected_nodes: string[];
  category: string;
  
  estimated_savings: number;
  implementation_effort: Severity;
  
  auto_applicable: boolean;
  fix_id?: string;
}

export interface CostOptimization {
  currency: string;
  
  total_monthly_cost: number;
  cost_by_category: Record<string, number>;
  cost_by_service: Record<string, number>;
  
  node_costs: NodeCost[];
  
  recommendations: CostRecommendation[];
  total_potential_savings: number;
  savings_percent?: number;
  
  summary_markdown?: string;
  top_cost_drivers: string[];
  
  analyzed_at: string;
}

// -----------------------------------------------------------------------------
// Fix/Patch Types
// -----------------------------------------------------------------------------

export interface FixPatch {
  id: string;
  fix_type: FixType;
  title: string;
  description: string;
  
  affected_nodes: string[];
  node_patches: Record<string, unknown>[];
  new_nodes: InfraNode[];
  new_edges: InfraEdge[];
  remove_nodes: string[];
  remove_edges: string[];
  
  applied: boolean;
  applied_at?: string;
  result_graph?: InfraGraph;
  
  source?: string;
  created_at: string;
}

// -----------------------------------------------------------------------------
// API Request/Response Types
// -----------------------------------------------------------------------------

export interface ReverseImportRequest {
  project_id: string;
  provider: CloudProvider;
  inventory: Record<string, unknown>;
}

export interface MigrationPlanRequest {
  project_id: string;
  source_provider: CloudProvider;
  target_provider?: CloudProvider;
  options?: {
    modernize?: boolean;
    optimize_cost?: boolean;
    preserve_architecture?: boolean;
  };
}

export interface CostAnalyzeRequest {
  project_id: string;
  infra_graph: InfraGraph;
}

export interface FixApplyRequest {
  project_id: string;
  fix_id: string;
  fix_type: FixType;
}

// -----------------------------------------------------------------------------
// Helper Functions
// -----------------------------------------------------------------------------

export function isAWSProvider(provider: CloudProvider): boolean {
  return provider === 'aws';
}

export function isGCPProvider(provider: CloudProvider): boolean {
  return provider === 'gcp';
}

export function isAzureProvider(provider: CloudProvider): boolean {
  return provider === 'azure';
}

export function isMixedProvider(provider: CloudProvider): boolean {
  return provider === 'mixed';
}

export function getSeverityColor(severity: Severity): string {
  switch (severity) {
    case 'critical':
      return 'text-red-600 bg-red-100';
    case 'high':
      return 'text-orange-600 bg-orange-100';
    case 'medium':
      return 'text-yellow-600 bg-yellow-100';
    case 'low':
      return 'text-blue-600 bg-blue-100';
    case 'info':
      return 'text-gray-600 bg-gray-100';
    default:
      return 'text-gray-600 bg-gray-100';
  }
}

export function formatCurrency(amount: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

export function formatSavingsPercent(percent: number | undefined): string {
  if (percent === undefined || percent === null) return 'N/A';
  const sign = percent >= 0 ? '+' : '';
  return `${sign}${percent.toFixed(1)}%`;
}
