/**
 * Documentation Panel
 * 
 * AI-powered documentation generator for architecture diagrams:
 * - HLD (High-Level Design) - 10 sections
 * - LLD (Low-Level Design) - 6 sections
 * - Runbook (Operations) - 10 sections
 * - Deployment Guide - 7 sections
 * 
 * Features: Live preview, Markdown/PDF/Word export, Regenerate with custom instructions
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
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { 
  FileText,
  Download,
  Loader2,
  RefreshCw,
  Copy,
  CheckCircle,
  Book,
  Code,
  Wrench,
  Rocket
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import ReactMarkdown from 'react-markdown';

type DocType = 'hld' | 'lld' | 'runbook' | 'deployment';

interface DocumentTypeInfo {
  type: DocType;
  name: string;
  icon: React.ReactNode;
  color: string;
  description: string;
  sections: number;
}

interface DocumentMetadata {
  document_type: string;
  generated_at: string;
  diagram_services_count: number;
  version: string;
}

interface GeneratedDoc {
  markdown: string;
  metadata: DocumentMetadata;
  format: string;
}

interface DocumentationPanelProps {
  open: boolean;
  onClose: () => void;
  diagram: { nodes: RFNode[]; edges: Edge[] };
  requirements?: string;
}

const DOC_TYPES: DocumentTypeInfo[] = [
  {
    type: 'hld',
    name: 'High-Level Design',
    icon: <Book className="h-4 w-4" />,
    color: 'blue',
    description: 'Executive summary, architecture overview, components, data flows, integrations, tech stack, security, scalability, HA/DR, cost',
    sections: 10,
  },
  {
    type: 'lld',
    name: 'Low-Level Design',
    icon: <Code className="h-4 w-4" />,
    color: 'purple',
    description: 'Service specifications (SKU, config, dependencies), network architecture, IAM, data architecture, monitoring, backup/DR',
    sections: 6,
  },
  {
    type: 'runbook',
    name: 'Operational Runbook',
    icon: <Wrench className="h-4 w-4" />,
    color: 'green',
    description: 'Startup/shutdown, health checks, troubleshooting, incident response, maintenance, scaling, backup/recovery, monitoring/alerts',
    sections: 10,
  },
  {
    type: 'deployment',
    name: 'Deployment Guide',
    icon: <Rocket className="h-4 w-4" />,
    color: 'orange',
    description: 'Prerequisites, environment setup, deployment steps (Bicep/Terraform), validation, rollback, common issues',
    sections: 7,
  },
];

export const DocumentationPanel: React.FC<DocumentationPanelProps> = ({
  open,
  onClose,
  diagram,
  requirements,
}) => {
  const { toast } = useToast();
  
  const [selectedDocType, setSelectedDocType] = useState<DocType>('hld');
  const [generatedDoc, setGeneratedDoc] = useState<GeneratedDoc | null>(null);
  const [customInstructions, setCustomInstructions] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  // Generate documentation
  const handleGenerate = async () => {
    if (!diagram || !diagram.nodes || diagram.nodes.length === 0) {
      toast({
        title: "No diagram",
        description: "Please create a diagram first",
        variant: "destructive",
      });
      return;
    }

    setIsGenerating(true);
    try {
      const response = await fetch('/api/docs/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          diagram,
          doc_type: selectedDocType,
          requirements: requirements || customInstructions || undefined,
        }),
      });

      if (!response.ok) throw new Error('Failed to generate documentation');

      const data = await response.json();
      
      if (data.success) {
        setGeneratedDoc({
          markdown: data.markdown,
          metadata: data.metadata,
          format: data.format,
        });
        
        toast({
          title: "Documentation generated!",
          description: `${DOC_TYPES.find(t => t.type === selectedDocType)?.name} is ready`,
        });
      } else {
        throw new Error('Generation failed');
      }
    } catch (error) {
      toast({
        title: "Generation failed",
        description: error instanceof Error ? error.message : "Failed to generate documentation",
        variant: "destructive",
      });
    } finally {
      setIsGenerating(false);
    }
  };

  // Copy to clipboard
  const handleCopy = async () => {
    if (generatedDoc) {
      await navigator.clipboard.writeText(generatedDoc.markdown);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
      
      toast({
        title: "Copied!",
        description: "Markdown copied to clipboard",
      });
    }
  };

  // Download as markdown
  const handleDownload = (format: 'markdown' | 'pdf' | 'word') => {
    if (!generatedDoc) return;

    if (format === 'markdown') {
      const blob = new Blob([generatedDoc.markdown], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedDocType}-${Date.now()}.md`;
      a.click();
      URL.revokeObjectURL(url);
      
      toast({
        title: "Downloaded",
        description: "Markdown file saved",
      });
    } else {
      toast({
        title: "Coming soon",
        description: `${format.toUpperCase()} export will be available soon`,
      });
    }
  };

  const selectedDocInfo = DOC_TYPES.find(t => t.type === selectedDocType);

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-6xl max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-blue-500" />
            Documentation Generator
          </DialogTitle>
          <DialogDescription>
            Generate enterprise-grade technical documentation from your architecture
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-hidden">
          <Tabs value={selectedDocType} onValueChange={(v) => setSelectedDocType(v as DocType)} className="h-full flex flex-col">
            {/* Document Type Selector */}
            <TabsList className="grid w-full grid-cols-4 mb-4">
              {DOC_TYPES.map((docType) => (
                <TabsTrigger key={docType.type} value={docType.type} className="flex items-center gap-2">
                  {docType.icon}
                  <span className="hidden md:inline">{docType.name}</span>
                  <span className="md:hidden">{docType.type.toUpperCase()}</span>
                </TabsTrigger>
              ))}
            </TabsList>

            {/* Content for each doc type */}
            {DOC_TYPES.map((docType) => (
              <TabsContent key={docType.type} value={docType.type} className="flex-1 overflow-auto space-y-4">
                {/* Doc Type Info */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      {docType.icon}
                      {docType.name}
                      <Badge variant="outline">{docType.sections} sections</Badge>
                    </CardTitle>
                    <CardDescription>{docType.description}</CardDescription>
                  </CardHeader>
                </Card>

                {/* Custom Instructions */}
                {!generatedDoc && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Custom Instructions (Optional)</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Textarea
                        placeholder="Add specific details or requirements to include in the documentation..."
                        value={customInstructions}
                        onChange={(e) => setCustomInstructions(e.target.value)}
                        rows={3}
                      />
                    </CardContent>
                  </Card>
                )}

                {/* Generated Documentation */}
                {generatedDoc && (
                  <Card className="flex-1">
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <div>
                          <CardTitle className="text-sm">Generated Documentation</CardTitle>
                          <CardDescription className="text-xs">
                            Generated: {new Date(generatedDoc.metadata.generated_at).toLocaleString()} • 
                            Services: {generatedDoc.metadata.diagram_services_count} • 
                            Version: {generatedDoc.metadata.version}
                          </CardDescription>
                        </div>
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={handleCopy}>
                            {isCopied ? (
                              <>
                                <CheckCircle className="mr-2 h-3 w-3 text-green-500" />
                                Copied
                              </>
                            ) : (
                              <>
                                <Copy className="mr-2 h-3 w-3" />
                                Copy
                              </>
                            )}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setGeneratedDoc(null);
                              setCustomInstructions('');
                            }}
                          >
                            <RefreshCw className="mr-2 h-3 w-3" />
                            New
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <Tabs defaultValue="preview">
                        <TabsList>
                          <TabsTrigger value="preview">Preview</TabsTrigger>
                          <TabsTrigger value="markdown">Markdown</TabsTrigger>
                        </TabsList>
                        
                        <TabsContent value="preview" className="max-h-96 overflow-y-auto">
                          <div className="prose prose-sm max-w-none">
                            <ReactMarkdown>{generatedDoc.markdown}</ReactMarkdown>
                          </div>
                        </TabsContent>
                        
                        <TabsContent value="markdown" className="max-h-96 overflow-y-auto">
                          <pre className="p-4 bg-gray-50 rounded-lg text-xs whitespace-pre-wrap">
                            {generatedDoc.markdown}
                          </pre>
                        </TabsContent>
                      </Tabs>
                    </CardContent>
                  </Card>
                )}

                {/* Generate/Download Buttons */}
                <DialogFooter>
                  {!generatedDoc ? (
                    <>
                      <Button variant="outline" onClick={onClose}>
                        Cancel
                      </Button>
                      <Button onClick={handleGenerate} disabled={isGenerating}>
                        {isGenerating ? (
                          <>
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            Generating...
                          </>
                        ) : (
                          <>
                            <FileText className="mr-2 h-4 w-4" />
                            Generate {docType.name}
                          </>
                        )}
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button variant="outline" onClick={() => handleDownload('markdown')}>
                        <Download className="mr-2 h-4 w-4" />
                        Markdown
                      </Button>
                      <Button variant="outline" onClick={() => handleDownload('pdf')} disabled>
                        <Download className="mr-2 h-4 w-4" />
                        PDF (Soon)
                      </Button>
                      <Button variant="outline" onClick={() => handleDownload('word')} disabled>
                        <Download className="mr-2 h-4 w-4" />
                        Word (Soon)
                      </Button>
                    </>
                  )}
                </DialogFooter>
              </TabsContent>
            ))}
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
};
