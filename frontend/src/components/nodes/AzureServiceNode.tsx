import { memo } from 'react';
import { Handle, Position, NodeProps } from '@xyflow/react';
import { Icon } from '@iconify/react';

interface AzureServiceData {
  title: string;
  subtitle?: string;
  icon?: string;
  iconPath?: string;
  status?: 'active' | 'inactive' | 'warning' | 'error';
  badges?: string[];
  region?: string;
  animationProfile?: {
    effect: 'pulse' | 'glow' | 'rotate' | 'none';
    speed: number;
    color?: string;
  };
  // Optional Azure-like metadata
  provisioningState?: string;
  tags?: Record<string, string>;
  endpoints?: { type: string; url: string }[];
  sku?: string;
  resourceType?: string;
}

const AzureServiceNode = ({ data, selected }: NodeProps) => {
  const nodeData = data as unknown as AzureServiceData;
  
  const statusColors = {
    active: 'border-green-500/50 shadow-green-500/20',
    inactive: 'border-border shadow-muted/10',
    warning: 'border-yellow-500/50 shadow-yellow-500/20',
    error: 'border-destructive/50 shadow-destructive/20',
  };

  const statusColor = statusColors[nodeData.status || 'inactive'];
  const isAnimated = nodeData.animationProfile?.effect !== 'none';

  return (
    <div 
      className={`
        glass-panel rounded-2xl p-4 min-w-[140px] max-w-[180px]
        transition-all duration-300
        ${selected ? 'ring-2 ring-primary glow-primary scale-105' : ''}
        ${statusColor}
        hover:shadow-xl hover:scale-102 hover:border-primary/40
        ${isAnimated && nodeData.animationProfile?.effect === 'pulse' ? 'animate-pulse' : ''}
        ${isAnimated && nodeData.animationProfile?.effect === 'glow' ? 'glow-accent' : ''}
      `}
      data-node-id={nodeData.title}
    >
      {/* Top handles */}
      <Handle
        type="target"
        position={Position.Top}
        id="top-target"
        className="!bg-primary !w-3 !h-3 !border-2 !border-background transition-all hover:!w-4 hover:!h-4"
      />
      <Handle
        type="source"
        position={Position.Top}
        id="top-source"
        className="!bg-primary/80 !w-3 !h-3 !border-2 !border-background transition-all hover:!w-4 hover:!h-4"
      />
      
      <div className="flex flex-col items-center gap-3">
        {/* Icon Container */}
        <div className={`
          p-4 rounded-xl transition-all duration-300
          ${nodeData.status === 'active' 
            ? 'bg-primary/20 shadow-lg shadow-primary/20' 
            : 'bg-muted/20'
          }
          ${isAnimated && nodeData.animationProfile?.effect === 'rotate' ? 'animate-spin-slow' : ''}
        `}>
          {nodeData.iconPath ? (
            <img
              src={nodeData.iconPath}
              alt={nodeData.title}
              className="h-12 w-12 object-contain transition-transform duration-300"
            />
          ) : nodeData.icon ? (
            <Icon 
              icon={nodeData.icon} 
              className={`text-4xl transition-colors duration-300 ${
                nodeData.status === 'active' ? 'text-primary' : 'text-muted-foreground'
              }`}
            />
          ) : (
            <Icon 
              icon="mdi:cube-outline" 
              className={`text-4xl transition-colors duration-300 ${
                nodeData.status === 'active' ? 'text-primary' : 'text-muted-foreground'
              }`}
            />
          )}
        </div>
        
        {/* Labels */}
        <div className="text-center space-y-1 w-full">
          <h3 className="font-semibold text-sm text-foreground leading-tight px-1">
            {nodeData.title}
          </h3>
          {nodeData.subtitle && (
            <p className="text-xs text-muted-foreground">{nodeData.subtitle}</p>
          )}
          {nodeData.region && (
            <p className="text-xs text-accent font-medium">{nodeData.region}</p>
          )}
        </div>

        {/* Badges */}
        {nodeData.badges && nodeData.badges.length > 0 && (
          <div className="flex gap-1 flex-wrap justify-center w-full">
            {nodeData.badges.map((badge, i) => (
              <span 
                key={i} 
                className="px-2 py-0.5 bg-accent/20 text-accent text-[10px] rounded-full font-medium border border-accent/30"
              >
                {badge}
              </span>
            ))}
          </div>
        )}

        {/* Provisioning State */}
        {nodeData.provisioningState && (
          <div className="mt-2">
            <span className="px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted/10 border border-muted/20">
              {nodeData.provisioningState}
            </span>
          </div>
        )}

        {/* Tags */}
        {nodeData.tags && Object.keys(nodeData.tags).length > 0 && (
          <div className="flex gap-1 flex-wrap justify-center w-full mt-2">
            {Object.entries(nodeData.tags).map(([k, v]) => (
              <span key={k} className="px-2 py-0.5 bg-muted/10 text-sm rounded-full text-muted-foreground border border-muted/20">
                {k}: {v}
              </span>
            ))}
          </div>
        )}

        {/* Endpoints */}
        {nodeData.endpoints && nodeData.endpoints.length > 0 && (
          <div className="w-full mt-2 text-xs text-muted-foreground">
            {nodeData.endpoints.map((ep, i) => (
              <div key={i} className="truncate">{ep.type}: {ep.url}</div>
            ))}
          </div>
        )}
      </div>

      {/* Bottom handles */}
      <Handle
        type="target"
        position={Position.Bottom}
        id="bottom-target"
        className="!bg-primary !w-3 !h-3 !border-2 !border-background transition-all hover:!w-4 hover:!h-4"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom-source"
        className="!bg-primary/80 !w-3 !h-3 !border-2 !border-background transition-all hover:!w-4 hover:!h-4"
      />

      {/* Left / Right handles to allow more connection points */}
      <Handle
        type="target"
        position={Position.Left}
        id="left-target"
        className="!bg-primary !w-3 !h-3 !border-2 !border-background transition-all hover:!w-4 hover:!h-4"
      />
      <Handle
        type="source"
        position={Position.Left}
        id="left-source"
        className="!bg-primary/80 !w-3 !h-3 !border-2 !border-background transition-all hover:!w-4 hover:!h-4"
      />
      <Handle
        type="target"
        position={Position.Right}
        id="right-target"
        className="!bg-primary !w-3 !h-3 !border-2 !border-background transition-all hover:!w-4 hover:!h-4"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right-source"
        className="!bg-primary/80 !w-3 !h-3 !border-2 !border-background transition-all hover:!w-4 hover:!h-4"
      />
    </div>
  );
};

export default memo(AzureServiceNode);
