import json
import logging
import asyncio
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _cancelled_response(provider: str, stage: str) -> Dict[str, Any]:
    logger.warning('Terraform generation cancelled during %s stage', stage)
    return {
        'terraform_code': '',
        'parameters': {
            'error': f'Terraform generation cancelled during {stage}',
            'provider': provider,
        },
    }


async def generate_terraform_code(agent_client: Any, diagram: Dict[str, Any], options: Dict[str, Any] | None = None, use_model: bool = False) -> Dict[str, Any]:
    """Generate Terraform HCL using AI ONLY - no deterministic fallbacks.
    
    Prefers MCP-enhanced generation for better schema grounding,
    falls back to standard agent generation.

    Returns a dict with keys: 'terraform_code' and 'parameters'.
    """
    provider = (options or {}).get('provider', 'azurerm')
    
    # Try MCP-enhanced generation first (schema grounded)
    try:
        if agent_client and hasattr(agent_client, 'generate_terraform_via_mcp'):
            logger.debug('Calling agent.generate_terraform_via_mcp')
            raw = await agent_client.generate_terraform_via_mcp(diagram, provider=provider)
            if isinstance(raw, dict) and raw.get('terraform_code'):
                # Add MCP enhancement flag
                raw.setdefault('parameters', {})['mcp_enhanced'] = True
                return raw
    except asyncio.CancelledError:
        return _cancelled_response(provider, 'MCP (terraform)')
    except Exception:
        logger.exception('MCP-enhanced terraform generation failed, falling back to standard')

    # Fall back to standard agent method
    try:
        if agent_client and hasattr(agent_client, 'generate_terraform_code'):
            logger.debug('Calling agent.generate_terraform_code')
            raw = await agent_client.generate_terraform_code(
                architecture_description={'diagram': diagram}, 
                include_monitoring=True, 
                include_security=True,
                provider=provider
            )
            if isinstance(raw, dict) and raw.get('terraform_code'):
                return raw
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except Exception:
                    return {'terraform_code': raw, 'parameters': {'provider': provider}}
    except asyncio.CancelledError:
        return _cancelled_response(provider, 'standard')
    except Exception:
        logger.exception('Agent terraform generation failed')

    # NO DETERMINISTIC FALLBACKS - AI ONLY!
    logger.error("AI terraform generation failed and no deterministic fallbacks allowed")
    return {'terraform_code': '', 'parameters': {'error': 'AI generation failed - no deterministic fallbacks allowed', 'provider': provider}}
