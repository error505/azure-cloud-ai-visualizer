"""
Auto-Remediation Engine

Automatically fixes common architecture issues identified by the Critic agent:
- Security: Add NSGs, enable encryption, configure private endpoints
- Cost: Right-size SKUs, add autoscaling, enable dev/test pricing
- Reliability: Add backup vaults, configure redundancy, add health probes
- Compliance: Enable audit logging, add diagnostic settings
- Performance: Add caching layers, CDN, optimize data flows

Each fix is deterministic and safe to apply automatically.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RemediationAction:
    """Represents a single auto-remediation action."""
    action_type: str  # add_node, modify_node, add_edge, remove_node
    target_id: Optional[str]  # Node ID affected
    changes: Dict[str, Any]  # The actual changes to apply
    description: str


class AutoRemediationEngine:
    """
    Applies automatic fixes to diagrams based on validation issues.
    """
    
    def __init__(self):
        """Initialize the remediation engine."""
        self.azure_services_catalog = self._load_azure_catalog()
    
    def _load_azure_catalog(self) -> Dict[str, Any]:
        """Load Azure services catalog for icon IDs and configurations."""
        # This would normally load from the actual catalog
        # For now, return a simplified mapping
        return {
            "nsg": {
                "id": "networking/10067-icon-service-Network-Security-Groups",
                "title": "Network Security Group",
                "category": "Networking"
            },
            "keyvault": {
                "id": "security/10245-icon-service-Key-Vaults",
                "title": "Key Vault",
                "category": "Security"
            },
            "backup": {
                "id": "storage/10122-icon-service-Backup",
                "title": "Backup Vault",
                "category": "Storage"
            },
            "appinsights": {
                "id": "devops/00012-icon-service-Application-Insights",
                "title": "Application Insights",
                "category": "DevOps"
            },
            "loganalytics": {
                "id": "analytics/00009-icon-service-Log-Analytics-Workspaces",
                "title": "Log Analytics Workspace",
                "category": "Analytics"
            },
            "redis": {
                "id": "databases/10137-icon-service-Cache-Redis",
                "title": "Azure Cache for Redis",
                "category": "Databases"
            },
            "privateendpoint": {
                "id": "networking/10084-icon-service-Private-Link",
                "title": "Private Endpoint",
                "category": "Networking"
            }
        }
    
    def remediate_issues(
        self, 
        diagram: Dict[str, Any],
        issues: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Apply automatic fixes to diagram based on validation issues.
        
        Args:
            diagram: ReactFlow diagram with nodes/edges/groups
            issues: List of validation issues (must have auto_fixable=True)
            
        Returns:
            Updated diagram with fixes applied
        """
        actions: List[RemediationAction] = []
        
        # Process each issue and generate remediation actions
        for issue in issues:
            if not issue.get('auto_fixable', False):
                continue
            
            category = issue.get('category', '')
            severity = issue.get('severity', '')
            affected_services = issue.get('affected_services', [])
            
            # Route to appropriate remediation handler
            if category == 'security':
                actions.extend(self._remediate_security(diagram, issue, affected_services))
            elif category == 'cost':
                actions.extend(self._remediate_cost(diagram, issue, affected_services))
            elif category == 'reliability':
                actions.extend(self._remediate_reliability(diagram, issue, affected_services))
            elif category == 'compliance':
                actions.extend(self._remediate_compliance(diagram, issue, affected_services))
            elif category == 'performance':
                actions.extend(self._remediate_performance(diagram, issue, affected_services))
        
        # Apply all actions to the diagram
        updated_diagram = self._apply_actions(diagram, actions)
        
        logger.info(f"Applied {len(actions)} remediation actions to diagram")
        
        return updated_diagram
    
    def _remediate_security(
        self,
        diagram: Dict[str, Any],
        issue: Dict[str, Any],
        affected_services: List[str]
    ) -> List[RemediationAction]:
        """Generate security remediation actions."""
        actions = []
        title = issue.get('title', '').lower()
        description = issue.get('description', '').lower()
        
        # Missing NSG
        if 'network security' in title or 'nsg' in title:
            nsg_config = self.azure_services_catalog['nsg']
            action = RemediationAction(
                action_type='add_node',
                target_id=None,
                changes={
                    'id': f"nsg-{len(diagram.get('nodes', []))}",
                    'type': 'azureService',
                    'position': {'x': 100, 'y': 100},  # Will be repositioned
                    'data': {
                        'id': nsg_config['id'],
                        'label': nsg_config['title'],
                        'category': nsg_config['category'],
                        'description': 'Auto-added for network security',
                        'icon': nsg_config['id']
                    }
                },
                description='Add Network Security Group for traffic filtering'
            )
            actions.append(action)
            
            # Connect NSG to affected services
            for service_id in affected_services[:3]:  # Limit to first 3
                edge_action = RemediationAction(
                    action_type='add_edge',
                    target_id=None,
                    changes={
                        'id': f"edge-nsg-{service_id}",
                        'source': f"nsg-{len(diagram.get('nodes', []))}",
                        'target': service_id,
                        'label': 'controls traffic',
                        'type': 'smoothstep',
                        'animated': False,
                        'style': {'strokeWidth': 1, 'stroke': '#ef4444'}
                    },
                    description=f'Connect NSG to {service_id}'
                )
                actions.append(edge_action)
        
        # Missing Key Vault
        if 'secret' in description or 'key vault' in title or 'encryption key' in description:
            kv_config = self.azure_services_catalog['keyvault']
            action = RemediationAction(
                action_type='add_node',
                target_id=None,
                changes={
                    'id': f"keyvault-{len(diagram.get('nodes', []))}",
                    'type': 'azureService',
                    'position': {'x': 200, 'y': 200},
                    'data': {
                        'id': kv_config['id'],
                        'label': kv_config['title'],
                        'category': kv_config['category'],
                        'description': 'Secure secrets and encryption keys',
                        'icon': kv_config['id']
                    }
                },
                description='Add Key Vault for secrets management'
            )
            actions.append(action)
        
        # Enable encryption
        if 'encryption' in description and affected_services:
            for service_id in affected_services:
                action = RemediationAction(
                    action_type='modify_node',
                    target_id=service_id,
                    changes={
                        'data.encryption_at_rest': True,
                        'data.encryption_in_transit': True
                    },
                    description=f'Enable encryption for {service_id}'
                )
                actions.append(action)
        
        # Add private endpoints
        if 'private endpoint' in title or 'public access' in description:
            pe_config = self.azure_services_catalog['privateendpoint']
            for service_id in affected_services[:2]:
                action = RemediationAction(
                    action_type='add_node',
                    target_id=None,
                    changes={
                        'id': f"pe-{service_id}",
                        'type': 'azureService',
                        'position': {'x': 150, 'y': 150},
                        'data': {
                            'id': pe_config['id'],
                            'label': f'Private Endpoint',
                            'category': pe_config['category'],
                            'description': f'Private access to {service_id}',
                            'icon': pe_config['id']
                        }
                    },
                    description=f'Add private endpoint for {service_id}'
                )
                actions.append(action)
        
        return actions
    
    def _remediate_cost(
        self,
        diagram: Dict[str, Any],
        issue: Dict[str, Any],
        affected_services: List[str]
    ) -> List[RemediationAction]:
        """Generate cost optimization remediation actions."""
        actions = []
        title = issue.get('title', '').lower()
        description = issue.get('description', '').lower()
        
        # Right-size SKUs
        if 'oversized' in description or 'sku' in title:
            for service_id in affected_services:
                action = RemediationAction(
                    action_type='modify_node',
                    target_id=service_id,
                    changes={
                        'data.sku': 'Standard',  # Downgrade to standard
                        'data.tier': 'Standard'
                    },
                    description=f'Right-size SKU for {service_id}'
                )
                actions.append(action)
        
        # Add autoscaling
        if 'autoscal' in description or 'right-siz' in description:
            for service_id in affected_services:
                action = RemediationAction(
                    action_type='modify_node',
                    target_id=service_id,
                    changes={
                        'data.autoscale_enabled': True,
                        'data.min_instances': 1,
                        'data.max_instances': 10
                    },
                    description=f'Enable autoscaling for {service_id}'
                )
                actions.append(action)
        
        # Add reservation recommendation
        if 'reservation' in description or 'reserved' in title:
            for service_id in affected_services:
                action = RemediationAction(
                    action_type='modify_node',
                    target_id=service_id,
                    changes={
                        'data.reserved_instance': True,
                        'data.reservation_term': '1-year'
                    },
                    description=f'Enable reserved instance pricing for {service_id}'
                )
                actions.append(action)
        
        return actions
    
    def _remediate_reliability(
        self,
        diagram: Dict[str, Any],
        issue: Dict[str, Any],
        affected_services: List[str]
    ) -> List[RemediationAction]:
        """Generate reliability remediation actions."""
        actions = []
        title = issue.get('title', '').lower()
        description = issue.get('description', '').lower()
        
        # Add backup
        if 'backup' in title or 'backup' in description:
            backup_config = self.azure_services_catalog['backup']
            action = RemediationAction(
                action_type='add_node',
                target_id=None,
                changes={
                    'id': f"backup-vault",
                    'type': 'azureService',
                    'position': {'x': 300, 'y': 300},
                    'data': {
                        'id': backup_config['id'],
                        'label': backup_config['title'],
                        'category': backup_config['category'],
                        'description': 'Backup and disaster recovery',
                        'icon': backup_config['id']
                    }
                },
                description='Add Backup Vault for data protection'
            )
            actions.append(action)
            
            # Connect backup to affected data services
            for service_id in affected_services:
                edge_action = RemediationAction(
                    action_type='add_edge',
                    target_id=None,
                    changes={
                        'id': f"edge-backup-{service_id}",
                        'source': service_id,
                        'target': 'backup-vault',
                        'label': 'backup data',
                        'type': 'smoothstep',
                        'animated': False,
                        'style': {'strokeWidth': 1, 'stroke': '#3b82f6'}
                    },
                    description=f'Connect {service_id} to backup vault'
                )
                actions.append(edge_action)
        
        # Add redundancy
        if 'redundancy' in title or 'single point' in description:
            for service_id in affected_services:
                action = RemediationAction(
                    action_type='modify_node',
                    target_id=service_id,
                    changes={
                        'data.redundancy': 'ZoneRedundant',
                        'data.availability_zones': [1, 2, 3]
                    },
                    description=f'Enable zone redundancy for {service_id}'
                )
                actions.append(action)
        
        # Add health probes
        if 'health' in title or 'monitoring' in description:
            for service_id in affected_services:
                action = RemediationAction(
                    action_type='modify_node',
                    target_id=service_id,
                    changes={
                        'data.health_probe_enabled': True,
                        'data.health_probe_interval': 30,
                        'data.unhealthy_threshold': 3
                    },
                    description=f'Add health probe to {service_id}'
                )
                actions.append(action)
        
        return actions
    
    def _remediate_compliance(
        self,
        diagram: Dict[str, Any],
        issue: Dict[str, Any],
        affected_services: List[str]
    ) -> List[RemediationAction]:
        """Generate compliance remediation actions."""
        actions = []
        title = issue.get('title', '').lower()
        description = issue.get('description', '').lower()
        
        # Add logging
        if 'audit' in description or 'logging' in title or 'diagnostic' in description:
            la_config = self.azure_services_catalog['loganalytics']
            action = RemediationAction(
                action_type='add_node',
                target_id=None,
                changes={
                    'id': 'log-analytics',
                    'type': 'azureService',
                    'position': {'x': 400, 'y': 400},
                    'data': {
                        'id': la_config['id'],
                        'label': la_config['title'],
                        'category': la_config['category'],
                        'description': 'Centralized logging and compliance',
                        'icon': la_config['id']
                    }
                },
                description='Add Log Analytics for audit logging'
            )
            actions.append(action)
            
            # Enable diagnostic settings on affected services
            for service_id in affected_services:
                modify_action = RemediationAction(
                    action_type='modify_node',
                    target_id=service_id,
                    changes={
                        'data.diagnostic_settings_enabled': True,
                        'data.log_analytics_workspace': 'log-analytics'
                    },
                    description=f'Enable diagnostic settings for {service_id}'
                )
                actions.append(modify_action)
        
        # Add compliance tags
        if 'tag' in description or 'metadata' in description:
            for service_id in affected_services:
                action = RemediationAction(
                    action_type='modify_node',
                    target_id=service_id,
                    changes={
                        'data.tags': {
                            'Compliance': 'Required',
                            'DataClassification': 'Confidential',
                            'Environment': 'Production'
                        }
                    },
                    description=f'Add compliance tags to {service_id}'
                )
                actions.append(action)
        
        return actions
    
    def _remediate_performance(
        self,
        diagram: Dict[str, Any],
        issue: Dict[str, Any],
        affected_services: List[str]
    ) -> List[RemediationAction]:
        """Generate performance remediation actions."""
        actions = []
        title = issue.get('title', '').lower()
        description = issue.get('description', '').lower()
        
        # Add caching
        if 'cach' in description or 'performance' in title:
            redis_config = self.azure_services_catalog['redis']
            action = RemediationAction(
                action_type='add_node',
                target_id=None,
                changes={
                    'id': 'redis-cache',
                    'type': 'azureService',
                    'position': {'x': 250, 'y': 250},
                    'data': {
                        'id': redis_config['id'],
                        'label': redis_config['title'],
                        'category': redis_config['category'],
                        'description': 'Caching layer for performance',
                        'icon': redis_config['id']
                    }
                },
                description='Add Redis Cache for performance'
            )
            actions.append(action)
        
        # Add Application Insights
        if 'monitoring' in description or 'telemetry' in description:
            ai_config = self.azure_services_catalog['appinsights']
            action = RemediationAction(
                action_type='add_node',
                target_id=None,
                changes={
                    'id': 'app-insights',
                    'type': 'azureService',
                    'position': {'x': 350, 'y': 350},
                    'data': {
                        'id': ai_config['id'],
                        'label': ai_config['title'],
                        'category': ai_config['category'],
                        'description': 'Performance monitoring and diagnostics',
                        'icon': ai_config['id']
                    }
                },
                description='Add Application Insights for monitoring'
            )
            actions.append(action)
        
        return actions
    
    def _apply_actions(
        self,
        diagram: Dict[str, Any],
        actions: List[RemediationAction]
    ) -> Dict[str, Any]:
        """Apply remediation actions to diagram."""
        # Deep copy to avoid mutating original
        import copy
        updated = copy.deepcopy(diagram)
        
        nodes = updated.get('nodes', [])
        edges = updated.get('edges', [])
        
        for action in actions:
            if action.action_type == 'add_node':
                nodes.append(action.changes)
                logger.info(f"Added node: {action.description}")
            
            elif action.action_type == 'add_edge':
                edges.append(action.changes)
                logger.info(f"Added edge: {action.description}")
            
            elif action.action_type == 'modify_node':
                # Find and update the target node
                for node in nodes:
                    if node.get('id') == action.target_id:
                        # Apply changes (supports nested dot notation)
                        for key, value in action.changes.items():
                            if '.' in key:
                                # Handle nested keys like 'data.encryption_at_rest'
                                parts = key.split('.')
                                target = node
                                for part in parts[:-1]:
                                    if part not in target:
                                        target[part] = {}
                                    target = target[part]
                                target[parts[-1]] = value
                            else:
                                node[key] = value
                        logger.info(f"Modified node: {action.description}")
                        break
            
            elif action.action_type == 'remove_node':
                nodes = [n for n in nodes if n.get('id') != action.target_id]
                # Remove edges connected to this node
                edges = [e for e in edges if e.get('source') != action.target_id and e.get('target') != action.target_id]
                logger.info(f"Removed node: {action.description}")
        
        updated['nodes'] = nodes
        updated['edges'] = edges
        
        return updated
