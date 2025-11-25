import { useState } from 'react';
import { Icon } from '@iconify/react';
import { azureServices, serviceCategories } from '@/data/azureServices';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';

interface ServicePaletteProps {
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  isChatOpen?: boolean;
  isIacOpen?: boolean;
}
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '@/components/ui/accordion';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const ServicePalette = ({ isCollapsed = false, onToggleCollapse, isChatOpen = false, isIacOpen = false }: ServicePaletteProps = {}) => {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const groupTemplates = [
    {
      id: 'management-group',
      label: 'Management Group',
      groupType: 'managementGroup',
      metadata: { scope: 'Tenant Root' },
    },
    {
      id: 'subscription',
      label: 'Subscription',
      groupType: 'subscription',
      metadata: { subscriptionId: '00000000-0000-0000-0000-000000000000' },
    },
    { id: 'landing-zone', label: 'Landing Zone', groupType: 'landingZone' },
    { id: 'azure-region', label: 'Azure Region', groupType: 'region' },
    { id: 'virtual-network', label: 'Virtual Network', groupType: 'virtualNetwork' },
    { id: 'subnet', label: 'Subnet', groupType: 'subnet' },
    { id: 'cluster', label: 'Cluster', groupType: 'cluster' },
    {
      id: 'policy-assignment',
      label: 'Policy Assignment',
      groupType: 'policyAssignment',
      metadata: { policyDefinitionId: '/providers/Microsoft.Authorization/policyDefinitions/...' },
    },
    {
      id: 'role-assignment',
      label: 'Role Assignment',
      groupType: 'roleAssignment',
      metadata: { roleDefinitionId: 'Reader', principalType: 'User' },
    },
  ];

    const filteredServices = azureServices.filter((service) => {
    const title = (service.title || '').toLowerCase();
    const desc = (service.description || '').toLowerCase();
    const matchesSearch = title.includes(search.toLowerCase()) || desc.includes(search.toLowerCase());
    const matchesCategory = !selectedCategory || service.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  const onDragStart = (event: React.DragEvent, service: typeof azureServices[0]) => {
    event.dataTransfer.setData(
      'application/reactflow',
      JSON.stringify({
        type: 'azure.service',
        data: {
          title: service.title,
          iconPath: service.iconPath,
          status: 'inactive',
          category: service.category,
        },
      }),
    );
    event.dataTransfer.effectAllowed = 'move';
  };

  const onGroupDragStart = (
    event: React.DragEvent,
    template: { id: string; label: string; groupType: string; metadata?: Record<string, unknown> }
  ) => {
    event.dataTransfer.setData(
      'application/reactflow',
      JSON.stringify({
        type: 'azure.group',
        data: {
          label: template.label,
          groupType: template.groupType,
          status: 'group',
          metadata: template.metadata,
        },
        style: {
          width: 420,
          height: 280,
        },
      })
    );
    event.dataTransfer.effectAllowed = 'move';
  };

  // Collapsed state - just show toggle button
  if (isCollapsed) {
    // Use fixed positioning when no side panels are open, absolute when they are
    const hasSidePanels = isChatOpen || isIacOpen;
    const buttonClassName = hasSidePanels
      ? "absolute -right-12 top-1/2 -translate-y-1/2 z-50 p-3 rounded-r-lg bg-primary/90 border border-l-0 border-primary/50 hover:bg-primary hover:border-primary transition-all shadow-2xl backdrop-blur-sm text-primary-foreground"
      : "fixed left-0 top-1/2 -translate-y-1/2 z-50 p-3 rounded-r-lg bg-primary/90 border border-l-0 border-primary/50 hover:bg-primary hover:border-primary transition-all shadow-2xl backdrop-blur-sm text-primary-foreground";
    
    return (
      <aside className="relative h-full w-0 flex-shrink-0 overflow-visible">
        <button
          onClick={onToggleCollapse}
          className={buttonClassName}
          title="Expand service palette"
          aria-label="Expand service palette"
          style={{ marginLeft: 0 }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 18l6-6-6-6" />
            <path d="M9 18l6-6-6-6" />
          </svg>
        </button>
      </aside>
    );
  }

  return (
    <aside className="glass-panel border-r border-border/50 w-64 flex flex-col min-h-0 relative">
      {onToggleCollapse && (
        <button
          onClick={onToggleCollapse}
          className="absolute -right-3 top-1/2 -translate-y-1/2 z-50 p-2 rounded-full bg-primary/90 border border-primary/50 hover:bg-primary hover:border-primary transition-all shadow-lg backdrop-blur-sm text-primary-foreground"
          title="Collapse service palette"
          aria-label="Collapse service palette"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
      )}
      <div className="p-4 border-b border-border/50">
        <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
          <Icon icon="mdi:view-grid-plus" className="text-primary" />
          Service Palette
        </h2>
        <Input
          type="text"
          placeholder="Search services..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-muted/30"
        />
      </div>

  <div className="p-2 border-b border-border/50">
        {/* Use a non-empty sentinel value for the "All" option because Radix Select
            does not allow an Item with an empty string value. We map the sentinel
            to null in state so filtering behavior remains the same. */}
        <Select
          value={selectedCategory ?? '__all__'}
          onValueChange={(v) => setSelectedCategory(v === '__all__' ? null : v)}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All</SelectItem>
            {serviceCategories.map((category) => (
              <SelectItem key={category} value={category}>
                {category}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Make the middle area scrollable so Group Templates and services list
          can both be scrolled to the end on small viewports */}
      <ScrollArea className="flex-1 p-2 space-y-2 min-h-0">
        <div className="border-b border-border/10 pb-2">
          <Accordion type="single" collapsible>
            <AccordionItem value="group-templates">
              <AccordionTrigger className="w-full text-sm font-semibold uppercase tracking-wide text-muted-foreground text-left">
                Group Templates
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-1">
                  {groupTemplates.map((template) => {
                    const iconMap: Record<string, string> = {
                      'management-group': 'mdi:account-group',
                      subscription: 'mdi:card-account-mail',
                      'landing-zone': 'mdi:map-outline',
                      'azure-region': 'mdi:earth',
                      'virtual-network': 'mdi:network',
                      subnet: 'mdi:subnet',
                      cluster: 'mdi:server-network',
                      'policy-assignment': 'mdi:shield-check',
                      'role-assignment': 'mdi:account-key',
                    };

                    const ic = iconMap[template.id] ?? 'mdi:shape-outline';

                    return (
                      <div
                        key={template.id}
                        draggable
                        onDragStart={(event) => onGroupDragStart(event, template)}
                        className="glass-hover p-3 rounded-lg cursor-move flex items-center justify-between group"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded bg-primary/10 group-hover:bg-primary/20 transition-colors">
                            <Icon icon={ic} className="h-5 w-5" />
                          </div>
                          <div className="flex flex-col">
                            <span className="text-sm font-medium text-foreground">
                              {template.label}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              Drag to create a container
                            </span>
                          </div>
                        </div>
                        <Icon icon="mdi:drag" className="text-muted-foreground" />
                      </div>
                    );
                  })}
                </div>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
  </div>

  <div className="space-y-1">
          {filteredServices.map((service) => (
            <div
              key={service.id}
              draggable
              onDragStart={(e) => onDragStart(e, service)}
              className="glass-hover p-3 rounded-lg cursor-move flex items-center gap-3 group"
            >
              <div className="p-2 rounded bg-primary/10 group-hover:bg-primary/20 transition-colors">
                <img
                  src={service.iconPath}
                  alt={service.title}
                  className="h-6 w-6 object-contain"
                  draggable={false}
                />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-sm font-medium truncate">{service.title}</h3>
                <p className="text-xs text-muted-foreground truncate">{service.description}</p>
              </div>
            </div>
          ))}
        </div>
      </ScrollArea>
    </aside>
  );
};

export default ServicePalette;
