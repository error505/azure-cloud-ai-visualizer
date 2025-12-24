"""API routes for the Azure Architect Backend."""

from fastapi import APIRouter

from app.api.endpoints import projects_simple, chat_simple, diagram_analysis
from app.api.endpoints import deployment, iac_mcp, runs, validation, autopilot, compliance, docs
from app.api.endpoints import reverse_engineering, migration, cost, fix

# iac endpoints depend on optional agent/azure libraries. Import lazily so the
# main app can start in dev environments where those deps may be missing.
_iac_module = None
iac = None
_HAS_IAC = False
try:
	# Compatibility shim: some versions export `prepare_function_call_results`
	# inside `agent_framework.openai._shared` while other packages expect it on
	# the top-level `agent_framework` module. Attempt to copy the symbol if
	# present to avoid import-time errors when loading the `iac` endpoints.
	try:
		import importlib
		af_shared = importlib.import_module("agent_framework.openai._shared")
		af_mod = importlib.import_module("agent_framework")
		if not hasattr(af_mod, "prepare_function_call_results") and hasattr(
			af_shared, "prepare_function_call_results"
		):
			setattr(af_mod, "prepare_function_call_results", af_shared.prepare_function_call_results)
	except Exception:
		# Non-fatal; we'll fall back to the shim router if the real iac module fails
		pass
	from app.api.endpoints import iac as _iac_module
	iac = _iac_module
	_HAS_IAC = True
except Exception as _err:  # pragma: no cover - environment-dependent
	_HAS_IAC = False
	import logging
	logging.getLogger(__name__).warning("Skipping iac router import: %s", _err)

api_router = APIRouter()

# Include simplified endpoint routers for testing
api_router.include_router(projects_simple.router, prefix="/projects", tags=["projects"])
api_router.include_router(chat_simple.router, prefix="/chat", tags=["chat"])
api_router.include_router(diagram_analysis.router, prefix="", tags=["diagram-analysis"])
api_router.include_router(runs.router, prefix="", tags=["runs"])

# TODO: Add back full endpoints when agent framework issues are resolved
# api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
if _HAS_IAC:
	# _iac_module is set in the try block above when import succeeds
	# use getattr to avoid static-analysis errors when _iac_module may be None
	api_router.include_router(getattr(_iac_module, 'router'), prefix="/iac", tags=["iac"])
else:
	# Register a lightweight shim so the /api/iac prefix exists and returns
	# either a simple OpenAI-only endpoint (if OPENAI_API_KEY set) or stub shim.
	import os
	openai_key = os.getenv("OPENAI_API_KEY")
	if openai_key:
		from app.api.endpoints import iac_openai_simple
		api_router.include_router(iac_openai_simple.router, prefix="/iac", tags=["iac"])
	else:
		from app.api.endpoints import iac_shim
		api_router.include_router(iac_shim.router, prefix="/iac", tags=["iac"])
api_router.include_router(deployment.router, prefix="/deployment", tags=["deployment"])
api_router.include_router(iac_mcp.router, prefix="/iac/mcp", tags=["iac-mcp"])
api_router.include_router(validation.router, prefix="", tags=["validation"])
api_router.include_router(autopilot.router, prefix="", tags=["autopilot"])
api_router.include_router(compliance.router, prefix="", tags=["compliance"])
api_router.include_router(docs.router, prefix="", tags=["docs"])
api_router.include_router(reverse_engineering.router, prefix="", tags=["reverse-engineering"])
api_router.include_router(migration.router, prefix="", tags=["migration"])
api_router.include_router(cost.router, prefix="", tags=["cost"])
api_router.include_router(fix.router, prefix="", tags=["fix"])
