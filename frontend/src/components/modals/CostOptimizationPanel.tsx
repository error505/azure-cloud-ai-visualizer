import { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Loader2, DollarSign, TrendingDown, AlertTriangle, CheckCircle2, Lightbulb, BarChart3, X } from 'lucide-react';
import { Progress } from '@/components/ui/progress';
import { useDiagramStore } from '@/store/diagramStore';

// API Response types matching backend models
interface NodeCostResponse {
  node_id: string;
  service_name: string;
  category: string;
  current_sku?: string;
  current_monthly_cost: number;
  recommended_sku?: string;
  recommended_monthly_cost?: number;
  potential_savings: number;
  savings_percent?: number;
  cost_drivers: string[];
  optimization_tips: string[];
}

interface CostRecommendationResponse {
  id: string;
  title: string;
  description: string;
  affected_nodes: string[];
  category: string;
  estimated_savings: number;
  implementation_effort: string;
  auto_applicable: boolean;
}

interface CostOptimizationResponse {
  currency: string;
  total_monthly_cost: number;
  cost_by_category: Record<string, number>;
  cost_by_service: Record<string, number>;
  node_costs: NodeCostResponse[];
  recommendations: CostRecommendationResponse[];
  total_potential_savings: number;
  savings_percent?: number;
  summary_markdown: string;
  top_cost_drivers: string[];
  analyzed_at: string;
}

interface CostOptimizationPanelProps {
  isOpen: boolean;
  onClose: () => void;
  projectId?: string;
}

export function CostOptimizationPanel({ isOpen, onClose, projectId }: CostOptimizationPanelProps) {
  const [loading, setLoading] = useState(false);
  const [costData, setCostData] = useState<CostOptimizationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const nodes = useDiagramStore((state) => state.nodes);
  const edges = useDiagramStore((state) => state.edges);

  const analyzeCosts = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {

      // Transform nodes to diagram format expected by API
      const diagramNodes = nodes.map(node => ({
        id: node.id,
        type: node.type || 'default',
        position: node.position,
        data: node.data,
      }));

      const diagramEdges = edges.map(edge => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        sourceHandle: edge.sourceHandle,
        targetHandle: edge.targetHandle,
        data: edge.data,
      }));

      const response = await fetch('/api/cost/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          diagram: {
            nodes: diagramNodes,
            edges: diagramEdges,
          },
          project_id: projectId,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to analyze costs');
      }

      const data = await response.json();
      setCostData(data.cost_optimization);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze costs');
    } finally {
      setLoading(false);
    }
  }, [nodes, edges, projectId]);

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'high':
        return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
      case 'medium':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'low':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'compute':
        return 'bg-purple-500/20 text-purple-400';
      case 'storage':
        return 'bg-blue-500/20 text-blue-400';
      case 'network':
        return 'bg-green-500/20 text-green-400';
      case 'database':
        return 'bg-orange-500/20 text-orange-400';
      case 'ai_ml':
        return 'bg-pink-500/20 text-pink-400';
      default:
        return 'bg-gray-500/20 text-gray-400';
    }
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl w-[900px] max-h-[85vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/20 rounded-lg">
              <DollarSign className="h-6 w-6 text-green-400" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white">Cost Optimization</h2>
              <p className="text-sm text-gray-400">Analyze and optimize your cloud spending</p>
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Content */}
        <ScrollArea className="flex-1 p-6">
          {!costData && !loading && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="p-4 bg-green-500/10 rounded-full mb-4">
                <BarChart3 className="h-12 w-12 text-green-400" />
              </div>
              <h3 className="text-lg font-medium text-white mb-2">Analyze Your Infrastructure Costs</h3>
              <p className="text-gray-400 text-center max-w-md mb-6">
                Get detailed cost breakdowns, optimization recommendations, and potential savings for your cloud architecture.
              </p>
              <Button onClick={analyzeCosts} className="bg-green-600 hover:bg-green-700">
                <DollarSign className="h-4 w-4 mr-2" />
                Analyze Costs
              </Button>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-green-400 mb-4" />
              <p className="text-gray-400">Analyzing infrastructure costs...</p>
            </div>
          )}

          {error && (
            <div className="flex flex-col items-center justify-center py-12">
              <div className="p-4 bg-red-500/10 rounded-full mb-4">
                <AlertTriangle className="h-12 w-12 text-red-400" />
              </div>
              <h3 className="text-lg font-medium text-white mb-2">Analysis Failed</h3>
              <p className="text-red-400 text-center max-w-md mb-6">{error}</p>
              <Button onClick={analyzeCosts} variant="outline">
                Try Again
              </Button>
            </div>
          )}

          {costData && !loading && (
            <div className="space-y-6">
              {/* Summary Cards */}
              <div className="grid grid-cols-3 gap-4">
                <Card className="bg-gray-800/50 border-gray-700">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-400">Current Monthly Cost</p>
                        <p className="text-2xl font-bold text-white">
                          {formatCurrency(costData.total_monthly_cost)}
                        </p>
                      </div>
                      <DollarSign className="h-8 w-8 text-gray-500" />
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-gray-800/50 border-gray-700">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-gray-400">After Optimization</p>
                        <p className="text-2xl font-bold text-green-400">
                          {formatCurrency(costData.total_monthly_cost - costData.total_potential_savings)}
                        </p>
                      </div>
                      <TrendingDown className="h-8 w-8 text-green-500" />
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-green-900/30 border-green-700/50">
                  <CardContent className="pt-6">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-green-400">Potential Savings</p>
                        <p className="text-2xl font-bold text-green-300">
                          {formatCurrency(costData.total_potential_savings)}
                        </p>
                        <p className="text-xs text-green-500">
                          {costData.savings_percent
                            ? `${Math.round(costData.savings_percent)}% reduction`
                            : '0% reduction'}
                        </p>
                      </div>
                      <CheckCircle2 className="h-8 w-8 text-green-400" />
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Cost Breakdown by Category */}
              <Card className="bg-gray-800/50 border-gray-700">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    Cost Breakdown by Category
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {Object.entries(costData.cost_by_category || {}).map(([category, amount]) => {
                      const percentage = costData.total_monthly_cost > 0
                        ? (amount / costData.total_monthly_cost) * 100
                        : 0;
                      return (
                        <div key={category} className="space-y-2">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Badge className={getCategoryColor(category.toLowerCase())}>
                                {category.replace('_', ' ').toUpperCase()}
                              </Badge>
                            </div>
                            <span className="text-white font-medium">
                              {formatCurrency(amount)}
                              <span className="text-gray-400 text-sm ml-2">
                                ({percentage.toFixed(1)}%)
                              </span>
                            </span>
                          </div>
                          <Progress value={percentage} className="h-2" />
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>

              {/* Node Costs */}
              {costData.node_costs && costData.node_costs.length > 0 && (
                <Card className="bg-gray-800/50 border-gray-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2">
                      <DollarSign className="h-5 w-5" />
                      Individual Resource Costs
                    </CardTitle>
                    <CardDescription>Monthly cost per resource</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2 max-h-[300px] overflow-y-auto">
                      {costData.node_costs
                        .sort((a, b) => b.current_monthly_cost - a.current_monthly_cost)
                        .map((nodeCost) => (
                          <div
                            key={nodeCost.node_id}
                            className="flex items-center justify-between p-3 bg-gray-900/50 rounded-lg"
                          >
                            <div className="flex items-center gap-3">
                              <Badge className={getCategoryColor(nodeCost.category.toLowerCase())}>
                                {nodeCost.category}
                              </Badge>
                              <span className="text-white">{nodeCost.service_name}</span>
                            </div>
                            <div className="text-right">
                              <p className="text-white font-medium">
                                {formatCurrency(nodeCost.current_monthly_cost)}/mo
                              </p>
                              {nodeCost.current_sku && (
                                <p className="text-xs text-gray-400">{nodeCost.current_sku}</p>
                              )}
                            </div>
                          </div>
                        ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Recommendations */}
              {costData.recommendations && costData.recommendations.length > 0 && (
                <Card className="bg-gray-800/50 border-gray-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2">
                      <Lightbulb className="h-5 w-5 text-yellow-400" />
                      Optimization Recommendations
                    </CardTitle>
                    <CardDescription>
                      {costData.recommendations.length} recommendations found
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {costData.recommendations.map((rec, index) => (
                        <div
                          key={rec.id || index}
                          className="p-4 bg-gray-900/50 rounded-lg border border-gray-700"
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <Badge className={getPriorityColor(rec.implementation_effort)}>
                                  {rec.implementation_effort.toUpperCase()} EFFORT
                                </Badge>
                                <Badge variant="outline" className="text-gray-400 border-gray-600">
                                  {rec.category}
                                </Badge>
                              </div>
                              <h4 className="text-white font-medium mb-1">{rec.title}</h4>
                              <p className="text-gray-400 text-sm">{rec.description}</p>
                              {rec.affected_nodes.length > 0 && (
                                <p className="text-xs text-gray-500 mt-2">
                                  Affected resources: {rec.affected_nodes.length}
                                </p>
                              )}
                            </div>
                            <div className="text-right shrink-0">
                              <p className="text-green-400 font-bold">
                                {formatCurrency(rec.estimated_savings)}/mo
                              </p>
                              <p className="text-xs text-gray-400">potential savings</p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-4">
                <Button variant="outline" onClick={analyzeCosts}>
                  Re-analyze
                </Button>
                <Button className="bg-green-600 hover:bg-green-700">
                  Apply Optimizations
                </Button>
              </div>
            </div>
          )}
        </ScrollArea>
      </div>
    </div>
  );
}
