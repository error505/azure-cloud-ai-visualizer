/**
 * Full Autopilot Wizard
 * 
 * Multi-step wizard for generating complete architectures from natural language requirements:
 * 1. Requirements Input - Natural language description
 * 2. Parsed Specs Review - Edit extracted specifications
 * 3. Generate Architecture - Create complete diagram + IaC
 * 4. Review & Refine - Iterate and improve
 */

import React, { useState } from 'react';
import type { Edge, Node as RFNode } from '@xyflow/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { 
  Wand2, 
  ArrowRight, 
  ArrowLeft, 
  CheckCircle, 
  Loader2,
  Sparkles,
  Code,
  DollarSign,
  ShieldCheck,
  RefreshCw
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface ParsedRequirements {
  workload_type: string;
  services_needed: string[];
  compliance_frameworks: string[];
  budget_constraint?: string;
  performance_requirements?: string;
  data_requirements?: string;
  scale_requirements?: string;
  integration_requirements?: string;
}

interface GeneratedArchitecture {
  diagram: { nodes: RFNode[]; edges: Edge[] };
  iac: {
    bicep: string;
    terraform: string;
  };
  cost_estimate: string;
  compliance: string[];
  run_id: string;
}

interface AutopilotWizardProps {
  open: boolean;
  onClose: () => void;
  onArchitectureGenerated: (architecture: GeneratedArchitecture) => void;
}

type WizardStep = 'input' | 'review' | 'generate' | 'result';

const EXAMPLE_REQUIREMENTS = [
  "Build a HIPAA-compliant healthcare data platform with real-time analytics, supporting 10,000 concurrent users",
  "Create an e-commerce platform with payment processing, inventory management, and global CDN distribution",
  "Design a microservices architecture for a SaaS application with multi-tenancy, auto-scaling, and 99.9% uptime",
  "Build a data warehouse for analytics with streaming ingestion, budget under $3,000/month"
];

export const AutopilotWizard: React.FC<AutopilotWizardProps> = ({
  open,
  onClose,
  onArchitectureGenerated,
}) => {
  const { toast } = useToast();
  
  // Wizard state
  const [currentStep, setCurrentStep] = useState<WizardStep>('input');
  const [requirements, setRequirements] = useState('');
  const [parsedSpecs, setParsedSpecs] = useState<ParsedRequirements | null>(null);
  const [generatedArchitecture, setGeneratedArchitecture] = useState<GeneratedArchitecture | null>(null);
  
  // Loading states
  const [isParsing, setIsParsing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState(0);

  // Parse requirements
  const handleParseRequirements = async () => {
    if (!requirements.trim()) {
      toast({
        title: "Requirements needed",
        description: "Please enter your architecture requirements",
        variant: "destructive",
      });
      return;
    }

    setIsParsing(true);
    try {
      const response = await fetch('/api/autopilot/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requirements }),
      });

      if (!response.ok) throw new Error('Failed to parse requirements');

      const data = await response.json();
      setParsedSpecs(data);
      setCurrentStep('review');
      
      toast({
        title: "Requirements parsed",
        description: "Review and edit the extracted specifications",
      });
    } catch (error) {
      toast({
        title: "Parsing failed",
        description: error instanceof Error ? error.message : "Failed to parse requirements",
        variant: "destructive",
      });
    } finally {
      setIsParsing(false);
    }
  };

  // Generate architecture
  const handleGenerateArchitecture = async () => {
    setIsGenerating(true);
    setGenerationProgress(0);
    setCurrentStep('generate');

    // Simulate progress
    const progressInterval = setInterval(() => {
      setGenerationProgress(prev => Math.min(prev + 10, 90));
    }, 1000);

    try {
      const response = await fetch('/api/autopilot/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          requirements,
          use_parallel_pass: true 
        }),
      });

      if (!response.ok) throw new Error('Failed to generate architecture');

      const data = await response.json();
      
      clearInterval(progressInterval);
      setGenerationProgress(100);
      
      if (data.success && data.result) {
        setGeneratedArchitecture(data.result);
        setCurrentStep('result');
        
        toast({
          title: "Architecture generated!",
          description: "Your complete architecture is ready",
        });
      } else {
        throw new Error(data.error || 'Generation failed');
      }
    } catch (error) {
      clearInterval(progressInterval);
      toast({
        title: "Generation failed",
        description: error instanceof Error ? error.message : "Failed to generate architecture",
        variant: "destructive",
      });
      setCurrentStep('review');
    } finally {
      setIsGenerating(false);
    }
  };

  // Apply generated architecture
  const handleApplyArchitecture = () => {
    if (generatedArchitecture) {
      onArchitectureGenerated(generatedArchitecture);
      handleReset();
      onClose();
      
      toast({
        title: "Architecture applied",
        description: "Your generated architecture has been loaded",
      });
    }
  };

  // Reset wizard
  const handleReset = () => {
    setCurrentStep('input');
    setRequirements('');
    setParsedSpecs(null);
    setGeneratedArchitecture(null);
    setGenerationProgress(0);
  };

  // Update parsed spec field
  const updateParsedSpec = (field: keyof ParsedRequirements, value: unknown) => {
    if (parsedSpecs) {
      setParsedSpecs({ ...parsedSpecs, [field]: value });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Wand2 className="h-5 w-5 text-purple-500" />
            Full Autopilot - Architecture Generator
          </DialogTitle>
          <DialogDescription>
            Transform natural language requirements into complete Azure architectures
          </DialogDescription>
        </DialogHeader>

        {/* Progress Indicator */}
        <div className="flex items-center justify-between mb-6">
          {(['input', 'review', 'generate', 'result'] as WizardStep[]).map((step, index) => (
            <React.Fragment key={step}>
              <div className="flex flex-col items-center">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    currentStep === step
                      ? 'bg-purple-500 text-white'
                      : index < ['input', 'review', 'generate', 'result'].indexOf(currentStep)
                      ? 'bg-green-500 text-white'
                      : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  {index < ['input', 'review', 'generate', 'result'].indexOf(currentStep) ? (
                    <CheckCircle className="h-5 w-5" />
                  ) : (
                    <span>{index + 1}</span>
                  )}
                </div>
                <span className="text-xs mt-1 capitalize">{step}</span>
              </div>
              {index < 3 && (
                <div className={`flex-1 h-1 mx-2 ${
                  index < ['input', 'review', 'generate', 'result'].indexOf(currentStep)
                    ? 'bg-green-500'
                    : 'bg-gray-200'
                }`} />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Step 1: Requirements Input */}
        {currentStep === 'input' && (
          <div className="space-y-4">
            <div>
              <Label htmlFor="requirements">Architecture Requirements</Label>
              <Textarea
                id="requirements"
                placeholder="Describe your architecture requirements in natural language..."
                value={requirements}
                onChange={(e) => setRequirements(e.target.value)}
                rows={6}
                className="mt-1"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Include details about: workload type, compliance needs, budget, performance, scale
              </p>
            </div>

            <div>
              <Label>Examples (click to use)</Label>
              <div className="grid grid-cols-1 gap-2 mt-2">
                {EXAMPLE_REQUIREMENTS.map((example, index) => (
                  <Card
                    key={index}
                    className="cursor-pointer hover:border-purple-500 transition-colors"
                    onClick={() => setRequirements(example)}
                  >
                    <CardContent className="p-3">
                      <p className="text-sm">{example}</p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={handleParseRequirements} disabled={isParsing || !requirements.trim()}>
                {isParsing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Parsing...
                  </>
                ) : (
                  <>
                    Parse Requirements
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </>
                )}
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 2: Review Parsed Specs */}
        {currentStep === 'review' && parsedSpecs && (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Extracted Specifications</CardTitle>
                <CardDescription>Review and edit as needed before generation</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <Label htmlFor="workload_type">Workload Type</Label>
                  <Input
                    id="workload_type"
                    value={parsedSpecs.workload_type}
                    onChange={(e) => updateParsedSpec('workload_type', e.target.value)}
                    className="mt-1"
                  />
                </div>

                <div>
                  <Label>Services Needed</Label>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {parsedSpecs.services_needed?.map((service, index) => (
                      <Badge key={index} variant="secondary">
                        {service}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div>
                  <Label>Compliance Frameworks</Label>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {parsedSpecs.compliance_frameworks?.map((framework, index) => (
                      <Badge key={index} variant="outline" className="border-purple-500">
                        <ShieldCheck className="mr-1 h-3 w-3" />
                        {framework}
                      </Badge>
                    ))}
                  </div>
                </div>

                {parsedSpecs.budget_constraint && (
                  <div>
                    <Label htmlFor="budget">Budget Constraint</Label>
                    <Input
                      id="budget"
                      value={parsedSpecs.budget_constraint}
                      onChange={(e) => updateParsedSpec('budget_constraint', e.target.value)}
                      className="mt-1"
                    />
                  </div>
                )}

                {parsedSpecs.performance_requirements && (
                  <div>
                    <Label htmlFor="performance">Performance Requirements</Label>
                    <Input
                      id="performance"
                      value={parsedSpecs.performance_requirements}
                      onChange={(e) => updateParsedSpec('performance_requirements', e.target.value)}
                      className="mt-1"
                    />
                  </div>
                )}

                {parsedSpecs.scale_requirements && (
                  <div>
                    <Label htmlFor="scale">Scale Requirements</Label>
                    <Input
                      id="scale"
                      value={parsedSpecs.scale_requirements}
                      onChange={(e) => updateParsedSpec('scale_requirements', e.target.value)}
                      className="mt-1"
                    />
                  </div>
                )}
              </CardContent>
            </Card>

            <DialogFooter>
              <Button variant="outline" onClick={() => setCurrentStep('input')}>
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back
              </Button>
              <Button onClick={handleGenerateArchitecture}>
                Generate Architecture
                <Sparkles className="ml-2 h-4 w-4" />
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* Step 3: Generating */}
        {currentStep === 'generate' && (
          <div className="space-y-6 py-8">
            <div className="text-center">
              <Loader2 className="h-12 w-12 animate-spin text-purple-500 mx-auto mb-4" />
              <h3 className="text-lg font-semibold mb-2">Generating Your Architecture</h3>
              <p className="text-sm text-muted-foreground mb-6">
                Our AI agents are designing your complete Azure architecture...
              </p>
              <Progress value={generationProgress} className="w-full" />
              <p className="text-xs text-muted-foreground mt-2">{generationProgress}% complete</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-100 rounded-lg">
                      <Code className="h-5 w-5 text-blue-600" />
                    </div>
                    <div>
                      <p className="font-medium">Architecture Design</p>
                      <p className="text-xs text-muted-foreground">Creating diagram & services</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-green-100 rounded-lg">
                      <ShieldCheck className="h-5 w-5 text-green-600" />
                    </div>
                    <div>
                      <p className="font-medium">Compliance Check</p>
                      <p className="text-xs text-muted-foreground">Validating frameworks</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-100 rounded-lg">
                      <Code className="h-5 w-5 text-purple-600" />
                    </div>
                    <div>
                      <p className="font-medium">IaC Generation</p>
                      <p className="text-xs text-muted-foreground">Bicep & Terraform</p>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-yellow-100 rounded-lg">
                      <DollarSign className="h-5 w-5 text-yellow-600" />
                    </div>
                    <div>
                      <p className="font-medium">Cost Estimation</p>
                      <p className="text-xs text-muted-foreground">Calculating expenses</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Step 4: Results */}
        {currentStep === 'result' && generatedArchitecture && (
          <div className="space-y-4">
            <Tabs defaultValue="overview">
              <TabsList className="grid w-full grid-cols-4">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="iac">IaC Code</TabsTrigger>
                <TabsTrigger value="cost">Cost</TabsTrigger>
                <TabsTrigger value="compliance">Compliance</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Architecture Generated Successfully!</CardTitle>
                    <CardDescription>
                      Complete architecture with {generatedArchitecture.diagram?.nodes?.length || 0} services
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 bg-blue-50 rounded-lg">
                        <p className="text-sm font-medium text-blue-900">Services</p>
                        <p className="text-2xl font-bold text-blue-600">
                          {generatedArchitecture.diagram?.nodes?.length || 0}
                        </p>
                      </div>
                      <div className="p-4 bg-purple-50 rounded-lg">
                        <p className="text-sm font-medium text-purple-900">Connections</p>
                        <p className="text-2xl font-bold text-purple-600">
                          {generatedArchitecture.diagram?.edges?.length || 0}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="iac" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle>Infrastructure as Code</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <Tabs defaultValue="bicep">
                      <TabsList>
                        <TabsTrigger value="bicep">Bicep</TabsTrigger>
                        <TabsTrigger value="terraform">Terraform</TabsTrigger>
                      </TabsList>
                      <TabsContent value="bicep">
                        <pre className="p-4 bg-gray-50 rounded-lg overflow-x-auto text-xs">
                          {generatedArchitecture.iac.bicep || 'No Bicep code generated'}
                        </pre>
                      </TabsContent>
                      <TabsContent value="terraform">
                        <pre className="p-4 bg-gray-50 rounded-lg overflow-x-auto text-xs">
                          {generatedArchitecture.iac.terraform || 'No Terraform code generated'}
                        </pre>
                      </TabsContent>
                    </Tabs>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="cost" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <DollarSign className="h-5 w-5" />
                      Cost Estimate
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold text-green-600">
                      {generatedArchitecture.cost_estimate}
                    </p>
                    <p className="text-sm text-muted-foreground mt-2">
                      Estimated monthly cost for this architecture
                    </p>
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="compliance" className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <ShieldCheck className="h-5 w-5" />
                      Compliance Frameworks
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex flex-wrap gap-2">
                      {generatedArchitecture.compliance.map((framework, index) => (
                        <Badge key={index} variant="outline" className="border-green-500">
                          <CheckCircle className="mr-1 h-3 w-3 text-green-500" />
                          {framework}
                        </Badge>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            <DialogFooter>
              <Button variant="outline" onClick={handleGenerateArchitecture}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Regenerate
              </Button>
              <Button onClick={handleApplyArchitecture}>
                <CheckCircle className="mr-2 h-4 w-4" />
                Apply Architecture
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
