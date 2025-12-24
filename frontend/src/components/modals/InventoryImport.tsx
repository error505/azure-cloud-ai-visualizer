/**
 * InventoryImport Component
 * 
 * Allows users to import cloud inventory JSON files from:
 * - Azure Resource Graph exports
 * - AWS CloudFormation/Config exports
 * - GCP Cloud Asset Inventory exports
 * 
 * Converts imported inventory to InfraGraph for visualization and analysis.
 */

import React, { useState, useCallback, useRef } from 'react';
import { Upload, FileJson, AlertCircle, CheckCircle, Loader2, Cloud, X } from 'lucide-react';
import type { CloudProvider, ReverseEngineeringResult, InfraGraph } from '@/types/infra';

interface InventoryImportProps {
  projectId: string;
  onImportComplete: (result: ReverseEngineeringResult) => void;
  onClose?: () => void;
}

interface ImportState {
  status: 'idle' | 'detecting' | 'importing' | 'success' | 'error';
  provider: CloudProvider | null;
  detectedProvider: CloudProvider | null;
  fileName: string | null;
  fileSize: number | null;
  progress: string;
  error: string | null;
  result: ReverseEngineeringResult | null;
}

const PROVIDER_LABELS: Record<CloudProvider, { label: string; color: string; icon: string }> = {
  azure: { label: 'Microsoft Azure', color: 'bg-blue-500', icon: '☁️' },
  aws: { label: 'Amazon Web Services', color: 'bg-orange-500', icon: '🔶' },
  gcp: { label: 'Google Cloud Platform', color: 'bg-red-500', icon: '🔴' },
  mixed: { label: 'Multi-Cloud', color: 'bg-purple-500', icon: '🌐' },
};

export function InventoryImport({ projectId, onImportComplete, onClose }: InventoryImportProps) {
  const [state, setState] = useState<ImportState>({
    status: 'idle',
    provider: null,
    detectedProvider: null,
    fileName: null,
    fileSize: null,
    progress: '',
    error: null,
    result: null,
  });
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [inventory, setInventory] = useState<Record<string, unknown> | null>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const detectProvider = useCallback(async (inventoryData: Record<string, unknown>) => {
    setState(s => ({ ...s, status: 'detecting', progress: 'Detecting cloud provider...' }));
    
    try {
      const response = await fetch('/api/reverse/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ inventory: inventoryData }),
      });
      
      if (!response.ok) {
        throw new Error(`Detection failed: ${response.statusText}`);
      }
      
      const data = await response.json();
      const detected = data.provider as CloudProvider | null;
      
      setState(s => ({
        ...s,
        status: 'idle',
        detectedProvider: detected,
        provider: detected,
        progress: detected ? `Detected: ${PROVIDER_LABELS[detected].label}` : 'Could not detect provider',
      }));
      
      return detected;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Detection failed';
      setState(s => ({ ...s, status: 'idle', progress: '', error: message }));
      return null;
    }
  }, []);

  const handleFileSelect = useCallback(async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    setState(s => ({
      ...s,
      fileName: file.name,
      fileSize: file.size,
      error: null,
      progress: 'Reading file...',
    }));
    
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      setInventory(parsed);
      
      // Auto-detect provider
      await detectProvider(parsed);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to parse JSON';
      setState(s => ({ ...s, status: 'error', error: `Invalid JSON: ${message}` }));
    }
  }, [detectProvider]);

  const handleDrop = useCallback(async (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    
    const file = event.dataTransfer.files[0];
    if (!file) return;
    
    if (!file.name.endsWith('.json')) {
      setState(s => ({ ...s, error: 'Please upload a JSON file' }));
      return;
    }
    
    setState(s => ({
      ...s,
      fileName: file.name,
      fileSize: file.size,
      error: null,
      progress: 'Reading file...',
    }));
    
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      setInventory(parsed);
      
      await detectProvider(parsed);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to parse JSON';
      setState(s => ({ ...s, status: 'error', error: `Invalid JSON: ${message}` }));
    }
  }, [detectProvider]);

  const handleDragOver = useCallback((event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
  }, []);

  const handleImport = useCallback(async () => {
    if (!inventory || !state.provider) {
      setState(s => ({ ...s, error: 'Please select a file and provider' }));
      return;
    }
    
    setState(s => ({ ...s, status: 'importing', progress: 'Importing inventory...' }));
    
    try {
      const response = await fetch('/api/reverse/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: projectId,
          provider: state.provider,
          inventory,
        }),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || response.statusText);
      }
      
      const result: ReverseEngineeringResult = await response.json();
      
      setState(s => ({
        ...s,
        status: 'success',
        result,
        progress: `Imported ${result.nodes_imported} nodes, ${result.edges_inferred} edges`,
      }));
      
      onImportComplete(result);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Import failed';
      setState(s => ({ ...s, status: 'error', error: message }));
    }
  }, [inventory, state.provider, projectId, onImportComplete]);

  const handleReset = useCallback(() => {
    setState({
      status: 'idle',
      provider: null,
      detectedProvider: null,
      fileName: null,
      fileSize: null,
      progress: '',
      error: null,
      result: null,
    });
    setInventory(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  return (
    <div className="bg-slate-800 rounded-lg p-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-500/20 rounded-lg">
            <Cloud className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white">Import Cloud Inventory</h2>
            <p className="text-sm text-slate-400">Upload JSON exports from Azure, AWS, or GCP</p>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-700 rounded-lg transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        )}
      </div>

      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
          ${state.status === 'error' ? 'border-red-500/50 bg-red-500/10' : 'border-slate-600 hover:border-blue-500/50 hover:bg-slate-700/50'}
        `}
        onClick={() => fileInputRef.current?.click()}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".json"
          onChange={handleFileSelect}
          className="hidden"
        />
        
        {state.fileName ? (
          <div className="flex items-center justify-center gap-3">
            <FileJson className="w-10 h-10 text-blue-400" />
            <div className="text-left">
              <p className="text-white font-medium">{state.fileName}</p>
              <p className="text-sm text-slate-400">
                {state.fileSize && formatFileSize(state.fileSize)}
              </p>
            </div>
          </div>
        ) : (
          <>
            <Upload className="w-12 h-12 text-slate-500 mx-auto mb-4" />
            <p className="text-slate-300 mb-2">
              Drop your inventory JSON file here, or click to browse
            </p>
            <p className="text-sm text-slate-500">
              Supports Azure Resource Graph, AWS CloudFormation, GCP Cloud Asset exports
            </p>
          </>
        )}
      </div>

      {/* Provider Selection */}
      {inventory && (
        <div className="mt-6">
          <label className="block text-sm font-medium text-slate-300 mb-3">
            Cloud Provider
            {state.detectedProvider && (
              <span className="ml-2 text-green-400 text-xs">
                (Auto-detected: {PROVIDER_LABELS[state.detectedProvider].label})
              </span>
            )}
          </label>
          <div className="grid grid-cols-3 gap-3">
            {(['azure', 'aws', 'gcp'] as CloudProvider[]).map((provider) => {
              const info = PROVIDER_LABELS[provider];
              const isSelected = state.provider === provider;
              const isDetected = state.detectedProvider === provider;
              
              return (
                <button
                  key={provider}
                  onClick={() => setState(s => ({ ...s, provider }))}
                  className={`
                    p-4 rounded-lg border-2 transition-all text-left
                    ${isSelected 
                      ? 'border-blue-500 bg-blue-500/20' 
                      : 'border-slate-600 hover:border-slate-500 bg-slate-700/50'
                    }
                    ${isDetected && !isSelected ? 'ring-2 ring-green-500/50' : ''}
                  `}
                >
                  <span className="text-2xl mb-2 block">{info.icon}</span>
                  <span className={`font-medium ${isSelected ? 'text-white' : 'text-slate-300'}`}>
                    {info.label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Status Messages */}
      {state.progress && state.status !== 'error' && (
        <div className="mt-4 flex items-center gap-2 text-blue-400">
          {state.status === 'importing' || state.status === 'detecting' ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : state.status === 'success' ? (
            <CheckCircle className="w-4 h-4 text-green-400" />
          ) : null}
          <span className={state.status === 'success' ? 'text-green-400' : ''}>
            {state.progress}
          </span>
        </div>
      )}

      {state.error && (
        <div className="mt-4 flex items-center gap-2 text-red-400 bg-red-500/10 p-3 rounded-lg">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span>{state.error}</span>
        </div>
      )}

      {/* Warnings */}
      {state.result?.warnings && state.result.warnings.length > 0 && (
        <div className="mt-4 bg-yellow-500/10 p-3 rounded-lg">
          <p className="text-yellow-400 font-medium mb-2">Warnings:</p>
          <ul className="text-sm text-yellow-300/80 space-y-1">
            {state.result.warnings.map((w, i) => (
              <li key={i}>• {w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Import Summary */}
      {state.result && state.status === 'success' && (
        <div className="mt-4 bg-green-500/10 p-4 rounded-lg">
          <h3 className="text-green-400 font-medium mb-3">Import Successful!</h3>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span className="text-slate-400">Nodes Imported:</span>
              <span className="ml-2 text-white font-medium">{state.result.nodes_imported}</span>
            </div>
            <div>
              <span className="text-slate-400">Edges Inferred:</span>
              <span className="ml-2 text-white font-medium">{state.result.edges_inferred}</span>
            </div>
            <div>
              <span className="text-slate-400">Provider:</span>
              <span className="ml-2 text-white font-medium">
                {PROVIDER_LABELS[state.result.source_provider as CloudProvider]?.label || state.result.source_provider}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="mt-6 flex gap-3 justify-end">
        {state.fileName && (
          <button
            onClick={handleReset}
            className="px-4 py-2 text-slate-300 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
          >
            Reset
          </button>
        )}
        <button
          onClick={handleImport}
          disabled={!inventory || !state.provider || state.status === 'importing'}
          className={`
            px-6 py-2 rounded-lg font-medium transition-all flex items-center gap-2
            ${inventory && state.provider && state.status !== 'importing'
              ? 'bg-blue-600 hover:bg-blue-500 text-white'
              : 'bg-slate-700 text-slate-500 cursor-not-allowed'
            }
          `}
        >
          {state.status === 'importing' && <Loader2 className="w-4 h-4 animate-spin" />}
          {state.status === 'success' ? 'Imported!' : 'Import Inventory'}
        </button>
      </div>
    </div>
  );
}

export default InventoryImport;
