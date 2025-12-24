import { useEffect, useMemo, useState } from 'react';
import { Icon } from '@iconify/react';
import { azureServices, serviceCategories } from '@/data/azureServices';
import { awsServices, awsServiceCategories } from '@/data/awsServices';
import gcpServicesDefault, { gcpServiceCategories } from '@/data/gcpServices';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
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

type AzurePaletteService = (typeof azureServices)[number];
type AwsPaletteService = (typeof awsServices)[number];
type ProviderFilter = 'all' | 'azure' | 'aws' | 'gcp';

const ServicePalette = () => {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [providerFilter, setProviderFilter] = useState<ProviderFilter>('azure');

  useEffect(() => {
    setSelectedCategory(null);
  }, [providerFilter]);

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

  const categoryOptions = useMemo(() => {
    if (providerFilter === 'azure') return serviceCategories;
    if (providerFilter === 'aws') return awsServiceCategories;
    if (providerFilter === 'gcp') return gcpServiceCategories;
    return [];
  }, [providerFilter]);

  const matchesSearch = (title: string, description: string) => {
    const needle = search.trim().toLowerCase();
    if (!needle) return true;
    return title.toLowerCase().includes(needle) || description.toLowerCase().includes(needle);
  };

  const matchesCategoryFilter = (category: string, serviceProvider: ProviderFilter) => {
    if (!selectedCategory || providerFilter === 'all') {
      return true;
    }
    return providerFilter === serviceProvider && category === selectedCategory;
  };

  const shouldShowAzure = providerFilter === 'all' || providerFilter === 'azure';
  const shouldShowAws = providerFilter === 'all' || providerFilter === 'aws';
  const shouldShowGcp = providerFilter === 'all' || providerFilter === 'gcp';

  const filteredAzureServices = shouldShowAzure
    ? azureServices.filter((service) => matchesSearch(service.title, service.description) && matchesCategoryFilter(service.category, 'azure'))
    : [];

  const filteredAwsServices = shouldShowAws
    ? awsServices.filter((service) => matchesSearch(service.title, service.description) && matchesCategoryFilter(service.category, 'aws'))
    : [];

  const filteredGcpServices = shouldShowGcp
    ? gcpServicesDefault.filter((service) => matchesSearch(service.title, service.description) && matchesCategoryFilter(service.category, 'gcp'))
    : [];

  const onDragStart = (
    event: React.DragEvent,
    service: AzurePaletteService | AwsPaletteService,
    provider: 'azure' | 'aws',
  ) => {
    event.dataTransfer.setData(
      'application/reactflow',
      JSON.stringify({
        type: 'azure.service',
        data: {
          title: service.title,
          iconPath: service.iconPath,
          status: 'inactive',
          category: service.category,
          provider,
          ...(provider === 'aws'
            ? { awsServiceId: (service as AwsPaletteService).sourceIconId, awsTitle: service.title }
            : {}),
        },
      }),
    );
    event.dataTransfer.effectAllowed = 'move';
  };

  // GCP drag helper
  const onDragStartGcp = (event: React.DragEvent, service: (typeof gcpServices)[number]) => {
    event.dataTransfer.setData(
      'application/reactflow',
      JSON.stringify({
        type: 'azure.service',
        data: {
          title: service.title,
          iconPath: service.iconPath,
          status: 'inactive',
          category: service.category,
          provider: 'gcp',
          gcpServiceId: service.id,
          gcpTitle: service.title,
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

  return (
    <aside className="glass-panel border-r border-border/50 w-64 flex flex-col min-h-0">
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

      <div className="p-2 border-b border-border/50 space-y-2">
        <Select value={providerFilter} onValueChange={(value) => setProviderFilter(value as ProviderFilter)}>
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Provider" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="azure">Azure</SelectItem>
            <SelectItem value="gcp">GCP</SelectItem>
            <SelectItem value="aws">AWS</SelectItem>
            <SelectItem value="all">All providers</SelectItem>
          </SelectContent>
        </Select>

        {/* Use a non-empty sentinel value for the "All" option because Radix Select
            does not allow an Item with an empty string value. We map the sentinel
            to null in state so filtering behavior remains the same. */}
        <Select
          disabled={providerFilter === 'all'}
          value={selectedCategory ?? '__all__'}
          onValueChange={(v) => setSelectedCategory(v === '__all__' ? null : v)}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All</SelectItem>
            {categoryOptions.map((category) => (
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

        <Accordion type="multiple" className="space-y-2" defaultValue={['azure-services']}>
          {shouldShowAzure && (
            <AccordionItem value="azure-services">
              <AccordionTrigger className="w-full text-sm font-semibold uppercase tracking-wide text-muted-foreground text-left">
                Azure Services ({filteredAzureServices.length})
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-1">
                  {filteredAzureServices.length === 0 && (
                    <div className="text-xs text-muted-foreground px-2 py-3">
                      No Azure services match your filters.
                    </div>
                  )}
                  {filteredAzureServices.map((service) => (
                    <div
                      key={service.id}
                      draggable
                      onDragStart={(e) => onDragStart(e, service, 'azure')}
                      className="glass-hover p-3 rounded-lg cursor-move flex items-center gap-3 group"
                    >
                      <div className="p-2 rounded bg-primary/10 group-hover:bg-primary/20 transition-colors">
                        <img src={service.iconPath} alt={service.title} className="h-6 w-6 object-contain" draggable={false} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-medium truncate">{service.title}</h3>
                        <p className="text-xs text-muted-foreground truncate">{service.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          )}

          {shouldShowAws && (
            <AccordionItem value="aws-services">
              <AccordionTrigger className="w-full text-sm font-semibold uppercase tracking-wide text-muted-foreground text-left">
                AWS Services ({filteredAwsServices.length})
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-1">
                  {filteredAwsServices.length === 0 && (
                    <div className="text-xs text-muted-foreground px-2 py-3">
                      No AWS services match your filters.
                    </div>
                  )}
                  {filteredAwsServices.map((service) => (
                    <div
                      key={service.id}
                      draggable
                      onDragStart={(e) => onDragStart(e, service, 'aws')}
                      className="glass-hover p-3 rounded-lg cursor-move flex items-center gap-3 group"
                    >
                      <div className="p-2 rounded bg-primary/10 group-hover:bg-primary/20 transition-colors">
                        <img src={service.iconPath} alt={service.title} className="h-6 w-6 object-contain" draggable={false} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-medium truncate">{service.title}</h3>
                        <p className="text-xs text-muted-foreground truncate">{service.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          )}
      {shouldShowGcp && (
        <AccordionItem value="gcp-services">
          <AccordionTrigger className="w-full text-sm font-semibold uppercase tracking-wide text-muted-foreground text-left">
            GCP Services ({filteredGcpServices.length})
          </AccordionTrigger>
          <AccordionContent>
            <div className="space-y-1">
              {filteredGcpServices.length === 0 && (
                <div className="text-xs text-muted-foreground px-2 py-3">
                  No GCP services match your filters.
                </div>
              )}
              {filteredGcpServices.map((service) => (
                <div
                  key={service.id}
                  draggable
                  onDragStart={(e) => onDragStartGcp(e, service)}
                  className="glass-hover p-3 rounded-lg cursor-move flex items-center gap-3 group"
                >
                  <div className="p-2 rounded bg-primary/10 group-hover:bg-primary/20 transition-colors">
                    <img src={service.iconPath} alt={service.title} className="h-6 w-6 object-contain" draggable={false} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-medium truncate">{service.title}</h3>
                    <p className="text-xs text-muted-foreground truncate">{service.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </AccordionContent>
        </AccordionItem>
      )}
        </Accordion>
      </ScrollArea>
    </aside>
  );
};

export default ServicePalette;
