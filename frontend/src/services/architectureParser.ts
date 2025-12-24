/**
 * Service to parse AI chat responses and extract Azure architecture components
 */

import { Node } from '@xyflow/react';
import { AzureService, azureServices } from '@/data/azureServices';
import iconIndex from '@/data/azureIconIndex.json';
import { ParsedGroupType } from './types';
import {GROUP_TITLE_KEYWORDS} from './groupTitleKeywords';
import {SERVICE_TO_ICON_MAPPINGS} from './serviceToIconMapper';
import AWS_SERVICE_TO_ICON_MAPPINGS from './awsServiceToIconMapper';
import awsIconIndex from '@/data/awsIconIndex.json';
import GCP_SERVICE_TO_ICON_MAPPINGS from './gcpServiceToIconMapper';
import gcpIconIndex from '@/data/gcpIconIndex.json';
import { patterns, connectionPatterns, bicepResourcePatterns, serviceNamePatterns } from './patterns';

type IconEntry = { title?: string; file?: string; id?: string };
type IconCategory = { icons?: IconEntry[] };
type IconIndex = { categories?: IconCategory[] };
import { BicepResourceMapper, BICEP_RESOURCE_MAPPINGS } from './bicepResourceMapper';

export interface ServiceLayoutHint {
  x: number;
  y: number;
  width?: number;
  height?: number;
}

export interface ParsedArchitecture {
  services: AzureService[];
  connections: { from: string; to: string; label?: string }[];
  layout: 'horizontal' | 'vertical' | 'grid' | 'manual';
  groups?: ParsedGroup[];
  bicepResources?: { resourceType: string; resourceName: string }[];
  serviceLayouts?: Record<string, ServiceLayoutHint>;
}


export interface ParsedGroup {
  id: string;
  label: string;
  type: ParsedGroupType;
  members: string[];
  parentId?: string;
  metadata?: Record<string, unknown>;
  sourceServiceId?: string;
}

export class ArchitectureParser {
  /**
   * Parse AI response and extract Azure services and their relationships
   */
  private static extractDiagramJsonBlock(response: string): string | null {
    if (!response) return null;
    const fencedMatch = response.match(/Diagram JSON\s*```json\s*([\s\S]*?)```/i);
    if (fencedMatch?.[1]) {
      return fencedMatch[1].trim();
    }

    const markerIndex = response.toLowerCase().indexOf('diagram json');
    if (markerIndex === -1) {
      return null;
    }
    const braceStart = response.indexOf('{', markerIndex);
    if (braceStart === -1) {
      return null;
    }
    let depth = 0;
    for (let i = braceStart; i < response.length; i += 1) {
      const char = response[i];
      if (char === '{') {
        depth += 1;
      } else if (char === '}') {
        depth -= 1;
        if (depth === 0) {
          return response.slice(braceStart, i + 1);
        }
      }
    }
    return null;
  }

  private static convertStructuredDiagram(data: unknown): ParsedArchitecture | null {
    if (!data || typeof data !== 'object') {
      return null;
    }

    const diagram = data as Record<string, unknown>;
    const rawServices = Array.isArray(diagram.services) ? diagram.services : [];
    const rawGroups = Array.isArray(diagram.groups) ? diagram.groups : [];
    const rawConnections = Array.isArray(diagram.connections) ? diagram.connections : [];

    const toStringSafe = (value: unknown): string | undefined => {
      if (typeof value === 'string') {
        const trimmed = value.trim();
        return trimmed.length > 0 ? trimmed : undefined;
      }
      return undefined;
    };

    const toSlug = (value: string): string =>
      value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

    const services: AzureService[] = [];
    const serviceLayouts: Record<string, ServiceLayoutHint> = {};
    const groups: ParsedGroup[] = [];
    const connections: { from: string; to: string; label?: string }[] = [];

    const groupMap = new Map<string, ParsedGroup>();
    const groupMembers = new Map<string, Set<string>>();
    const groupIdsFromJson = new Set<string>(
      rawGroups
        .map((entry) => (entry && typeof entry === 'object' ? toStringSafe((entry as Record<string, unknown>).id) : undefined))
        .filter((id): id is string => !!id)
    );

    const resolveAzureServiceByIdOrTitle = (id?: string, title?: string): AzureService | null => {
      const idMatch = id ? azureServices.find((service) => service.id === id) : undefined;
      if (idMatch) {
        return { ...idMatch };
      }
      if (title) {
        const titleMatch = this.findAzureServiceByName(title);
        if (titleMatch) {
          return { ...titleMatch };
        }
      }
      return null;
    };

    rawGroups.forEach((entry) => {
      if (!entry || typeof entry !== 'object') {
        return;
      }
      const groupEntry = entry as Record<string, unknown>;
      const groupId = toStringSafe(groupEntry.id) || `group:${toSlug(toStringSafe(groupEntry.label) || toStringSafe(groupEntry.title) || 'group')}`;
      const label = toStringSafe(groupEntry.label) || toStringSafe(groupEntry.title) || groupId;
      if (!groupId || !label) {
        return;
      }

      const detectedType =
        toStringSafe(groupEntry.type) ||
        toStringSafe(groupEntry.groupType) ||
        undefined;
      const groupType =
        (detectedType ? this.detectGroupType(detectedType) : null) ||
        this.detectGroupType(label) ||
        'default';

      const matchedService = resolveAzureServiceByIdOrTitle(groupId, label);
      const metadata = matchedService
        ? {
            category: matchedService.category,
            iconPath: matchedService.iconPath,
          }
        : undefined;

      const parsedGroup: ParsedGroup = {
        id: groupId,
        label,
        type: groupType,
        members: [],
        parentId: toStringSafe(groupEntry.parentId ?? (groupEntry as Record<string, unknown>).parent_id) ?? undefined,
        metadata,
        sourceServiceId: matchedService?.id,
      };

      const rawMembers = groupEntry.members;
      if (Array.isArray(rawMembers)) {
        const memberSet = new Set<string>();
        rawMembers.forEach((member) => {
          const memberId = toStringSafe(member);
          if (memberId) {
            memberSet.add(memberId);
          }
        });
        groupMembers.set(groupId, memberSet);
      } else {
        groupMembers.set(groupId, new Set<string>());
      }

      groups.push(parsedGroup);
      groupMap.set(groupId, parsedGroup);
    });

    const servicesByTitle = new Map<string, string>();
    const servicesById = new Map<string, AzureService>();
    const serviceGroupHints = new Map<string, Set<string>>();
    const autoCreatedGroups = new Set<string>();

    const registerServiceGroup = (serviceId: string, groupId: string) => {
      if (!groupId || groupId === serviceId) {
        return;
      }
      if (!serviceGroupHints.has(serviceId)) {
        serviceGroupHints.set(serviceId, new Set<string>());
      }
      serviceGroupHints.get(serviceId)!.add(groupId);
    };

    const ensureContainerGroup = (service: AzureService, potentialParents: string[]) => {
      const groupId = service.id;
      let containerGroup = groupMap.get(groupId);
      if (!containerGroup) {
        containerGroup = {
          id: groupId,
          label: service.title || groupId,
          type: this.detectGroupType(service.title || groupId) ?? 'default',
          members: [],
          parentId: undefined,
          metadata: {
            category: service.category,
            iconPath: service.iconPath,
          },
          sourceServiceId: service.id,
        };
        groups.push(containerGroup);
        groupMap.set(groupId, containerGroup);
        autoCreatedGroups.add(groupId);
      } else {
        if (!containerGroup.metadata) {
          containerGroup.metadata = {
            category: service.category,
            iconPath: service.iconPath,
          };
        }
        if (!containerGroup.sourceServiceId) {
          containerGroup.sourceServiceId = service.id;
        }
      }

      const validParents = potentialParents.filter((parentId) => parentId && parentId !== groupId);
      if (validParents.length && !containerGroup.parentId) {
        containerGroup.parentId = validParents[0];
      }

      validParents.forEach((parentId) => registerServiceGroup(groupId, parentId));
    };

    rawServices.forEach((entry) => {
      if (!entry) {
        return;
      }

      // Support simple string entries like ["Azure Front Door", "Azure Firewall"]
      const serviceEntry: Record<string, unknown> =
        typeof entry === 'string'
          ? { title: entry }
          : typeof entry === 'object'
          ? (entry as Record<string, unknown>)
          : {};
      if (Object.keys(serviceEntry).length === 0) {
        return;
      }
      const explicitId = toStringSafe(serviceEntry.id);
      const title = toStringSafe(serviceEntry.title);
      const pendingGroupIds: string[] = [];
      const position = serviceEntry.position;
      const size = serviceEntry.data;
      const layoutHint: Partial<ServiceLayoutHint> = {};
      if (position && typeof position === 'object') {
        const posObj = position as Record<string, unknown>;
        const x = typeof posObj.x === 'number' ? posObj.x : undefined;
        const y = typeof posObj.y === 'number' ? posObj.y : undefined;
        if (typeof x === 'number' && typeof y === 'number') {
          layoutHint.x = x;
          layoutHint.y = y;
        }
      }
      if (size && typeof size === 'object') {
        const dimObj = size as Record<string, unknown>;
        const width = typeof dimObj.width === 'number' ? dimObj.width : undefined;
        const height = typeof dimObj.height === 'number' ? dimObj.height : undefined;
        if (typeof width === 'number') {
          layoutHint.width = width;
        }
        if (typeof height === 'number') {
          layoutHint.height = height;
        }
      }
      const rawGroupIds = serviceEntry.groupIds ?? serviceEntry.groupId ?? serviceEntry.groups;
      if (Array.isArray(rawGroupIds)) {
        rawGroupIds.forEach((groupIdCandidate) => {
          const groupId = toStringSafe(groupIdCandidate);
          if (groupId) {
            pendingGroupIds.push(groupId);
          }
        });
      } else if (rawGroupIds) {
        const groupId = toStringSafe(rawGroupIds);
        if (groupId) {
          pendingGroupIds.push(groupId);
        }
      }

      const uniqueGroupIds = Array.from(new Set(pendingGroupIds));
      const resolvedService = resolveAzureServiceByIdOrTitle(explicitId, title);

      const isContainer = (candidateId?: string, labelHint?: string) => {
        if (!candidateId) return false;
        const group = groupMap.get(candidateId);
        if (group && group.type !== 'default') {
          return true;
        }
        const detected = this.detectGroupType(labelHint || candidateId);
        return !!detected;
      };

      if (!resolvedService) {
        const fallbackTitle = title || explicitId || 'AI Detected Service';
        const slug = toSlug(fallbackTitle);
        const stub: AzureService = {
          id: explicitId || `ai:${slug}`,
          type: explicitId || `ai.detected/${slug}`,
          category: toStringSafe(serviceEntry.category) || 'AI Detected',
          categoryId: toStringSafe(serviceEntry.categoryId) || 'ai-detected',
          title: fallbackTitle,
          iconPath: '/Icons/generic-service.svg',
          description: toStringSafe(serviceEntry.description) || 'Detected by AI from structured response',
          publicIp: null,
          privateIp: null,
        };
        const canonicalId = stub.id;
        if (layoutHint.x !== undefined && layoutHint.y !== undefined) {
          serviceLayouts[canonicalId] = {
            x: layoutHint.x,
            y: layoutHint.y,
            ...(layoutHint.width ? { width: layoutHint.width } : {}),
            ...(layoutHint.height ? { height: layoutHint.height } : {}),
          };
        }
        if (isContainer(canonicalId, fallbackTitle)) {
          ensureContainerGroup(stub, uniqueGroupIds);
          return;
        }

        uniqueGroupIds.forEach((groupId) => registerServiceGroup(canonicalId, groupId));

        if (!groupIdsFromJson.has(canonicalId)) {
          services.push(stub);
          servicesById.set(canonicalId, stub);
          servicesByTitle.set(stub.title.toLowerCase(), canonicalId);
        }
        return;
      }

      const clone: AzureService = {
        ...resolvedService,
        description: toStringSafe(serviceEntry.description) || resolvedService.description,
      };

      const canonicalId = clone.id;
      if (layoutHint.x !== undefined && layoutHint.y !== undefined) {
        serviceLayouts[canonicalId] = {
          x: layoutHint.x,
          y: layoutHint.y,
          ...(layoutHint.width ? { width: layoutHint.width } : {}),
          ...(layoutHint.height ? { height: layoutHint.height } : {}),
        };
      }
      if (isContainer(canonicalId, clone.title)) {
        ensureContainerGroup(clone, uniqueGroupIds);
        return;
      }

      uniqueGroupIds.forEach((groupId) => registerServiceGroup(canonicalId, groupId));

      servicesById.set(clone.id, clone);
      servicesByTitle.set((clone.title || '').toLowerCase(), clone.id);

      if (!groupIdsFromJson.has(clone.id)) {
        services.push(clone);
      }
    });

    serviceGroupHints.forEach((groupIds, serviceKey) => {
      const resolvedServiceId =
        servicesById.has(serviceKey) ? serviceKey : servicesByTitle.get(serviceKey.toLowerCase()) || serviceKey;
      groupIds.forEach((groupIdValue) => {
        const group = groupMap.get(groupIdValue);
        if (group) {
          group.members.push(resolvedServiceId);
        } else {
          const fallbackGroup: ParsedGroup = {
            id: groupIdValue,
            label: groupIdValue,
            type: this.detectGroupType(groupIdValue) ?? 'default',
            members: [resolvedServiceId],
          };
          groups.push(fallbackGroup);
          groupMap.set(groupIdValue, fallbackGroup);
        }
      });
    });

    const groupsByType = new Map<ParsedGroupType, ParsedGroup[]>();
    groups.forEach((group) => {
      const type = group.type ?? 'default';
      if (!groupsByType.has(type)) {
        groupsByType.set(type, []);
      }
      groupsByType.get(type)!.push(group);
    });

    const parentPreferences: Record<ParsedGroupType | 'default', ParsedGroupType[]> = {
      managementGroup: [],
      subscription: ['managementGroup'],
      landingZone: ['subscription', 'managementGroup'],
      region: ['landingZone', 'subscription', 'managementGroup'],
      resourceGroup: ['region', 'landingZone', 'subscription', 'managementGroup'],
      virtualNetwork: ['region', 'landingZone', 'subscription'],
      subnet: ['virtualNetwork', 'region', 'landingZone'],
      cluster: ['resourceGroup', 'region', 'landingZone', 'subscription'],
      networkSecurityGroup: ['virtualNetwork', 'resourceGroup', 'subscription'],
      securityBoundary: ['resourceGroup', 'subscription', 'managementGroup'],
      policyAssignment: ['managementGroup', 'subscription'],
      roleAssignment: ['managementGroup', 'subscription'],
      default: ['resourceGroup', 'landingZone', 'subscription', 'managementGroup'],
    };

    const ensureParentMembership = (childId: string, parentId: string) => {
      const parent = groupMap.get(parentId);
      if (!parent) return;
      parent.members = parent.members || [];
      if (!parent.members.includes(childId)) {
        parent.members.push(childId);
      }
    };

    groups.forEach((group) => {
      if (group.parentId) {
        ensureParentMembership(group.id, group.parentId);
        return;
      }
      const preferences = parentPreferences[group.type ?? 'default'] ?? parentPreferences.default;
      for (const candidateType of preferences) {
        const candidates = groupsByType.get(candidateType);
        if (!candidates || candidates.length === 0) continue;
        const candidate = candidates.find((item) => item.id !== group.id);
        if (candidate) {
          group.parentId = candidate.id;
          ensureParentMembership(group.id, candidate.id);
          break;
        }
      }
    });

    groups.forEach((group) => {
      const memberSet = groupMembers.get(group.id);
      if (memberSet) {
        memberSet.forEach((memberId) => {
          group.members.push(memberId);
        });
      }
      group.members = Array.from(new Set(group.members));
    });

    const serviceIdSet = new Set<string>(services.map((service) => service.id));
    groups.forEach((group) => {
      group.members = group.members.filter((memberId) => serviceIdSet.has(memberId) || groupMap.has(memberId));
    });
    const resolveConnectionId = (candidate: unknown): string | null => {
      const direct = toStringSafe(candidate);
      if (!direct) {
        return null;
      }
      if (serviceIdSet.has(direct)) {
        return direct;
      }
      const alias = servicesByTitle.get(direct.toLowerCase());
      if (alias) {
        return alias;
      }
      if (groupMap.has(direct)) {
        return direct;
      }
      return null;
    };

    rawConnections.forEach((entry) => {
      if (!entry || typeof entry !== 'object') {
        return;
      }
      const connectionEntry = entry as Record<string, unknown>;
      const fromId = resolveConnectionId(connectionEntry.from ?? connectionEntry.source ?? connectionEntry.from_service);
      const toId = resolveConnectionId(connectionEntry.to ?? connectionEntry.target ?? connectionEntry.to_service);
      if (fromId && toId && fromId !== toId) {
        connections.push({
          from: fromId,
          to: toId,
          label: toStringSafe(connectionEntry.label) || undefined,
        });
      }
    });

    if (connections.length === 0) {
      const connectSequence = (ids: string[]) => {
        if (ids.length < 2) return;
        for (let i = 0; i < ids.length - 1; i += 1) {
          const fromId = ids[i];
          const toId = ids[i + 1];
          if (fromId !== toId) {
            connections.push({ from: fromId, to: toId });
          }
        }
      };

      groups.forEach((group) => {
        const serviceMembers = group.members.filter((memberId) => serviceIdSet.has(memberId));
        connectSequence(serviceMembers);
      });

      const ungroupedServices = services
        .map((service) => service.id)
        .filter((serviceId) => !groups.some((group) => group.members.includes(serviceId)));
      connectSequence(ungroupedServices);
    }

    const droppedConnections = rawConnections.length - connections.length;
    const orphanGroups = groups.filter((group) => group.members.length === 0);
    if (typeof console !== 'undefined') {
      console.log('[ArchitectureParser] Structured diagram summary', {
        services: services.length,
        groups: groups.length,
        connections: connections.length,
        droppedConnections: droppedConnections > 0 ? droppedConnections : 0,
        autoCreatedGroups: Array.from(autoCreatedGroups),
        orphanGroups: orphanGroups.map((group) => group.id),
      });
    }

    const layoutRaw = toStringSafe(diagram.layout);
    const hasExplicitLayout = Object.keys(serviceLayouts).length > 0;
    const layout: ParsedArchitecture['layout'] =
      layoutRaw && (layoutRaw === 'horizontal' || layoutRaw === 'vertical' || layoutRaw === 'grid' || layoutRaw === 'manual')
        ? layoutRaw
        : hasExplicitLayout
        ? 'manual'
        : services.length <= 3
        ? 'horizontal'
        : services.length <= 6
        ? 'vertical'
        : 'grid';

    if (services.length === 0 && groups.length === 0) {
      return null;
    }

    return {
      services,
      connections,
      groups,
      layout,
      ...(hasExplicitLayout ? { serviceLayouts } : {}),
    };
  }

  static parseStructuredDiagram(structured: unknown): ParsedArchitecture | null {
    return this.convertStructuredDiagram(structured);
  }

  static parseResponse(response: string): ParsedArchitecture {
    const structuredBlock = this.extractDiagramJsonBlock(response);
    if (structuredBlock) {
      try {
        const structuredData = JSON.parse(structuredBlock);
        const structuredDiagram = this.convertStructuredDiagram(structuredData);
        if (structuredDiagram) {
          console.log('[ArchitectureParser] Using structured diagram JSON section');
          console.log('[ArchitectureParser] parseResponse summary', {
            serviceCount: structuredDiagram.services.length,
            connectionCount: structuredDiagram.connections.length,
            groupCount: structuredDiagram.groups?.length ?? 0,
            services: structuredDiagram.services.map((svc) => svc.title),
          });
          return structuredDiagram;
        }
      } catch (error) {
        console.warn('[ArchitectureParser] Failed to parse structured diagram JSON', error);
      }
    }

    const services: AzureService[] = [];
    const connections: { from: string; to: string; label?: string }[] = [];
    
    // Extract mentioned Azure services
    const mentionedServices = this.extractServices(response);
    console.log('?? Extracted service names:', mentionedServices);
    
    // Find actual Azure service objects
    for (const serviceName of mentionedServices) {
      const azureService = this.findAzureService(serviceName);
      console.log(`?? Looking for "${serviceName}" -> Found:`, azureService?.title || 'NOT FOUND');
      if (azureService && !services.find(s => s.id === azureService.id)) {
        services.push(azureService);
      }
    }
    
    console.log('? Final services for diagram:', services.map(s => s.title));
    
    // Extract connections from text patterns
    const extractedConnections = this.extractConnections(response, services);
    connections.push(...extractedConnections);
    
    const { groups, refinedConnections } = this.buildGroupStructures(services, connections);

    console.log('[ArchitectureParser] parseResponse summary', {
      serviceCount: services.length,
      connectionCount: refinedConnections.length,
      groupCount: groups.length,
      services: services.map((svc) => svc.title),
    });

    return {
      services,
      connections: refinedConnections,
      groups,
      layout: services.length <= 3 ? 'horizontal' : services.length <= 6 ? 'vertical' : 'grid'
    };
  }

  private static detectGroupType(label?: string): ParsedGroupType | null {
    if (!label) return null;
    const normalized = label.toLowerCase().replace(/[\\/\-_]+/g, ' ');
    const match = GROUP_TITLE_KEYWORDS.find(({ keyword }) => normalized.includes(keyword));
    return match?.type ?? null;
  }

  private static buildGroupStructures(
    services: AzureService[],
    connections: { from: string; to: string; label?: string }[]
  ): { groups: ParsedGroup[]; refinedConnections: { from: string; to: string; label?: string }[] } {
    if (!services || services.length === 0) {
      console.log('[ArchitectureParser] parseResponse summary', {
      serviceCount: services.length,
      connectionCount: connections.length,
      groupCount: 0,
      services: services.map((svc) => svc.title),
    });

    return { groups: [], refinedConnections: connections };
    }

    const serviceMap = new Map(services.map((service) => [service.id, service]));
    const groups: ParsedGroup[] = [];
    const groupMap = new Map<string, ParsedGroup>();
    const groupServiceIds = new Set<string>();

    services.forEach((service) => {
      const type =
        this.detectGroupType(service.title) ||
        this.detectGroupType(service.category) ||
        this.detectGroupType(service.id);

      if (type) {
        const group: ParsedGroup = {
          id: service.id,
          label: service.title || service.id,
          type,
          members: [],
          metadata: {
            category: service.category,
            iconPath: service.iconPath,
          },
          sourceServiceId: service.id,
        };
        groups.push(group);
        groupMap.set(group.id, group);
        groupServiceIds.add(service.id);
        (service as unknown as { __isGroup?: boolean }).__isGroup = true;
      }
    });

    // If no explicit group services detected, try to infer from service names
    if (groups.length === 0) {
      services.forEach((service) => {
        const type = this.detectGroupType(service.title || service.description);
        if (type) {
          const groupId = service.id;
          if (!groupMap.has(groupId)) {
            const group: ParsedGroup = {
              id: groupId,
              label: service.title || service.id,
              type,
              members: [],
              metadata: {
                category: service.category,
                iconPath: service.iconPath,
              },
              sourceServiceId: service.id,
            };
            groups.push(group);
            groupMap.set(group.id, group);
            (service as unknown as { __isGroup?: boolean }).__isGroup = true;
          }
        }
      });
    }

    if (groups.length === 0) {
      console.log('[ArchitectureParser] parseResponse summary', {
      serviceCount: services.length,
      connectionCount: connections.length,
      groupCount: groups.length,
      services: services.map((svc) => svc.title),
    });

    return { groups: [], refinedConnections: connections };
    }

    const groupOrder: ParsedGroupType[] = [
      'managementGroup',
      'subscription',
      'region',
      'landingZone',
      'resourceGroup',
      'virtualNetwork',
      'subnet',
      'cluster',
      'networkSecurityGroup',
      'policyAssignment',
      'roleAssignment',
      'securityBoundary',
      'default',
    ];

    const edgeMembership = new Set<string>();

    const registerMembership = (group: ParsedGroup, memberId: string) => {
      if (!memberId || !group) return;
      if (!group.members.includes(memberId)) {
        group.members.push(memberId);
      }
    };

    const chooseParentGroup = (a: ParsedGroup, b: ParsedGroup): ParsedGroup => {
      const indexA = groupOrder.indexOf(a.type);
      const indexB = groupOrder.indexOf(b.type);
      if (indexA === -1 && indexB === -1) return a;
      if (indexA === -1) return b;
      if (indexB === -1) return a;
      return indexA <= indexB ? a : b;
    };

    const edgeKey = (from: string, to: string) => `${from}__${to}`;

    connections.forEach((connection) => {
      const fromGroup = groupMap.get(connection.from);
      const toGroup = groupMap.get(connection.to);

      if (fromGroup && !toGroup) {
        registerMembership(fromGroup, connection.to);
        edgeMembership.add(edgeKey(connection.from, connection.to));
        edgeMembership.add(edgeKey(connection.to, connection.from));
      } else if (!fromGroup && toGroup) {
        registerMembership(toGroup, connection.from);
        edgeMembership.add(edgeKey(connection.from, connection.to));
        edgeMembership.add(edgeKey(connection.to, connection.from));
      } else if (fromGroup && toGroup) {
        const parent = chooseParentGroup(fromGroup, toGroup);
        const child = parent.id === fromGroup.id ? toGroup : fromGroup;
        if (!child.parentId) {
          child.parentId = parent.id;
        }
        registerMembership(parent, child.id);
        edgeMembership.add(edgeKey(connection.from, connection.to));
        edgeMembership.add(edgeKey(connection.to, connection.from));
      }
    });

    // Deduplicate members and ensure referenced services exist
    groups.forEach((group) => {
      group.members = Array.from(
        new Set(
          group.members.filter((memberId) => serviceMap.has(memberId) || groupMap.has(memberId))
        )
      );
    });

    const groupTypeRank = new Map<ParsedGroupType, number>();
    groupOrder.forEach((type, index) => groupTypeRank.set(type, index));

    const nonContainerGroupTypes = new Set<ParsedGroupType>([
      'policyAssignment',
      'roleAssignment',
    ]);

    const finalMembers = new Map<string, Set<string>>();
    const serviceAssignments = new Map<string, string>();

    groups.forEach((group) => {
      finalMembers.set(group.id, new Set<string>());
    });

    groups.forEach((group) => {
      const members = finalMembers.get(group.id)!;
      group.members.forEach((memberId) => {
        if (groupMap.has(memberId)) {
          members.add(memberId);
          const childGroup = groupMap.get(memberId)!;
          if (!childGroup.parentId || childGroup.parentId === group.id) {
            childGroup.parentId = group.id;
          }
        } else if (serviceMap.has(memberId) && !nonContainerGroupTypes.has(group.type)) {
          const existingGroupId = serviceAssignments.get(memberId);
          if (!existingGroupId) {
            serviceAssignments.set(memberId, group.id);
            members.add(memberId);
          } else if (existingGroupId !== group.id) {
            const existingRank =
              groupTypeRank.get(groupMap.get(existingGroupId)?.type ?? 'default') ?? 0;
            const candidateRank = groupTypeRank.get(group.type) ?? 0;
            if (candidateRank >= existingRank) {
              finalMembers.get(existingGroupId)?.delete(memberId);
              serviceAssignments.set(memberId, group.id);
              members.add(memberId);
            }
          }
        }
      });
    });

    const GROUP_PARENT_FALLBACKS: Record<ParsedGroupType, ParsedGroupType[]> = {
      managementGroup: [],
      subscription: ['managementGroup'],
      region: ['subscription', 'managementGroup'],
      landingZone: ['subscription', 'managementGroup'],
      resourceGroup: ['landingZone', 'subscription', 'managementGroup'],
      virtualNetwork: ['resourceGroup', 'landingZone', 'subscription'],
      subnet: ['virtualNetwork', 'resourceGroup'],
      cluster: ['resourceGroup', 'landingZone'],
      networkSecurityGroup: ['virtualNetwork', 'resourceGroup', 'landingZone'],
      securityBoundary: ['managementGroup', 'subscription'],
      policyAssignment: ['managementGroup', 'subscription', 'landingZone'],
      roleAssignment: ['managementGroup', 'subscription', 'landingZone'],
      default: ['landingZone', 'resourceGroup', 'subscription'],
    };

    const ensureGroupMembership = (parentId: string, childId: string) => {
      const members = finalMembers.get(parentId);
      if (!members) return;
      members.add(childId);
      const childGroup = groupMap.get(childId);
      if (childGroup) {
        childGroup.parentId = parentId;
      }
    };

    groups.forEach((group) => {
      if (group.parentId) {
        ensureGroupMembership(group.parentId, group.id);
        return;
      }
      const fallbacks = GROUP_PARENT_FALLBACKS[group.type] ?? [];
      for (const parentType of fallbacks) {
        const candidates = groups.filter(
          (candidate) => candidate.type === parentType && candidate.id !== group.id
        );
        if (candidates.length === 0) continue;
        const chosen = candidates.reduce((best, candidate) => {
          const bestCount = finalMembers.get(best.id)?.size ?? 0;
          const candidateCount = finalMembers.get(candidate.id)?.size ?? 0;
          return candidateCount < bestCount ? candidate : best;
        }, candidates[0]);
        ensureGroupMembership(chosen.id, group.id);
        break;
      }
    });

    const adjacency = new Map<string, Set<string>>();
    const addAdjacency = (a: string, b: string) => {
      if (!adjacency.has(a)) {
        adjacency.set(a, new Set<string>());
      }
      adjacency.get(a)!.add(b);
    };

    connections.forEach((connection) => {
      addAdjacency(connection.from, connection.to);
      addAdjacency(connection.to, connection.from);
    });

    const assignServiceToGroup = (serviceId: string, groupId: string) => {
      const group = groupMap.get(groupId);
      if (!group || nonContainerGroupTypes.has(group.type)) return false;
      finalMembers.get(groupId)?.add(serviceId);
      serviceAssignments.set(serviceId, groupId);
      return true;
    };

    const containerFallbackOrder: ParsedGroupType[] = [
      'resourceGroup',
      'landingZone',
      'virtualNetwork',
      'subscription',
      'managementGroup',
      'default',
    ];

    const unassignedServices = services.filter(
      (service) =>
        !serviceAssignments.has(service.id) && !groupServiceIds.has(service.id)
    );

    unassignedServices.forEach((service) => {
      const neighborScores = new Map<string, number>();
      const neighbors = adjacency.get(service.id);
      if (neighbors) {
        neighbors.forEach((neighborId) => {
          if (groupMap.has(neighborId)) {
            const group = groupMap.get(neighborId)!;
            if (!nonContainerGroupTypes.has(group.type)) {
              neighborScores.set(group.id, (neighborScores.get(group.id) ?? 0) + 3);
            }
          }
          const assignedGroupId = serviceAssignments.get(neighborId);
          if (assignedGroupId) {
            neighborScores.set(assignedGroupId, (neighborScores.get(assignedGroupId) ?? 0) + 1);
          }
        });
      }

      if (neighborScores.size > 0) {
        let bestGroupId: string | null = null;
        let bestScore = -Infinity;
        neighborScores.forEach((score, groupId) => {
          const group = groupMap.get(groupId);
          if (!group || nonContainerGroupTypes.has(group.type)) return;
          const rank = groupTypeRank.get(group.type) ?? 0;
          const adjustedScore = score * 10 + rank;
          if (adjustedScore > bestScore) {
            bestScore = adjustedScore;
            bestGroupId = groupId;
          }
        });
        if (bestGroupId && assignServiceToGroup(service.id, bestGroupId)) {
          return;
        }
      }

      for (const fallbackType of containerFallbackOrder) {
        const candidates = groups.filter(
          (group) => group.type === fallbackType && !nonContainerGroupTypes.has(group.type)
        );
        if (candidates.length === 0) continue;
        const chosen = candidates.reduce((best, candidate) => {
          const bestSize = finalMembers.get(best.id)?.size ?? 0;
          const candidateSize = finalMembers.get(candidate.id)?.size ?? 0;
          return candidateSize < bestSize ? candidate : best;
        }, candidates[0]);
        if (assignServiceToGroup(service.id, chosen.id)) {
          return;
        }
      }
    });

    groups.forEach((group) => {
      group.members = Array.from(finalMembers.get(group.id) ?? new Set<string>());
    });

    const refinedConnections = connections.filter(
      (connection) => !edgeMembership.has(edgeKey(connection.from, connection.to))
    );

    console.log('[ArchitectureParser] parseResponse summary', {
      serviceCount: services.length,
      connectionCount: refinedConnections.length,
      groupCount: groups.length,
      services: services.map((svc) => svc.title),
    });

    return { groups, refinedConnections };
  }
  
  /**
   * Extract Azure service names from text
   */
  private static extractServices(text: string): string[] {
    const services: string[] = [];
    const lowerText = text.toLowerCase();
    

    
    // Extract Bicep resource types and add them to services
    bicepResourcePatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        matches.forEach(match => {
          services.push(match.trim());
        });
      }
    });
    

    
    // Extract natural language service names
    serviceNamePatterns.forEach(pattern => {
      const matches = text.match(pattern);
      if (matches) {
        matches.forEach(match => {
          let serviceName = match.toLowerCase().trim();
          // Clean up common prefixes
          serviceName = serviceName.replace(/^(azure\s+|microsoft\s+)/, '');
          services.push(serviceName);
        });
      }
    });
    
    // Check for service mappings using comprehensive mappings (Azure + AWS)
    Object.keys(SERVICE_TO_ICON_MAPPINGS).forEach((serviceName) => {
      if (lowerText.includes(serviceName)) {
        services.push(serviceName);
      }
    });
    Object.keys(AWS_SERVICE_TO_ICON_MAPPINGS).forEach((serviceName) => {
      if (lowerText.includes(serviceName)) {
        services.push(serviceName);
      }
    });
    
    // Extract services from Bicep/ARM template code blocks using comprehensive mapper
    const bicepResourceTypes = BicepResourceMapper.extractResourceTypesFromBicep(text);
    bicepResourceTypes.forEach(resourceType => {
      const mapping = BicepResourceMapper.getMapping(resourceType);
      if (mapping) {
        services.push(mapping.serviceName.toLowerCase());
      }
    });
    
    // Also check for service names mentioned in comprehensive mappings
    BICEP_RESOURCE_MAPPINGS.forEach(mapping => {
      if (lowerText.includes(mapping.serviceName.toLowerCase()) || 
          lowerText.includes(mapping.iconTitle.toLowerCase())) {
        services.push(mapping.serviceName.toLowerCase());
      }
    });
    
    return [...new Set(services)]; // Remove duplicates
  }
  
  /**
   * Find Azure service object by name or type
   */
  static findAzureServiceByName(serviceName: string): AzureService | null {
    return this.findAzureService(serviceName);
  }

  /**
   * Find Azure service object by name or type (internal implementation)
   */
  private static findAzureService(serviceName: string): AzureService | null {
    const normalizedName = serviceName.toLowerCase();
    
    console.log(`?? Looking for service: "${serviceName}" (normalized: "${normalizedName}")`);
    
    // Manual normalization for common Azure terms to avoid ontology mismatches
    const manualNormalization: Record<string, string> = {
      'azure vpn gateway': 'virtual network gateways',
      'vpn gateway': 'virtual network gateways',
      'virtual network gateways': 'virtual network gateways',
      'azure application gateway': 'application gateways',
      'application gateway': 'application gateways',
      'azure front door': 'front door and cdn profiles',
      'azure web application firewall': 'web application firewall policies(waf)',
      'azure firewall': 'azure firewall',
      'hub virtual network': 'virtual network',
      'wordpress on azure': 'wordpress',
    };
    const manualHit = Object.keys(manualNormalization).find((key) => normalizedName.includes(key));
    if (manualHit) {
      const target = manualNormalization[manualHit];
      const manualService = azureServices.find(
        (s) =>
          (s.title || '').toLowerCase() === target ||
          (s.id || '').toLowerCase().includes(target.replace(/\s+/g, '-')) ||
          (s.type || '').toLowerCase().includes(target.replace(/\s+/g, ''))
      );
      if (manualService) {
        return manualService;
      }
    }
    
    // Try direct mapping to icon titles first
    const exactIconTitle = SERVICE_TO_ICON_MAPPINGS[normalizedName];
    if (exactIconTitle) {
      console.log(`? Found exact mapping: "${normalizedName}" -> "${exactIconTitle}"`);
      const service = azureServices.find(s => 
        (s.title || '').toLowerCase() === exactIconTitle.toLowerCase()
      );
      if (service) {
        console.log(`? Found Azure service:`, service.title);
        return service;
      } else {
        console.log(`? No Azure service found for icon title: "${exactIconTitle}"`);
      }
    }
    
    // Try Bicep resource mappings
    const bicepMapping = BICEP_RESOURCE_MAPPINGS.find(mapping => 
      mapping.serviceName.toLowerCase() === normalizedName ||
      mapping.iconTitle.toLowerCase() === normalizedName
    );
    
    if (bicepMapping) {
      console.log(`? Found Bicep mapping:`, bicepMapping);
      const service = azureServices.find(s => 
        (s.title || '').toLowerCase() === bicepMapping.iconTitle.toLowerCase()
      );
      if (service) {
        console.log(`? Found Azure service from Bicep mapping:`, service.title);
        return service;
      }
    }
    
    // Try fuzzy matching as last resort - but be more restrictive
    const fuzzyMatch = azureServices.find(service => {
      const serviceTitle = (service.title || '').toLowerCase();
      
      // Exact match
      if (serviceTitle === normalizedName) return true;
      
      // Don't match very short titles (like "Azure A") unless exact
      if (serviceTitle.length <= 8 && serviceTitle !== normalizedName) return false;
      
      // Only match if the normalized name is reasonably long
      if (normalizedName.length < 4) return false;
      
      // For Bicep resource types, only match if they contain the right parts
      if (normalizedName.includes('microsoft.')) {
        const parts = normalizedName.split('/');
        if (parts.length >= 2) {
          const resourceType = parts[parts.length - 1]; // e.g., "sites" from "Microsoft.Web/sites"
          return serviceTitle.includes(resourceType) || serviceTitle.includes(parts[0].replace('microsoft.', ''));
        }
      }
      
      // Contains match (both directions) - but with minimum length requirement
      if (normalizedName.length >= 6 && (serviceTitle.includes(normalizedName) || normalizedName.includes(serviceTitle))) {
        return true;
      }
      
      return false;
    });
    
    if (fuzzyMatch) {
      console.log(`?? Found fuzzy match: "${serviceName}" -> "${fuzzyMatch.title}"`);
      return fuzzyMatch;
    }
    
    console.log(`? No service found for: "${serviceName}" - creating custom stub`);

    // Create a generic custom stub so the UI can show a node even when the
    // LLM can't be mapped to a known provider icon. This gives the user a
    // visible placeholder and allows them to edit title/description later.
    const slug = normalizedName.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    const humanTitle = serviceName && typeof serviceName === 'string' ? serviceName : `Custom Service`;
    const customStub: AzureService = {
      id: `ai:${slug || 'custom'}`,
      type: `ai.detected/${slug || 'custom'}`,
      category: 'Custom',
      categoryId: 'custom',
      title: humanTitle,
      // Use a generic icon so custom stubs are visible in the UI
      iconPath: '/Icons/general/10805-icon-service-Gear.svg',
      description: 'Custom service detected  description unavailable',
      publicIp: null,
      privateIp: null,
    };
    return customStub;
  }

  // Cache for icon titles extracted from azureIconIndex.json
  private static _iconTitleCache: string[] | null = null;

  /**
   * Find the best matching AzureService using the icon index ontology.
   * Builds a flat list of icon titles and scores them against the query.
   */
  private static findBestIconMatch(query: string): AzureService | null {
    if (!query || typeof query !== 'string') return null;
    const normalizedQuery = query.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').trim();

    // Build cache of icon titles
    if (!this._iconTitleCache) {
      const titles: string[] = [];
      const cats = (iconIndex as IconIndex).categories || [];
      for (const c of cats) {
        // c.icons may be an array or an object map depending on how index was generated
  const rawIcons = (c && (c as unknown as IconCategory).icons) || [];
        const iconsArr = Array.isArray(rawIcons) ? rawIcons : Object.values(rawIcons || {});
        for (const ic of iconsArr) {
          let title = '';
          if (!ic) continue;
          if (typeof ic === 'string') {
            title = ic;
          } else if (typeof ic === 'object') {
            const iconObj = ic as Record<string, unknown>;
            const rawTitle = ['title', 'file', 'id', 'path']
              .map((key) => iconObj[key])
              .find((value) => typeof value === 'string') as string | undefined;
            title = rawTitle ?? '';
          } else {
            title = String(ic);
          }
          if (title) titles.push(title.toLowerCase());
        }
      }
      this._iconTitleCache = [...new Set(titles)];
    }

    let bestScore = 0;
    let bestTitle: string | null = null;
    for (const title of this._iconTitleCache) {
      const score = this.computeNameScore(normalizedQuery, title);
      if (score > bestScore) {
        bestScore = score;
        bestTitle = title;
      }
    }

    // Threshold only reasonably good matches
    if (bestScore >= 0.35 && bestTitle) {
      const found = azureServices.find(s => (s.title || '').toLowerCase() === bestTitle);
      return found || null;
    }

    return null;
  }

  /**
   * Attempt to resolve AWS service names to a minimal stub AzureService-shaped object
   * using our AWS mappings and the generated awsIconIndex.json. This allows the
   * UI to render an iconPath for AWS services even though they are not part of
   * the Azure services list.
   */
  private static findAwsService(serviceName: string): AzureService | null {
    if (!serviceName || typeof serviceName !== 'string') return null;
    const normalized = serviceName.toLowerCase().trim();

    // Try exact mapping first
    const mappedTitle = AWS_SERVICE_TO_ICON_MAPPINGS[normalized];
    let resolvedTitle = mappedTitle;

    // If no exact mapping, try to find a mapping whose key is contained in the name
    if (!resolvedTitle) {
      for (const [key, title] of Object.entries(AWS_SERVICE_TO_ICON_MAPPINGS)) {
        if (normalized.includes(key)) {
          resolvedTitle = title;
          break;
        }
      }
    }

    if (!resolvedTitle) return null;

    // Lookup path from generated awsIconIndex.json (may be empty before generation)
    const iconPath = (awsIconIndex as Record<string, string>)[resolvedTitle] || '';

    // Build a minimal stub compatible with AzureService interface used across the app
    const titleHuman = resolvedTitle.replace(/^Arch_/, '').replace(/_/g, ' ').replace(/-/g, ' ');
    const stub: AzureService = {
      id: `aws:${resolvedTitle}`,
      type: `aws.${resolvedTitle}`,
      category: 'AWS',
      categoryId: 'aws',
      title: titleHuman,
      iconPath: iconPath,
      description: 'Detected AWS service (icon stub)',
      publicIp: null,
      privateIp: null,
    };

    return stub;
  }

  /**
   * Attempt to resolve GCP service names to a minimal stub AzureService-shaped object
   * using our GCP mappings and the generated gcpIconIndex.json. This allows the
   * UI to render an iconPath for GCP services even though they are not part of
   * the Azure services list.
   */
  private static findGcpService(serviceName: string): AzureService | null {
    if (!serviceName || typeof serviceName !== 'string') return null;
    const normalized = serviceName.toLowerCase().trim();

    // Try exact mapping first
    const mappedTitle = GCP_SERVICE_TO_ICON_MAPPINGS[normalized];
    let resolvedTitle = mappedTitle;

    // If no exact mapping, try to find a mapping whose key is contained in the name
    if (!resolvedTitle) {
      for (const [key, title] of Object.entries(GCP_SERVICE_TO_ICON_MAPPINGS)) {
        if (normalized.includes(key)) {
          resolvedTitle = title;
          break;
        }
      }
    }

    if (!resolvedTitle) return null;

    // Lookup path from generated gcpIconIndex.json (may be empty before generation)
    const iconPath = (gcpIconIndex as Record<string, string>)[resolvedTitle] || '';

    // Build a minimal stub compatible with AzureService interface used across the app
    const titleHuman = resolvedTitle.replace(/[-_]+/g, ' ').replace(/Arch\s*/i, '').trim();
    const stub: AzureService = {
      id: `gcp:${resolvedTitle}`,
      type: `gcp.${resolvedTitle}`,
      category: 'GCP',
      categoryId: 'gcp',
      title: titleHuman,
      iconPath: iconPath,
      description: 'Detected GCP service (icon stub)',
      publicIp: null,
      privateIp: null,
    };

    return stub;
  }

  /**
   * Lightweight similarity score combining token overlap and trigram Jaccard.
   */
  private static computeNameScore(query: string, candidate: string): number {
    if (!query || !candidate) return 0;
    const qTokens = query.split(/\s+/).filter(Boolean);
    const cTokens = candidate.split(/\s+/).filter(Boolean);

    const intersection = qTokens.filter(t => cTokens.includes(t)).length;
    const tokenScore = intersection / Math.max(qTokens.length, cTokens.length, 1);

    const trigrams = (s: string) => {
      const t: string[] = [];
      const s2 = `  ${s}  `;
      for (let i = 0; i < s2.length - 2; i++) t.push(s2.substr(i, 3));
      return t;
    };
    const qTri = trigrams(query);
    const cTri = trigrams(candidate);
    const triInter = qTri.filter(t => cTri.includes(t)).length;
    const triUnion = new Set([...qTri, ...cTri]).size || 1;
    const trigramScore = triInter / triUnion;

    return tokenScore * 0.6 + trigramScore * 0.4;
  }
  
  /**
   * Extract connections between services from text
   */
  private static extractConnections(
    text: string, 
    services: AzureService[]
  ): { from: string; to: string; label?: string }[] {
    const connections: { from: string; to: string; label?: string }[] = [];
    

    
    connectionPatterns.forEach(pattern => {
      let match;
      while ((match = pattern.exec(text)) !== null) {
        const from = this.findServiceByName(match[1], services);
        const to = this.findServiceByName(match[2], services);
        
        if (from && to && from.id !== to.id) {
          connections.push({
            from: from.id,
            to: to.id,
            label: 'connection'
          });
        }
      }
    });
    
    // Add logical connections based on common Azure service patterns
    this.addLogicalConnections(services, connections);
    
    return connections;
  }
  
  /**
   * Add logical connections based on common Azure architecture patterns
   */
  private static addLogicalConnections(
    services: AzureService[], 
    connections: { from: string; to: string; label?: string }[]
  ): void {
    const servicesByTitle = new Map(services.map(s => [(s.title || '').toLowerCase(), s]));
    const aliasToCanonical: Record<string, string> = {
      'app service': 'app services',
      'virtual network': 'virtual networks',
      'stream analytics': 'stream analytics jobs',
      'azure stream analytics': 'stream analytics jobs',
      'synapse': 'azure synapse analytics',
      'synapse workspace': 'azure synapse analytics',
      'azure synapse': 'azure synapse analytics',
      'event hub': 'event hubs',
      'azure event hub': 'event hubs',
      'iot hub': 'azure iot hub',
      'azure iot hub': 'azure iot hub',
      'managed identity': 'managed identities',
    };

    Object.entries(aliasToCanonical).forEach(([alias, canonical]) => {
      const canonicalService = servicesByTitle.get(canonical);
      if (canonicalService) {
        servicesByTitle.set(alias, canonicalService);
      }
    });

    const findServiceForAlias = (alias: string): AzureService | null => {
      const key = alias.toLowerCase();
      if (servicesByTitle.has(key)) {
        return servicesByTitle.get(key)!;
      }
      for (const [title, service] of servicesByTitle.entries()) {
        if (title === key || title.includes(key) || key.includes(title)) {
          return service;
        }
      }
      return null;
    };
    

    
    patterns.forEach((pattern) => {
      pattern.from.forEach((fromAlias) => {
        const fromService = findServiceForAlias(fromAlias);
        if (!fromService) {
          return;
        }
        pattern.to.forEach((toAlias) => {
          const toService = findServiceForAlias(toAlias);
          if (
            !toService ||
            fromService.id === toService.id ||
            connections.some((c) => c.from === fromService.id && c.to === toService.id)
          ) {
            return;
          }
          connections.push({
            from: fromService.id,
            to: toService.id,
            label: pattern.label,
          });
        });
      });
    });
  }
  
  /**
   * Find service in list by partial name match
   */
  private static findServiceByName(name: string, services: AzureService[]): AzureService | null {
    // Guard against undefined/null and non-string names
    if (!name || typeof name !== 'string') return null;
    const normalizedName = name.toString().toLowerCase().trim();
    if (!normalizedName) return null;

    return services.find(service => {
      const title = service && service.title ? String(service.title).toLowerCase() : '';
      if (!title) return false;
      return title.includes(normalizedName) || normalizedName.includes(title);
    }) || null;
  }
  

  
  /**
   * Generate React Flow nodes from parsed architecture
   */
  static generateNodes(architecture: ParsedArchitecture): Node[] {
    const layoutHints = architecture.serviceLayouts || {};
    const hasManualLayout = Object.keys(layoutHints).length > 0;

    if (hasManualLayout) {
      // If upstream provided explicit coordinates, honor them and skip auto-layout/group packing.
      // This prevents the ReactFlow graph from collapsing into columns.
      return this.generateManualNodes(architecture, layoutHints);
    }

    const { groups } = architecture;
    if (groups && groups.length > 0) {
      return this.generateGroupedNodes(architecture);
    }

    // Try to derive a flow layout from connections when no groups/manual positions are present
    const flowPositions = this.deriveFlowLayout(architecture);
    if (flowPositions) {
      return architecture.services.map((service, idx) => {
        const pos = flowPositions.get(service.id) || { x: idx * 260, y: 120 };
        return {
          id: service.id,
          type: 'azure.service',
          position: pos,
          data: {
            title: service.title,
            subtitle: service.description,
            iconPath: service.iconPath,
            status: 'active' as const,
            service,
          },
        };
      });
    }

    const nodes: Node[] = [];
    const { services, layout } = architecture;
    
    services.forEach((service, index) => {
      const position = this.calculateNodePosition(index, services.length, layout);
      
      nodes.push({
        id: service.id,
        type: 'azure.service',
        position,
        data: {
          title: service.title,
          subtitle: service.description,
          iconPath: service.iconPath,
          status: 'active' as const,
          badges: service.badges,
          service, // Keep the original service object for reference
        },
      });
    });
    
    return nodes;
  }

  private static generateManualNodes(architecture: ParsedArchitecture, layoutHints: Record<string, ServiceLayoutHint>): Node[] {
    const nodes: Node[] = [];
    architecture.services.forEach((service, index) => {
      const hint = layoutHints[service.id];
      const position =
        hint && typeof hint.x === 'number' && typeof hint.y === 'number'
          ? { x: hint.x, y: hint.y }
          : this.calculateNodePosition(index, architecture.services.length, architecture.layout);

      nodes.push({
        id: service.id,
        type: 'azure.service',
        position,
        data: {
          title: service.title,
          subtitle: service.description,
          iconPath: service.iconPath,
          status: 'active' as const,
          service,
        },
        ...(hint?.width || hint?.height
          ? { style: { width: hint.width ?? undefined, height: hint.height ?? undefined } }
          : {}),
      });
    });
    return nodes;
  }

  /**
   * Derive a left-to-right layered layout from connection structure.
   * Useful when a vision extractor returns services + connections but no positions/groups.
   */
  private static deriveFlowLayout(architecture: ParsedArchitecture): Map<string, { x: number; y: number }> | null {
    const { services, connections } = architecture;
    if (!services || services.length === 0 || !connections || connections.length === 0) {
      return null;
    }

    const idSet = new Set(services.map((s) => s.id));
    const adj = new Map<string, Set<string>>();
    const indegree = new Map<string, number>();

    services.forEach((s) => {
      adj.set(s.id, new Set<string>());
      indegree.set(s.id, 0);
    });

    connections.forEach((c) => {
      if (!idSet.has(c.from) || !idSet.has(c.to)) return;
      if (!adj.has(c.from)) adj.set(c.from, new Set<string>());
      const set = adj.get(c.from)!;
      if (!set.has(c.to)) {
        set.add(c.to);
        indegree.set(c.to, (indegree.get(c.to) || 0) + 1);
      }
    });

    // Topological layering (Kahn)
    const queue: string[] = [];
    indegree.forEach((deg, id) => {
      if (deg === 0) queue.push(id);
    });
    if (queue.length === 0) {
      // Fall back if a cycle blocks layout
      queue.push(...services.map((s) => s.id));
    }

    const layer = new Map<string, number>();
    while (queue.length > 0) {
      const current = queue.shift()!;
      const currentLayer = layer.get(current) ?? 0;
      for (const nxt of adj.get(current) || []) {
        const nextLayer = Math.max(layer.get(nxt) ?? 0, currentLayer + 1);
        layer.set(nxt, nextLayer);
        indegree.set(nxt, (indegree.get(nxt) || 1) - 1);
        if ((indegree.get(nxt) || 0) === 0) {
          queue.push(nxt);
        }
      }
      if (!layer.has(current)) {
        layer.set(current, currentLayer);
      }
    }

    // Group by layer to spread vertically with consistent spacing
    const byLayer = new Map<number, string[]>();
    Array.from(layer.entries()).forEach(([id, l]) => {
      const arr = byLayer.get(l) || [];
      arr.push(id);
      byLayer.set(l, arr);
    });

    const positions = new Map<string, { x: number; y: number }>();
    const layerWidth = 480;
    const rowGap = 240;
    const baseX = 150;
    const baseY = 150;

    Array.from(byLayer.entries()).forEach(([l, ids]) => {
      // Stable order: sort by id to keep consistency
      ids.sort();
      const count = ids.length;
      ids.forEach((id, idx) => {
        // Spread vertically; keep center anchored so singletons don't stack at top
        const yOffset = (idx - (count - 1) / 2) * rowGap;
        positions.set(id, { x: baseX + l * layerWidth, y: baseY + yOffset });
      });
    });

    return positions;
  }

  private static generateGroupedNodes(architecture: ParsedArchitecture): Node[] {
    const nodes: Node[] = [];
    const { services, groups = [], layout } = architecture;
    if (groups.length === 0) {
      return nodes;
    }

    const serviceMap = new Map(services.map((service) => [service.id, service]));
    const groupMap = new Map(groups.map((group) => [group.id, group]));

    // Ensure parent references point to known groups
    groups.forEach((group) => {
      if (group.parentId && !groupMap.has(group.parentId)) {
        group.parentId = undefined;
      }
    });

    const depthCache = new Map<string, number>();
    const visitedStack = new Set<string>();

    const computeGroupDepth = (groupId: string): number => {
      if (depthCache.has(groupId)) {
        return depthCache.get(groupId)!;
      }
      if (visitedStack.has(groupId)) {
        console.warn('[ArchitectureParser] Detected circular group hierarchy', { groupId });
        depthCache.set(groupId, 0);
        return 0;
      }

      visitedStack.add(groupId);
      const group = groupMap.get(groupId);
      let depth = 0;
      if (group && group.parentId && groupMap.has(group.parentId)) {
        depth = computeGroupDepth(group.parentId) + 1;
      }
      depthCache.set(groupId, depth);
      visitedStack.delete(groupId);
      return depth;
    };

    groups.forEach((group) => computeGroupDepth(group.id));

    const serviceParent = new Map<string, string>();
    groups.forEach((group) => {
      const depth = depthCache.get(group.id) ?? 0;
      group.members = (group.members || []).filter((memberId) => {
        if (groupMap.has(memberId)) {
          const childGroup = groupMap.get(memberId)!;
          if (!childGroup.parentId || childGroup.parentId === group.id) {
            childGroup.parentId = group.id;
          }
          return true;
        }
        return serviceMap.has(memberId);
      });

      group.members.forEach((memberId) => {
        if (!serviceMap.has(memberId)) {
          return;
        }
        const existingParent = serviceParent.get(memberId);
        if (!existingParent) {
          serviceParent.set(memberId, group.id);
          return;
        }
        const existingDepth = depthCache.get(existingParent) ?? 0;
        if (depth > existingDepth) {
          serviceParent.set(memberId, group.id);
        }
      });
    });

    interface GroupLayoutInfo {
      width: number;
      height: number;
      serviceIds: string[];
      childGroupIds: string[];
      columns: number;
    }

    const SERVICE_WIDTH = 190;
    const SERVICE_HEIGHT = 120;
    const PADDING_X = 60;
    const PADDING_TOP = 80;
    const GROUP_GAP = 60;
    const SERVICE_GAP_X = 80;
    const SERVICE_GAP_Y = 50;

    const layoutInfoMap = new Map<string, GroupLayoutInfo>();

    // Protect against circular child-parent relationships during measurement
    const measuringStack = new Set<string>();

    const measureGroup = (groupId: string): GroupLayoutInfo => {
      if (layoutInfoMap.has(groupId)) {
        return layoutInfoMap.get(groupId)!;
      }

      // If we're already measuring this group, we've detected a cycle. Return a safe fallback.
      if (measuringStack.has(groupId)) {
        console.warn('[ArchitectureParser] Detected circular group measurement', { groupId });
        const fallback: GroupLayoutInfo = {
          width: 360,
          height: 240,
          serviceIds: [],
          childGroupIds: [],
          columns: 1,
        };
        layoutInfoMap.set(groupId, fallback);
        return fallback;
      }

      measuringStack.add(groupId);

      const group = groupMap.get(groupId);
      if (!group) {
        const empty: GroupLayoutInfo = {
          width: 360,
          height: 240,
          serviceIds: [],
          childGroupIds: [],
          columns: 1,
        };
        layoutInfoMap.set(groupId, empty);
        measuringStack.delete(groupId);
        return empty;
      }

      const childGroupIds = groups
        .filter((candidate) => candidate.parentId === groupId && candidate.id !== groupId)
        .map((candidate) => candidate.id);

      const serviceIds = group.members.filter((memberId) => serviceMap.has(memberId));

      const measuredChildGroups: GroupLayoutInfo[] = [];
      for (const childId of childGroupIds) {
        if (measuringStack.has(childId)) {
          // Break the cycle by using a conservative fallback for the child
          console.warn('[ArchitectureParser] Skipping recursive child measurement due to cycle', {
            groupId,
            childId,
          });
          measuredChildGroups.push({
            width: 360,
            height: 240,
            serviceIds: [],
            childGroupIds: [],
            columns: 1,
          });
        } else {
          measuredChildGroups.push(measureGroup(childId));
        }
      }

      const serviceCount = serviceIds.length;
      // Layout services in a single horizontal row with generous spacing
      const serviceAreaWidth =
        serviceCount > 0 ? serviceCount * SERVICE_WIDTH + Math.max(0, serviceCount - 1) * SERVICE_GAP_X : 0;
      const serviceAreaHeight = serviceCount > 0 ? SERVICE_HEIGHT : 0;

      const nestedWidth =
        measuredChildGroups.length > 0
          ? Math.max(...measuredChildGroups.map((info) => info.width))
          : 0;
      const nestedHeight =
        measuredChildGroups.length > 0
          ? measuredChildGroups.reduce((total, info, index) => {
              const gap = index === 0 ? 0 : GROUP_GAP;
              return total + info.height + gap;
            }, 0)
          : 0;

      const innerWidth = Math.max(serviceAreaWidth, nestedWidth, 400);
      const width = Math.max(innerWidth + PADDING_X * 2, 500);
      const height =
        PADDING_TOP +
        serviceAreaHeight +
        (serviceAreaHeight > 0 && nestedHeight > 0 ? GROUP_GAP : 0) +
        nestedHeight +
        60;

      const computed: GroupLayoutInfo = {
        width,
        height,
        serviceIds,
        childGroupIds,
        columns: 1, // Single row layout
      };

      layoutInfoMap.set(groupId, computed);
      measuringStack.delete(groupId);
      return computed;
    };

    groups.forEach((group) => measureGroup(group.id));

    const groupedServiceIds = new Set<string>(Array.from(serviceParent.keys()));
    const groupServiceIds = new Set<string>(
      groups.map((group) => group.sourceServiceId || group.id)
    );

    let rootGroups = groups.filter((group) => !group.parentId);
    if (rootGroups.length === 0) {
      rootGroups = [...groups];
      rootGroups.forEach((group) => {
        group.parentId = undefined;
      });
    }

    const placedGroupIds = new Set<string>();

    let maxCanvasX = 0;
    let maxCanvasY = 0;

    const placeGroup = (
      groupId: string,
      x: number,
      y: number,
      parentId?: string,
      absoluteX?: number,
      absoluteY?: number
    ) => {
      if (placedGroupIds.has(groupId)) {
        return;
      }
      placedGroupIds.add(groupId);

      const group = groupMap.get(groupId);
      const layoutInfo = layoutInfoMap.get(groupId);
      if (!group || !layoutInfo) {
        return;
      }

      const absoluteLeft = absoluteX ?? x;
      const absoluteTop = absoluteY ?? y;

      maxCanvasX = Math.max(maxCanvasX, absoluteLeft + layoutInfo.width);
      maxCanvasY = Math.max(maxCanvasY, absoluteTop + layoutInfo.height);

      const groupNode: Node = {
        id: group.id,
        type: 'azure.group',
        position: { x, y },
        data: {
          label: group.label,
          groupType: group.type,
          status: 'group',
          metadata: group.metadata,
        },
        style: {
          width: layoutInfo.width,
          height: layoutInfo.height,
        },
        draggable: true,
        selectable: true,
        ...(parentId
          ? {
              parentNode: parentId,
              extent: 'parent' as const,
            }
          : {}),
      };

      nodes.push(groupNode);

      // Layout services horizontally in a single row with generous spacing
      const serviceCount = layoutInfo.serviceIds.length;
      const totalServiceWidth = serviceCount * SERVICE_WIDTH;
      const totalGapWidth = Math.max(0, serviceCount - 1) * SERVICE_GAP_X;
      const servicesAreaWidth = totalServiceWidth + totalGapWidth;
      const startX = PADDING_X + Math.max(0, (layoutInfo.width - PADDING_X * 2 - servicesAreaWidth) / 2);

      layoutInfo.serviceIds.forEach((serviceId, index) => {
        const service = serviceMap.get(serviceId);
        if (!service) return;

        // Skip services that are also groups (to prevent duplicate nodes)
        if ((service as unknown as { __isGroup?: boolean }).__isGroup || groupMap.has(service.id)) {
          return;
        }

        const xOffset = startX + index * (SERVICE_WIDTH + SERVICE_GAP_X);
        const yOffset = PADDING_TOP;

        nodes.push({
          id: service.id,
          type: 'azure.service',
          position: { x: xOffset, y: yOffset },
          parentId: group.id,
          extent: 'parent',
          data: {
            title: service.title,
            subtitle: service.description,
            iconPath: service.iconPath,
            status: 'active' as const,
            service,
          },
        });
      });

      let currentY =
        PADDING_TOP +
        (layoutInfo.serviceIds.length > 0
          ? SERVICE_HEIGHT + SERVICE_GAP_Y
          : 0);

      if (layoutInfo.serviceIds.length > 0 && layoutInfo.childGroupIds.length > 0) {
        currentY += GROUP_GAP;
      }

      layoutInfo.childGroupIds.forEach((childId) => {
        const childInfo = layoutInfoMap.get(childId);
        if (!childInfo) return;

        const innerWidth = layoutInfo.width - PADDING_X * 2;
        const childX =
          PADDING_X + Math.max(0, (innerWidth - childInfo.width) / 2);
        const childY = currentY;

        placeGroup(
          childId,
          childX,
          childY,
          group.id,
          absoluteLeft + childX,
          absoluteTop + childY
        );

        currentY += childInfo.height + GROUP_GAP;
      });
    };

    const rootGap = 120;
    const primaryPaddingX = 80;
    const primaryPaddingY = 80;

    const rootCount = Math.max(rootGroups.length, 1);
    const columns =
      layout === 'vertical'
        ? 1
        : layout === 'horizontal'
        ? rootCount
        : Math.max(1, Math.ceil(Math.sqrt(rootCount)));

    let currentColumn = 0;
    let currentX = primaryPaddingX;
    let currentY = primaryPaddingY;
    let rowHeight = 0;

    rootGroups.forEach((group, index) => {
      const info = layoutInfoMap.get(group.id);
      if (!info) return;

      if (currentColumn >= columns) {
        currentColumn = 0;
        currentX = primaryPaddingX;
        currentY += rowHeight + rootGap;
        rowHeight = 0;
      }

      placeGroup(group.id, currentX, currentY, undefined, currentX, currentY);

      currentX += info.width + rootGap;
      rowHeight = Math.max(rowHeight, info.height);
      currentColumn += 1;
    });

    const ungroupedServices = services.filter((service) => {
      if (groupServiceIds.has(service.id)) return false;
      if ((service as unknown as { __isGroup?: boolean }).__isGroup) return false;
      return !groupedServiceIds.has(service.id);
    });

    if (ungroupedServices.length > 0) {
      const startY = maxCanvasY > 0 ? maxCanvasY + 160 : 400;
      const offsetX = 80;

      ungroupedServices.forEach((service, index) => {
        const position = this.calculateNodePosition(
          index,
          ungroupedServices.length,
          layout
        );
        nodes.push({
          id: service.id,
          type: 'azure.service',
          position: { x: position.x + offsetX, y: position.y + startY },
          data: {
            title: service.title,
            subtitle: service.description,
            iconPath: service.iconPath,
            status: 'active' as const,
            service,
          },
        });
      });
    }

    const MIN_MARGIN = 60;
    let minX = Number.POSITIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    nodes.forEach((node) => {
      if (node.position) {
        minX = Math.min(minX, node.position.x);
        minY = Math.min(minY, node.position.y);
      }
    });
    const shiftX = minX === Number.POSITIVE_INFINITY ? 0 : Math.max(0, MIN_MARGIN - minX);
    const shiftY = minY === Number.POSITIVE_INFINITY ? 0 : Math.max(0, MIN_MARGIN - minY);
    if (shiftX || shiftY) {
      nodes.forEach((node) => {
        if (node.position) {
          node.position = {
            x: node.position.x + shiftX,
            y: node.position.y + shiftY,
          };
        }
      });
    }

    return nodes;
  }
  
  /**
   * Calculate node position based on layout
   */
  private static calculateNodePosition(
    index: number, 
    total: number, 
    layout: 'horizontal' | 'vertical' | 'grid' | 'manual'
  ): { x: number; y: number } {
    switch (layout) {
      case 'horizontal':
        return {
          x: 150 + index * 450,
          y: 120,
        };
      
      case 'vertical':
        return {   
          x: 150,
          y: 120 + index * 200,
        };
      
      case 'grid': {
        const cols = Math.ceil(Math.sqrt(total));
        const row = Math.floor(index / cols);
        const col = index % cols;
        return {
          x: 150 + col * 400,
          y: 120 + row * 220,
        };
      }
      case 'manual': {
        // If manual layout nodes are missing coordinates, fall back to a gentle grid.
        const cols = Math.ceil(Math.sqrt(total || 1));
        const row = Math.floor(index / cols);
        const col = index % cols;
        return {
          x: 150 + col * 400,
          y: 120 + row * 220,
        };
      }
      
      default:
        return { x: 0, y: 0 };
    }
  }
}







