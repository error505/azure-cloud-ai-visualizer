import { memo } from 'react';
import { NodeResizer } from '@xyflow/react';
import type { NodeProps } from '@xyflow/react';

type GroupAccent =
  | 'region'
  | 'landingZone'
  | 'virtualNetwork'
  | 'subnet'
  | 'cluster'
  | 'resourceGroup'
  | 'networkSecurityGroup'
  | 'securityBoundary'
  | 'managementGroup'
  | 'subscription'
  | 'policyAssignment'
  | 'roleAssignment'
  | 'default';

interface AzureGroupNodeData {
  label: string;
  groupType?: GroupAccent;
  metadata?: Record<string, unknown>;
  status?: string;
}

const groupAccentClasses: Record<GroupAccent, string> = {
  region: 'border-sky-500/60 bg-sky-500/10',
  landingZone: 'border-emerald-500/60 bg-emerald-500/10',
  virtualNetwork: 'border-indigo-500/60 bg-indigo-500/10',
  subnet: 'border-purple-500/60 bg-purple-500/10',
  cluster: 'border-orange-500/60 bg-orange-500/10',
  resourceGroup: 'border-amber-500/60 bg-amber-500/10',
  networkSecurityGroup: 'border-rose-500/60 bg-rose-500/10',
  securityBoundary: 'border-fuchsia-500/60 bg-fuchsia-500/10',
  managementGroup: 'border-slate-500/60 bg-slate-500/10',
  subscription: 'border-teal-500/60 bg-teal-500/10',
  policyAssignment: 'border-amber-500/60 bg-amber-500/10',
  roleAssignment: 'border-emerald-600/60 bg-emerald-600/10',
  default: 'border-border/60 bg-muted/10',
};

const friendlyTypeLabel: Record<GroupAccent, string> = {
  region: 'Azure Region',
  landingZone: 'Landing Zone',
  virtualNetwork: 'Virtual Network',
  subnet: 'Subnet',
  cluster: 'Cluster',
  resourceGroup: 'Resource Group',
  networkSecurityGroup: 'Network Security Group',
  securityBoundary: 'Security Boundary',
  managementGroup: 'Management Group',
  subscription: 'Subscription',
  policyAssignment: 'Policy Assignment',
  roleAssignment: 'Role Assignment',
  default: 'Grouped Resources',
};

const AzureGroupNode = ({ data, selected }: NodeProps) => {
  const nodeData = (data || {}) as AzureGroupNodeData;
  const groupType = (nodeData.groupType as GroupAccent) || 'default';
  const accent = groupAccentClasses[groupType] || groupAccentClasses.default;

  return (
    <div
      className={`
        relative h-full w-full rounded-3xl border-2 border-dashed
        ${accent}
        transition-shadow duration-300
        ${selected ? 'shadow-xl shadow-primary/30 ring-2 ring-primary/30' : 'shadow-sm shadow-black/5'}
      `}
      data-node-type="azure-group"
    >
      <NodeResizer
        minWidth={320}
        minHeight={220}
        handleClassName="group-node-resizer"
        lineClassName="group-node-resize-line"
        isVisible={selected}
        keepAspectRatio={false}
      />
      <div className="absolute top-4 left-5 flex flex-col gap-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {friendlyTypeLabel[groupType]}
        </span>
        <h3 className="text-lg font-semibold text-foreground leading-tight">
          {nodeData.label || 'Grouped Resources'}
        </h3>
      </div>
      {nodeData.metadata && (
        <div className="absolute top-4 right-5 text-right space-y-1 text-xs text-muted-foreground/80">
          {Object.entries(nodeData.metadata)
            .filter(([, value]) => {
              if (value === undefined || value === null) return false;
              if (typeof value === 'string') return value.trim().length > 0;
              if (Array.isArray(value)) return value.length > 0;
              if (typeof value === 'object') return Object.keys(value || {}).length > 0;
              return true;
            })
            .slice(0, 3)
            .map(([key, value]) => (
              <div key={key} className="flex flex-col">
                <span className="uppercase tracking-wide">{key}</span>
                <span className="font-medium text-foreground/80">
                  {typeof value === 'string' || typeof value === 'number'
                    ? value
                    : JSON.stringify(value)}
                </span>
              </div>
            ))}
        </div>
      )}
      <div className="absolute inset-x-5 bottom-4 flex items-center justify-between text-[11px] text-muted-foreground uppercase tracking-wider">
        <span>Drag resources here</span>
        <span>Resize corners to fit</span>
      </div>
    </div>
  );
};

export default memo(AzureGroupNode);
