"""
Cloud Parsers Module

Provides functions to normalize cloud inventory JSON into InfraGraph format:
- normalize_azure: Parse Azure resource exports
- normalize_aws: Parse AWS inventory/CloudFormation exports
- normalize_gcp: Parse GCP resource manager exports
"""

from .parsers import (
    normalize_azure,
    normalize_aws,
    normalize_gcp,
    detect_provider,
    parse_inventory,
)

__all__ = [
    "normalize_azure",
    "normalize_aws",
    "normalize_gcp",
    "detect_provider",
    "parse_inventory",
]
