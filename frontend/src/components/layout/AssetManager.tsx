import React, { useState, useCallback, useRef } from 'react';
import { Icon } from '@iconify/react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useToast } from '@/hooks/use-toast';
import { useDiagramStore } from '@/store/diagramStore';

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  url: string;
  uploadProgress?: number;
  uploadStatus: 'uploading' | 'completed' | 'error';
  thumbnail?: string;
}

interface CloudImportState {
  status: 'idle' | 'detecting' | 'importing' | 'success' | 'error';
  provider: 'azure' | 'aws' | 'gcp' | null;
  fileName: string | null;
  fileSize: number | null;
  progress: string;
  error: string | null;
  nodeCount: number;
}

interface AssetManagerProps {
  isOpen: boolean;
  onToggle: () => void;
  onFileSelect?: (file: UploadedFile) => void;
  projectId?: string;
}

const PROVIDER_INFO = {
  azure: { label: 'Microsoft Azure', color: 'bg-blue-500', icon: '☁️' },
  aws: { label: 'Amazon Web Services', color: 'bg-orange-500', icon: '🔶' },
  gcp: { label: 'Google Cloud Platform', color: 'bg-red-500', icon: '🔴' },
};

const AssetManager: React.FC<AssetManagerProps> = ({ isOpen, onToggle, onFileSelect, projectId }) => {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('files');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const cloudInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();
  const loadDiagram = useDiagramStore((state) => state.loadDiagram);

  // Cloud import state
  const [cloudImport, setCloudImport] = useState<CloudImportState>({
    status: 'idle',
    provider: null,
    fileName: null,
    fileSize: null,
    progress: '',
    error: null,
    nodeCount: 0,
  });
  const [inventoryData, setInventoryData] = useState<Record<string, unknown> | null>(null);

  // File upload handlers
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const uploadFiles = useCallback(async (filesToUpload: File[]) => {
    for (const file of filesToUpload) {
      const fileId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const uploadedFile: UploadedFile = {
        id: fileId,
        name: file.name,
        size: file.size,
        type: file.type,
        url: '',
        uploadProgress: 0,
        uploadStatus: 'uploading'
      };

      setFiles(prev => [...prev, uploadedFile]);

      // Simulate upload progress
      let progress = 0;
      const interval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress >= 100) {
          clearInterval(interval);
          const url = URL.createObjectURL(file);
          setFiles(prev => prev.map(f => 
            f.id === fileId 
              ? { ...f, uploadStatus: 'completed', uploadProgress: 100, url, thumbnail: file.type.startsWith('image/') ? url : undefined }
              : f
          ));
          toast({ title: "Upload Complete", description: `${file.name} uploaded successfully` });
        } else {
          setFiles(prev => prev.map(f => 
            f.id === fileId ? { ...f, uploadProgress: Math.min(progress, 100) } : f
          ));
        }
      }, 150);
    }
  }, [toast]);

  // Cloud file handler - declared before handleDrop
  const handleCloudFile = useCallback(async (file: File) => {
    setCloudImport(s => ({
      ...s,
      status: 'detecting',
      fileName: file.name,
      fileSize: file.size,
      progress: 'Reading file...',
      error: null,
    }));

    try {
      const text = await file.text();
      const data = JSON.parse(text);
      setInventoryData(data);

      // Detect provider
      setCloudImport(s => ({ ...s, progress: 'Detecting cloud provider...' }));
      const detectResponse = await fetch('/api/reverse/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inventory: data }),
      });

      if (!detectResponse.ok) throw new Error('Failed to detect provider');

      const detectData = await detectResponse.json();
      const provider = detectData.provider as 'azure' | 'aws' | 'gcp';

      setCloudImport(s => ({
        ...s,
        status: 'idle',
        provider,
        progress: provider ? `Detected: ${PROVIDER_INFO[provider]?.label || provider}` : 'Ready to import',
      }));
    } catch (err) {
      setCloudImport(s => ({
        ...s,
        status: 'error',
        error: err instanceof Error ? err.message : 'Failed to read file',
        progress: '',
      }));
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    
    // Check if it's a JSON file for cloud import
    const jsonFiles = droppedFiles.filter(f => f.name.endsWith('.json'));
    if (jsonFiles.length > 0 && activeTab === 'cloud') {
      handleCloudFile(jsonFiles[0]);
    } else {
      uploadFiles(droppedFiles);
    }
  }, [uploadFiles, activeTab, handleCloudFile]);

  const handleFileSelect = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    uploadFiles(selectedFiles);
  }, [uploadFiles]);

  const deleteFile = useCallback((fileId: string) => {
    const file = files.find(f => f.id === fileId);
    if (file?.url) URL.revokeObjectURL(file.url);
    setFiles(prev => prev.filter(f => f.id !== fileId));
    toast({ title: "File Deleted", description: "File removed from assets" });
  }, [files, toast]);

  const handleCloudInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleCloudFile(file);
  }, [handleCloudFile]);

  const importInventory = useCallback(async () => {
    if (!inventoryData || !cloudImport.provider) return;

    setCloudImport(s => ({ ...s, status: 'importing', progress: 'Importing inventory...' }));

    try {
      // Step 1: Import the inventory to get parsed nodes
      const response = await fetch('/api/reverse/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId || 'default',
          inventory: inventoryData,
          provider: cloudImport.provider,
        }),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || 'Import failed');
      }

      const result = await response.json();
      const graph = result.graph;

      if (!graph?.nodes?.length) {
        throw new Error('No resources found in inventory');
      }

      // Step 2: Convert imported nodes to diagram format for source cloud
      const sourceNodes = graph.nodes.map((node: any, index: number) => ({
        id: node.id,
        type: 'azureService',
        position: { x: 100 + (index % 6) * 180, y: 100 + Math.floor(index / 6) * 140 },
        data: {
          label: node.label,
          title: node.label,
          serviceType: node.service_type,
          category: node.category,
          provider: node.provider,
          properties: node.properties,
          iconPath: node.icon_path,
          region: node.region,
          tags: node.tags,
          status: 'active',
        },
      }));

      const sourceEdges = (graph.edges || []).map((edge: any) => ({
        id: edge.id || `${edge.source}-${edge.target}`,
        source: edge.source,
        target: edge.target,
        type: 'smoothstep',
        animated: true,
      }));

      // Step 3: If source is AWS/GCP, automatically trigger AI-powered migration to Azure
      if (cloudImport.provider !== 'azure') {
        setCloudImport(s => ({ ...s, progress: '🤖 AI Agent analyzing infrastructure...' }));

        try {
          // Create diagram format for migration API
          const diagramForMigration = {
            nodes: sourceNodes,
            edges: sourceEdges,
          };

          // Use AI-powered migration endpoint
          const migrationResponse = await fetch('/api/migration/ai-plan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              project_id: projectId || 'default',
              source_provider: cloudImport.provider,
              target_provider: 'azure',
              diagram: diagramForMigration,
            }),
          });

          if (migrationResponse.ok) {
            const migrationResult = await migrationResponse.json();
            
            // Convert migrated nodes to display format
            const migratedNodes = migrationResult.target_nodes?.map((node: any, index: number) => ({
              id: `azure-${node.id}`,
              type: 'azureService',
              position: { x: 550 + (index % 6) * 180, y: 100 + Math.floor(index / 6) * 140 },
              data: {
                label: node.label,
                title: node.label,
                serviceType: node.service_type,
                category: node.category,
                provider: 'azure',
                resourceType: node.resource_type,
                status: 'active',
              },
            })) || [];

            // Combine source and migrated nodes for side-by-side view
            const allNodes = [...sourceNodes, ...migratedNodes];
            
            loadDiagram(allNodes, sourceEdges);

            // Show migration summary
            const savings = migrationResult.total_savings || 0;
            const sourceTotal = migrationResult.source_monthly_total || 0;
            const targetTotal = migrationResult.target_monthly_total || 0;

            setCloudImport(s => ({
              ...s,
              status: 'success',
              nodeCount: sourceNodes.length,
              progress: `Imported ${sourceNodes.length} ${cloudImport.provider?.toUpperCase()} resources → ${migratedNodes.length} Azure equivalents`,
            }));

            toast({
              title: "Migration Analysis Complete",
              description: `${sourceNodes.length} ${cloudImport.provider?.toUpperCase()} resources mapped to Azure. Estimated monthly savings: $${savings.toFixed(2)}`,
            });
          } else {
            // Migration failed, but still show source nodes
            loadDiagram(sourceNodes, sourceEdges);
            toast({
              title: "Partial Import",
              description: `Imported ${sourceNodes.length} resources. Migration analysis unavailable.`,
            });
          }
        } catch (migrationErr) {
          // Migration failed, show source nodes anyway
          loadDiagram(sourceNodes, sourceEdges);
          console.warn('Migration analysis failed:', migrationErr);
          toast({
            title: "Import Complete",
            description: `Imported ${sourceNodes.length} ${cloudImport.provider?.toUpperCase()} resources. Use Migration Panel for Azure mapping.`,
          });
        }
      } else {
        // Azure import - just load directly
        loadDiagram(sourceNodes, sourceEdges);
        setCloudImport(s => ({
          ...s,
          status: 'success',
          nodeCount: graph.nodes.length,
          progress: `Imported ${graph.nodes.length} Azure resources`,
        }));
        toast({
          title: "Import Successful",
          description: `Imported ${graph.nodes.length} Azure resources to diagram`,
        });
      }

      // Reset after 5 seconds
      setTimeout(() => {
        setCloudImport({
          status: 'idle',
          provider: null,
          fileName: null,
          fileSize: null,
          progress: '',
          error: null,
          nodeCount: 0,
        });
        setInventoryData(null);
      }, 5000);

    } catch (err) {
      setCloudImport(s => ({
        ...s,
        status: 'error',
        error: err instanceof Error ? err.message : 'Import failed',
        progress: '',
      }));
    }
  }, [inventoryData, cloudImport.provider, projectId, loadDiagram, toast]);

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileIcon = (type: string): string => {
    if (type.startsWith('image/')) return 'mdi:image';
    if (type.startsWith('video/')) return 'mdi:video';
    if (type.includes('pdf')) return 'mdi:file-pdf';
    if (type.includes('json')) return 'mdi:code-json';
    return 'mdi:file';
  };

  const filteredFiles = files.filter(file => 
    file.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (!isOpen) return null;

  return (
    <div className="w-80 h-full bg-background border-l border-border/50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-border/50">
        <div className="flex items-center gap-2">
          <Icon icon="mdi:folder-multiple-image" className="text-xl text-primary" />
          <h3 className="font-semibold">Assets & Import</h3>
        </div>
        <Button variant="ghost" size="icon" onClick={onToggle} className="h-8 w-8">
          <Icon icon="mdi:close" />
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col">
        <div className="px-4 pt-2">
          <TabsList className="w-full">
            <TabsTrigger value="files" className="flex-1">
              <Icon icon="mdi:file-multiple" className="mr-1.5" />
              Files
            </TabsTrigger>
            <TabsTrigger value="cloud" className="flex-1">
              <Icon icon="mdi:cloud-download" className="mr-1.5" />
              Cloud Import
            </TabsTrigger>
          </TabsList>
        </div>

        {/* Files Tab */}
        <TabsContent value="files" className="flex-1 flex flex-col mt-0 data-[state=inactive]:hidden">
          {/* Search */}
          <div className="p-4 border-b border-border/50">
            <Input
              placeholder="Search assets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full"
            />
          </div>

          {/* Upload Area */}
          <div className="p-4 border-b border-border/50">
            <div
              className={`border-2 border-dashed rounded-lg p-4 text-center transition-colors cursor-pointer ${
                isDragOver ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/50'
              }`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={handleFileSelect}
            >
              <Icon icon="mdi:cloud-upload" className="mx-auto text-3xl text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">Drop files or click to upload</p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={handleFileInputChange}
              accept="image/*,application/pdf,.doc,.docx"
            />
          </div>

          {/* File List */}
          <ScrollArea className="flex-1">
            <div className="p-4 space-y-2">
              {filteredFiles.length === 0 ? (
                <div className="text-center py-6">
                  <Icon icon="mdi:folder-open" className="mx-auto text-3xl text-muted-foreground mb-2" />
                  <p className="text-sm text-muted-foreground">
                    {searchQuery ? 'No matches' : 'No assets yet'}
                  </p>
                </div>
              ) : (
                filteredFiles.map((file) => (
                  <Card key={file.id} className="cursor-pointer hover:bg-accent/50">
                    <CardContent className="p-2">
                      <div className="flex items-center gap-2">
                        {file.thumbnail ? (
                          <img src={file.thumbnail} alt="" className="w-10 h-10 object-cover rounded" />
                        ) : (
                          <div className="w-10 h-10 bg-muted rounded flex items-center justify-center">
                            <Icon icon={getFileIcon(file.type)} className="text-lg text-muted-foreground" />
                          </div>
                        )}
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">{file.name}</p>
                          <p className="text-xs text-muted-foreground">{formatFileSize(file.size)}</p>
                          {file.uploadStatus === 'uploading' && (
                            <Progress value={file.uploadProgress} className="h-1 mt-1" />
                          )}
                        </div>
                        {file.uploadStatus === 'completed' && (
                          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); deleteFile(file.id); }}>
                            <Icon icon="mdi:delete" className="text-xs" />
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        {/* Cloud Import Tab */}
        <TabsContent value="cloud" className="flex-1 flex flex-col mt-0 data-[state=inactive]:hidden">
          <ScrollArea className="flex-1">
            <div className="p-4 space-y-4">
              {/* Cloud Upload Area */}
              <div
                className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
                  isDragOver ? 'border-primary bg-primary/10' : 'border-border hover:border-primary/50'
                }`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => cloudInputRef.current?.click()}
              >
                <Icon icon="mdi:cloud-upload" className="mx-auto text-4xl text-muted-foreground mb-2" />
                <p className="text-sm font-medium text-foreground mb-1">
                  Upload Cloud Inventory
                </p>
                <p className="text-xs text-muted-foreground">
                  Azure Resource Graph, AWS CloudFormation, GCP Asset exports
                </p>
              </div>
              <input
                ref={cloudInputRef}
                type="file"
                className="hidden"
                onChange={handleCloudInputChange}
                accept=".json"
              />

              {/* Import Status */}
              {cloudImport.fileName && (
                <Card>
                  <CardContent className="p-4 space-y-3">
                    {/* File Info */}
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 bg-muted rounded flex items-center justify-center">
                        <Icon icon="mdi:code-json" className="text-lg text-blue-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{cloudImport.fileName}</p>
                        <p className="text-xs text-muted-foreground">
                          {cloudImport.fileSize ? formatFileSize(cloudImport.fileSize) : ''}
                        </p>
                      </div>
                    </div>

                    {/* Provider Badge */}
                    {cloudImport.provider && (
                      <div className="flex items-center gap-2">
                        <Badge className={`${PROVIDER_INFO[cloudImport.provider].color} text-white`}>
                          {PROVIDER_INFO[cloudImport.provider].icon} {PROVIDER_INFO[cloudImport.provider].label}
                        </Badge>
                      </div>
                    )}

                    {/* Progress/Status */}
                    {cloudImport.progress && (
                      <p className="text-sm text-muted-foreground">{cloudImport.progress}</p>
                    )}

                    {/* Error */}
                    {cloudImport.error && (
                      <div className="bg-red-500/10 border border-red-500/30 rounded p-2">
                        <p className="text-sm text-red-400">{cloudImport.error}</p>
                      </div>
                    )}

                    {/* Success */}
                    {cloudImport.status === 'success' && (
                      <div className="bg-green-500/10 border border-green-500/30 rounded p-2 flex items-center gap-2">
                        <Icon icon="mdi:check-circle" className="text-green-400" />
                        <p className="text-sm text-green-400">
                          Imported {cloudImport.nodeCount} resources
                        </p>
                      </div>
                    )}

                    {/* Import Button */}
                    {cloudImport.status === 'idle' && cloudImport.provider && (
                      <Button onClick={importInventory} className="w-full">
                        <Icon icon="mdi:import" className="mr-2" />
                        Import to Diagram
                      </Button>
                    )}

                    {cloudImport.status === 'importing' && (
                      <Button disabled className="w-full">
                        <Icon icon="mdi:loading" className="mr-2 animate-spin" />
                        Importing...
                      </Button>
                    )}
                  </CardContent>
                </Card>
              )}

              {/* Help Text */}
              <div className="text-xs text-muted-foreground space-y-2">
                <p className="font-medium">Supported formats:</p>
                <ul className="list-disc pl-4 space-y-1">
                  <li>Azure Resource Graph JSON exports</li>
                  <li>AWS CloudFormation templates</li>
                  <li>AWS Config resource exports</li>
                  <li>GCP Cloud Asset Inventory</li>
                </ul>
              </div>
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>

      {/* Footer */}
      <div className="p-3 border-t border-border/50 text-xs text-muted-foreground">
        {activeTab === 'files' ? (
          <span>{files.length} asset{files.length !== 1 ? 's' : ''}</span>
        ) : (
          <span>Import cloud resources to diagram</span>
        )}
      </div>
    </div>
  );
};

export default AssetManager;
