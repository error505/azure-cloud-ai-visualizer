export const API_BASE_URL = 'http://localhost:8000';

export async function generateIac(diagramData: unknown, targetFormat: 'bicep'|'terraform', options?: { providerVersion?: string; workspace?: string; namingConvention?: string; requiredProviders?: string; variables?: string; remoteBackend?: string; initAndValidate?: boolean }) {
  // Include top-level service-config map to help backend deterministic generator
  const serviceConfigs: Record<string, unknown> = {};
  try {
    type DiagramNode = { id?: string; data?: Record<string, unknown> };
    type DiagramData = { nodes?: DiagramNode[] };
    const d = diagramData as DiagramData;
    if (d && Array.isArray(d.nodes)) {
      for (const n of d.nodes) {
        const rawData = n.data || {};
        const id = n.id || (rawData['id'] as string) || JSON.stringify(n).slice(0,8);
        const data = rawData as Record<string, unknown>;
        // attach known structured configs under the node id
        serviceConfigs[id] = {
          cognitiveServicesConfig: data['cognitiveServicesConfig'] ?? undefined,
          searchConfig: data['searchConfig'] ?? undefined,
          cosmosConfig: data['cosmosConfig'] ?? undefined,
          keyVaultConfig: data['keyVaultConfig'] ?? undefined,
          appServiceConfig: data['appServiceConfig'] ?? undefined,
          skuObject: data['skuObject'] ?? undefined,
        };
      }
    }
  } catch (err) {
    // ignore extraction errors
  }

  const body: Record<string, unknown> = { diagram_data: diagramData, target_format: targetFormat, service_configs: serviceConfigs };
  if (options) {
    if (options.namingConvention) body.resource_naming_convention = options.namingConvention;
    if (options.providerVersion) body.provider_version = options.providerVersion;
    if (options.workspace) body.workspace = options.workspace;
    if (options.requiredProviders) body.required_providers = options.requiredProviders;
    if (options.variables) body.variables = options.variables;
    if (options.remoteBackend) body.remote_backend = options.remoteBackend;
    if (typeof options.initAndValidate !== 'undefined') body.init_and_validate = !!options.initAndValidate;
  }

  const res = await fetch(`${API_BASE_URL}/api/iac/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`IaC generation failed: ${res.statusText}`);
  return res.json();
}

export async function createDeployment(resourceGroup: string, subscriptionId: string, templateContent: string, templateFormat: string = 'bicep', validationOnly = false) {
  const body = {
    resource_group: resourceGroup,
    subscription_id: subscriptionId,
    template_content: templateContent,
    template_format: templateFormat,
    validation_only: validationOnly,
  };

  const res = await fetch(`${API_BASE_URL}/api/deployment/deploy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Create deployment failed: ${res.status} ${text}`);
  }

  return res.json();
}
