import iconIndex from './azureIconIndex.json';

export interface AzureService {
  id: string;
  type: string;
  category: string;
  categoryId: string;
  title: string;
  iconPath: string;
  description: string;
  provider?: 'azure' | 'aws' | 'gcp' | string;
  badges?: string[];
  placeholder?: boolean;
  placeholderReason?: string;
  notes?: string;
  // Additional Azure/Bicep-like metadata (all optional)
  resourceType?: string; // e.g. Microsoft.Storage/storageAccounts
  resourceGroup?: string;
  subscriptionId?: string;
  location?: string; // Azure region
  provisioningState?: 'Succeeded' | 'Creating' | 'Failed' | 'Deleting' | 'Updating' | string;
  // Legacy simple SKU string (deprecated in favor of structured skuObject)
  sku?: string;
  skuObject?: {
    name?: string;
    tier?: string;
    size?: string;
    capacity?: number;
  };
  identity?: {
    type?: 'None' | 'SystemAssigned' | 'UserAssigned' | 'SystemAssigned,UserAssigned';
  userAssignedIdentities?: Record<string, object>; // map of resource IDs
  };
  appServiceConfig?: {
    serverFarmId?: string;
    linuxFxVersion?: string;
    httpsOnly?: boolean;
    appSettings?: { name: string; value: string }[];
    connectionStrings?: { name: string; value: string; type?: string }[];
  };
  cosmosConfig?: {
    offerType?: string; // Standard
    consistencyLevel?: 'Strong' | 'BoundedStaleness' | 'Session' | 'ConsistentPrefix' | 'Eventual';
    locations?: { locationName: string; failoverPriority: number; isZoneRedundant?: boolean }[];
    capabilities?: string[]; // e.g. EnableServerless
    enableAutomaticFailover?: boolean;
  };
  keyVaultConfig?: {
    skuName?: 'standard' | 'premium';
    accessPolicies?: {
      tenantId: string;
      objectId: string;
      permissions: {
        secrets?: string[];
        keys?: string[];
        certificates?: string[];
      };
    }[];
    enabledForDeployment?: boolean;
    enabledForTemplateDeployment?: boolean;
    enabledForDiskEncryption?: boolean;
    enablePurgeProtection?: boolean;
    enableSoftDelete?: boolean;
  };
  cognitiveServicesConfig?: {
    kind?: string; // e.g. CognitiveServices, OpenAI
    skuName?: string; // S1, F0, etc.
  };
  searchConfig?: {
    skuName?: string; // basic, standard, etc.
    replicaCount?: number;
    partitionCount?: number;
    hostingMode?: 'default' | 'highDensity';
  };
  managedIdentityMetadata?: {
    principalId?: string; // read-only after creation
    clientId?: string; // read-only after creation
  };
  roleAssignmentConfig?: {
    scope?: string;
    roleDefinitionId?: string;
    principalId?: string;
    principalType?: string;
  };
  tags?: Record<string, string>;
  endpoints?: { type: string; url: string }[];
  publicIp?: string | null;
  privateIp?: string | null;
  createdAt?: string; // ISO timestamp
  updatedAt?: string; // ISO timestamp
  properties?: Record<string, unknown>;
  dependsOn?: string[]; // ids of other services this depends on
}

interface AzureIconIndexIcon {
  category: string;
  id: string;
  title: string;
  file: string;
  path: string;
}

interface AzureIconIndexCategoryRaw {
  id: string;
  name: string;
  icons: AzureIconIndexIcon | AzureIconIndexIcon[];
}

interface AzureIconIndexRaw {
  categories: AzureIconIndexCategoryRaw[] | AzureIconIndexCategoryRaw;
}

const normalizeIcons = (icons: AzureIconIndexIcon | AzureIconIndexIcon[] | undefined): AzureIconIndexIcon[] => {
  if (!icons) {
    return [];
  }

  return Array.isArray(icons) ? icons : [icons];
};

const normalizeCategories = (
  categories: AzureIconIndexCategoryRaw[] | AzureIconIndexCategoryRaw | undefined,
): AzureIconIndexCategoryRaw[] => {
  if (!categories) {
    return [];
  }

  return Array.isArray(categories) ? categories : [categories];
};

const iconIndexData = iconIndex as AzureIconIndexRaw;
const normalizedCategories = normalizeCategories(iconIndexData.categories);

export const azureServices: AzureService[] = normalizedCategories
  .flatMap((category) =>
    normalizeIcons(category.icons).map((icon) => {
      // Normalize icon path to match the public/Icons folder casing and
      // ensure spaces and special characters are URI encoded so the browser
      // can correctly request the asset. The source JSON uses '/icons/...'
      // while the actual folder in `public` is `Icons` (capital I).
      const rawPath = icon.path || '';
      const normalizedPath = rawPath.replace(/^\/icons\//i, '/Icons/');
      const encodedPath = encodeURI(normalizedPath);

      return {
        id: icon.id,
        type: icon.id,
        category: category.name,
        categoryId: category.id,
        title: icon.title,
        iconPath: encodedPath,
        description: `${category.name} service`,
        provider: 'azure',
        badges: ['Azure'],
        // leave Azure metadata empty by default; parsers or analyzers may fill these
        resourceType: undefined,
        resourceGroup: undefined,
        subscriptionId: undefined,
        location: undefined,
        provisioningState: undefined,
        sku: undefined,
        tags: undefined,
        endpoints: undefined,
        publicIp: null,
        privateIp: null,
        createdAt: undefined,
        updatedAt: undefined,
        properties: undefined,
        dependsOn: undefined,
      };
    }),
  )
  .sort((a, b) => a.title.localeCompare(b.title));

export const serviceCategories = normalizedCategories
  .map((category) => category.name)
  .sort((a, b) => a.localeCompare(b));
