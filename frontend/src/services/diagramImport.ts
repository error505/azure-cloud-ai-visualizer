import { DiagramAnalyzer, DiagramAnalysisResult } from '@/services/diagramAnalyzer';
import { ArchitectureParser, ParsedArchitecture, ParsedGroup, ParsedGroupType } from '@/services/architectureParser';
import { AzureService } from '@/data/azureServices';
import { awsServices } from '@/data/awsServices';
import AWS_SERVICE_TO_ICON_MAPPINGS from '@/services/awsServiceToIconMapper';

const normalizeKey = (value?: string | null): string => {
  if (!value) return '';
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
};

const normalizeName = (value?: string): string => {
  if (!value) return '';
  return value.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
};

const mapBackendGroupType = (type?: string, label?: string): ParsedGroupType => {
  const normalizedType = (type || '').toLowerCase();
  const normalizedLabel = (label || '').toLowerCase();

  const matches = (...keys: string[]) => keys.some((key) => normalizedType.includes(key) || normalizedLabel.includes(key));

  if (matches('region')) return 'region';
  if (matches('landing zone', 'landing_zone', 'landing-zone')) return 'landingZone';
  if (matches('resource group')) return 'resourceGroup';
  if (matches('virtual network', 'virtual_network', 'vnet')) return 'virtualNetwork';
  if (matches('subnet')) return 'subnet';
  if (matches('network security group', 'nsg')) return 'networkSecurityGroup';
  if (matches('cluster', 'aks')) return 'cluster';
  if (matches('security boundary')) return 'securityBoundary';
  if (matches('management group', 'tenant root')) return 'managementGroup';
  if (matches('subscription')) return 'subscription';
  if (matches('policy assignment', 'policy definition')) return 'policyAssignment';
  if (matches('role assignment', 'rbac')) return 'roleAssignment';

  return 'default';
};

const awsIconIdToService = new Map(awsServices.map((svc) => [svc.sourceIconId.toLowerCase(), svc]));
const awsTitleToService = new Map(awsServices.map((svc) => [svc.title.toLowerCase(), svc]));

const cloneAwsService = (base: AzureService, displayTitle: string): AzureService => ({
  ...base,
  id: `${base.id}-${normalizeKey(displayTitle) || 'detected'}`,
  title: displayTitle || base.title,
  description: `${displayTitle || base.title} (detected AWS service)`,
  provider: 'aws',
  badges: ['AWS'],
});

const resolveAwsService = (name: string): AzureService | null => {
  const normalized = normalizeName(name);
  if (!normalized) return null;

  const direct =
    AWS_SERVICE_TO_ICON_MAPPINGS[normalized] ||
    AWS_SERVICE_TO_ICON_MAPPINGS[normalized.replace(/^aws\s+/, '')] ||
    AWS_SERVICE_TO_ICON_MAPPINGS[normalized.replace(/^amazon\s+/, '')] ||
    Object.entries(AWS_SERVICE_TO_ICON_MAPPINGS).find(([key]) => normalized.includes(key))?.[1];

  if (direct) {
    const base = awsIconIdToService.get(direct.toLowerCase());
    if (base) {
      return cloneAwsService(base, name);
    }
  }

  const byTitle =
    awsTitleToService.get(normalized) ||
    Array.from(awsTitleToService.entries()).find(([title]) => normalized.includes(title))?.[1];
  if (byTitle) {
    return cloneAwsService(byTitle, name);
  }

  return null;
};

const resolveServiceFromName = (name?: string): AzureService | null => {
  if (!name || typeof name !== 'string') return null;
  const trimmed = name.trim();
  if (!trimmed) return null;

  const lower = trimmed.toLowerCase();
  const prefersAws = lower.includes('aws') || lower.includes('amazon');

  if (prefersAws) {
    const awsMatch = resolveAwsService(trimmed);
    if (awsMatch) {
      return awsMatch;
    }
  }

  const azureMatch = ArchitectureParser.findAzureServiceByName(trimmed);
  if (azureMatch) {
    return azureMatch;
  }

  return resolveAwsService(trimmed);
};

const buildArchitectureFromAnalysis = (analysisResult: DiagramAnalysisResult): ParsedArchitecture => {
  const parsedServices: AzureService[] = [];

  const ensureParsedService = (name?: string): AzureService | null => {
    if (!name || typeof name !== 'string') return null;
    const svc = resolveServiceFromName(name);
    if (svc) {
      const exists = parsedServices.find((s) => s.id === svc.id);
      if (!exists) {
        parsedServices.push(svc);
      }
      return svc;
    }
    return null;
  };

  (analysisResult.services || []).forEach((serviceName) => {
    const svc = ensureParsedService(serviceName);
    if (!svc && serviceName) {
      console.warn('[DiagramImport] Unable to map detected service name', serviceName);
    }
  });

  const rawGroups = analysisResult.groups ?? [];
  const parsedGroups: ParsedGroup[] = [];
  const groupKeyToId = new Map<string, string>();
  const nestedGroupLinks: Array<{ parentId: string; childKey: string }> = [];

  rawGroups.forEach((group, index) => {
    const label = group.label || group.id || `Group ${index + 1}`;
    const resolvedId = `group-${index}-${normalizeKey(label) || index.toString()}`;

    const members: string[] = [];
    (group.members || []).forEach((memberName) => {
      const svc = ensureParsedService(memberName);
      if (svc) {
        members.push(svc.id);
        return;
      }
      const childKey = normalizeKey(memberName);
      if (childKey) {
        nestedGroupLinks.push({ parentId: resolvedId, childKey });
      }
    });

    const parsedGroup: ParsedGroup = {
      id: resolvedId,
      label,
      type: mapBackendGroupType(group.group_type, label),
      members,
      metadata: group.metadata,
      sourceServiceId: undefined,
    };

    parsedGroups.push(parsedGroup);

    [group.id, label].forEach((key) => {
      const normalizedKey = normalizeKey(key);
      if (normalizedKey) {
        groupKeyToId.set(normalizedKey, resolvedId);
      }
    });
  });

  rawGroups.forEach((group, index) => {
    const parsedGroup = parsedGroups[index];
    if (!parsedGroup) return;
    const parentKey = normalizeKey(group.parent_id);
    if (parentKey) {
      const parentId = groupKeyToId.get(parentKey);
      if (parentId && parentId !== parsedGroup.id) {
        parsedGroup.parentId = parentId;
      }
    }
  });

  nestedGroupLinks.forEach(({ parentId, childKey }) => {
    const childId = groupKeyToId.get(childKey);
    if (!childId || childId === parentId) return;
    const childGroup = parsedGroups.find((group) => group.id === childId);
    const parentGroup = parsedGroups.find((group) => group.id === parentId);
    if (!childGroup || !parentGroup) return;
    childGroup.parentId = childGroup.parentId ?? parentId;
    if (!parentGroup.members.includes(childId)) {
      parentGroup.members.push(childId);
    }
  });

  parsedGroups.forEach((group) => {
    if (group.parentId) {
      const parentGroup = parsedGroups.find((candidate) => candidate.id === group.parentId);
      if (parentGroup && !parentGroup.members.includes(group.id)) {
        parentGroup.members.push(group.id);
      }
    }
    group.members = Array.from(new Set(group.members));
  });

  const mappedConnections = (analysisResult.connections || [])
    .map((conn) => {
      const fromService = ensureParsedService(conn.from_service) || undefined;
      const toService = ensureParsedService(conn.to_service) || undefined;

      if (!fromService || !toService) {
        console.warn('[DiagramImport] Dropping connection with unmapped endpoint(s)', conn);
        return null;
      }

      return {
        from: fromService.id,
        to: toService.id,
        label: conn.label || 'connection',
      };
    })
    .filter((conn): conn is { from: string; to: string; label?: string } => !!conn);

  return {
    services: parsedServices,
    connections: mappedConnections,
    groups: parsedGroups,
    layout: 'grid',
  };
};

export const importDiagramImage = async (file: File): Promise<{ architecture: ParsedArchitecture; analysis: DiagramAnalysisResult }> => {
  const analysis = await DiagramAnalyzer.analyzeImage(file);
  const architecture = buildArchitectureFromAnalysis(analysis);
  return { architecture, analysis };
};

export const hasMeaningfulAwsCoverage = (architecture: ParsedArchitecture): boolean => {
  const awsServiceCount = architecture.services.filter((svc) => {
    const provider = (svc.provider || '').toLowerCase();
    return provider === 'aws' || svc.id.startsWith('aws:');
  }).length;

  return awsServiceCount >= 4;
};

export const hasMeaningfulGcpCoverage = (architecture: ParsedArchitecture): boolean => {
  const gcpServiceCount = architecture.services.filter((svc) => {
    const provider = (svc.provider || '').toLowerCase();
    return provider === 'gcp' || svc.id.startsWith('gcp:');
  }).length;

  return gcpServiceCount >= 4;
};

export const detectPrimaryProvider = (architecture: ParsedArchitecture): 'azure' | 'aws' | 'gcp' | 'mixed' => {
  let azureCount = 0;
  let awsCount = 0;
  let gcpCount = 0;

  architecture.services.forEach((svc) => {
    const provider = (svc.provider || '').toLowerCase();
    if (provider === 'azure' || (!provider && !svc.id.startsWith('aws:') && !svc.id.startsWith('gcp:'))) {
      azureCount++;
    } else if (provider === 'aws' || svc.id.startsWith('aws:')) {
      awsCount++;
    } else if (provider === 'gcp' || svc.id.startsWith('gcp:')) {
      gcpCount++;
    }
  });

  const total = azureCount + awsCount + gcpCount;
  if (total === 0) return 'azure';

  // If one provider has >70% of services, consider it primary
  if (azureCount / total > 0.7) return 'azure';
  if (awsCount / total > 0.7) return 'aws';
  if (gcpCount / total > 0.7) return 'gcp';

  return 'mixed';
};
