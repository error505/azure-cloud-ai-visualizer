# backend/app/models/__init__.py
"""
Pydantic models for the multi-cloud infrastructure platform.

This module provides the core data models used across the application:
- InfraGraph: Unified multi-cloud inventory model
- Migration, Compliance, and Cost result models
- Fix/Patch application models
"""

from app.models.infra_models import (
    InfraNode,
    InfraEdge,
    InfraGraph,
    ReverseEngineeringResult,
    MigrationResult,
    MigrationMapping,
    ComplianceReport,
    ComplianceViolation,
    CostOptimization,
    CostRecommendation,
    NodeCost,
    FixPatch,
    FixType,
)

__all__ = [
    "InfraNode",
    "InfraEdge",
    "InfraGraph",
    "ReverseEngineeringResult",
    "MigrationResult",
    "MigrationMapping",
    "ComplianceReport",
    "ComplianceViolation",
    "CostOptimization",
    "CostRecommendation",
    "NodeCost",
    "FixPatch",
    "FixType",
]
