"""
API endpoint for analyzing architecture diagrams using OpenAI Vision
"""
import base64
import logging
import json
import re
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional, Literal
import os
import asyncio
from dotenv import load_dotenv
try:
    # Prefer the async client when available so we don't block the event loop
    from openai import AsyncOpenAI
except Exception:
    AsyncOpenAI = None
import openai

from app.agents.diagram_guide_prompts import STRUCTURED_DIAGRAM_GUIDANCE

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()

# NOTE: We intentionally avoid creating a top-level OpenAI client here so that
# env changes during startup won't leave a stale client. The endpoint will
# create an AsyncOpenAI client per-request when needed (safe for async FastAPI).


def find_all_balanced_jsons(s: str) -> List[str]:
    """Return all balanced-brace substrings that look like JSON objects found in s."""
    results = []
    if not s:
        return results
    starts = [m.start() for m in re.finditer(r"\{", s)]
    for start_idx in starts:
        depth = 0
        for i, ch in enumerate(s[start_idx:], start=start_idx):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    cand = s[start_idx:i+1]
                    results.append(cand)
                    break
    return results


def extract_json_from_text(text: Optional[str]) -> Optional[dict]:
    """Attempt to extract a JSON object from free-form assistant text.

    Strategy:
    - If fenced ```json blocks exist, scan their contents for balanced JSON candidates.
    - Otherwise, scan the whole text for balanced JSON candidates.
    - Try candidates from largest->smallest, attempt json.loads, then simple repairs.
    - Return the first successfully decoded dict, or None.
    """
    if not text:
        return None

    candidates: List[str] = []

    # Prefer explicit fenced blocks first
    fenced = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fenced:
        for block in fenced:
            block = block.strip()
            logger.info('Found fenced JSON block preview: %s', block[:200])
            candidates.extend(find_all_balanced_jsons(block) or [block])
    else:
        # No fences: try stripping triple-backticks then scanning
        stripped = re.sub(r"```[a-zA-Z0-9_+-]*", "", text)
        stripped = stripped.replace('```', '').strip()
        logger.info('No fenced block - using stripped text preview: %s', (stripped or '')[:200])
        candidates.extend(find_all_balanced_jsons(stripped))
        # Also scan the original text as a fallback
        candidates.extend(find_all_balanced_jsons(text))

    # Deduplicate while preserving order
    seen = set()
    uniq_candidates = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            uniq_candidates.append(c)

    # Sort by length (largest first) - prefer full objects
    uniq_candidates.sort(key=len, reverse=True)

    for idx, cand in enumerate(uniq_candidates):
        preview = (cand or '')[:400]
        logger.info('Trying JSON candidate #%d (len=%d): %s', idx + 1, len(cand or ''), preview)
        try:
            parsed = json.loads(cand)
            logger.info('Parsed JSON candidate #%d successfully', idx + 1)
            return parsed
        except Exception as e:
            logger.debug('Failed to json.loads candidate #%d: %s', idx + 1, str(e))
            # Attempt simple repairs
            # 1) Remove trailing commas before } or ]
            repaired = re.sub(r",\s*(\}|\])", r"\1", cand)
            try:
                parsed = json.loads(repaired)
                logger.info('Parsed repaired JSON candidate #%d successfully', idx + 1)
                return parsed
            except Exception:
                pass
            # 2) Replace single quotes with double quotes (best-effort)
            try:
                swapped = cand.replace("'", '"')
                parsed = json.loads(swapped)
                logger.info('Parsed single-quote-replaced candidate #%d successfully', idx + 1)
                return parsed
            except Exception:
                pass

    return None


def normalize_connections(analysis_json: dict) -> List[dict]:
    """Normalize connection entries into DiagramConnection objects.

    Handles keys like 'from', 'from_service', 'source', 'to', 'to_service', 'target'.
    Tries to match names to the canonical services list (case-insensitive or substring).
    Deduplicates connections.
    """
    services = analysis_json.get("services", []) or []
    raw_conns = analysis_json.get("connections", []) or []

    def pick_key(d: dict, candidates):
        for k in candidates:
            if k in d and isinstance(d[k], str):
                return d[k]
        return None

    def best_match(name: str) -> str:
        if not name:
            return ""
        n = name.strip()
        low = n.lower()
        # exact match
        for s in services:
            if isinstance(s, str) and s.lower() == low:
                return s
        # substring match
        for s in services:
            if isinstance(s, str) and (low in s.lower() or s.lower() in low):
                return s
        # no match - return original
        return n

    seen = set()
    out: List[dict] = []
    for rc in raw_conns:
        if not isinstance(rc, dict):
            continue
        raw_from = pick_key(rc, ("from_service", "from", "source", "src")) or ""
        raw_to = pick_key(rc, ("to_service", "to", "target", "dst")) or ""
        label = rc.get("label") or rc.get("type") or rc.get("relationship") or "connection"

        f = best_match(raw_from)
        t = best_match(raw_to)

        key = (f, t, label or "")
        if key in seen:
            continue
        seen.add(key)
        out.append({"from_service": f, "to_service": t, "label": label})

    return out


GROUP_TYPE_KEYWORDS: List[tuple[str, str]] = [
    ("landing zone", "landingZone"),
    ("landing-zone", "landingZone"),
    ("virtual network", "virtualNetwork"),
    ("vnet", "virtualNetwork"),
    ("subnet", "subnet"),
    ("region", "region"),
    ("resource group", "resourceGroup"),
    ("cluster", "cluster"),
    ("aks", "cluster"),
    ("network security group", "networkSecurityGroup"),
    ("nsg", "networkSecurityGroup"),
    ("security boundary", "securityBoundary"),
    ("management group", "managementGroup"),
    ("tenant root", "managementGroup"),
    ("subscription", "subscription"),
    ("policy assignment", "policyAssignment"),
    ("policy definition", "policyAssignment"),
    ("role assignment", "roleAssignment"),
    ("rbac", "roleAssignment"),
]

GROUP_TYPE_ORDER: List[str] = [
    "managementGroup",
    "subscription",
    "region",
    "landingZone",
    "resourceGroup",
    "virtualNetwork",
    "subnet",
    "cluster",
    "networkSecurityGroup",
    "policyAssignment",
    "roleAssignment",
    "securityBoundary",
    "default",
]


def normalize_group_key(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def infer_group_type(label: Optional[str], explicit: Optional[str] = None) -> str:
    if explicit:
        cleaned = explicit.lower()
        for _, mapped in GROUP_TYPE_KEYWORDS:
            if mapped.lower() == explicit.lower().replace("_", ""):
                return mapped
    text = (label or "").lower()
    for keyword, mapped in GROUP_TYPE_KEYWORDS:
        if keyword in text:
            return mapped
    if explicit:
        combined = explicit.lower().replace("_", " ")
        for keyword, mapped in GROUP_TYPE_KEYWORDS:
            if keyword in combined:
                return mapped
    return "default"


class ImageAnalysisRequest(BaseModel):
    image: str  # Base64 encoded image
    format: str  # Image format (e.g., "image/jpeg")

class DiagramConnection(BaseModel):
    from_service: str = ""
    to_service: str = ""
    label: Optional[str] = None

class DiagramGroup(BaseModel):
    id: str
    label: str
    group_type: Literal[
        "managementGroup",
        "subscription",
        "region",
        "landingZone",
        "virtualNetwork",
        "subnet",
        "cluster",
        "resourceGroup",
        "networkSecurityGroup",
        "securityBoundary",
        "policyAssignment",
        "roleAssignment",
        "default",
    ] = "default"
    members: List[str] = []
    parent_id: Optional[str] = None
    metadata: Dict[str, Any] = {}

class DiagramAnalysisResult(BaseModel):
    services: List[str]
    connections: List[DiagramConnection]
    description: str
    suggested_services: List[str]
    groups: List[DiagramGroup] = []

class ImageAnalysisResponse(BaseModel):
    analysis: DiagramAnalysisResult


def _choose_parent_group(a: DiagramGroup, b: DiagramGroup) -> DiagramGroup:
    index_a = GROUP_TYPE_ORDER.index(a.group_type) if a.group_type in GROUP_TYPE_ORDER else len(GROUP_TYPE_ORDER)
    index_b = GROUP_TYPE_ORDER.index(b.group_type) if b.group_type in GROUP_TYPE_ORDER else len(GROUP_TYPE_ORDER)
    if index_a == index_b:
        return a
    return a if index_a < index_b else b


def _register_group(
    groups: Dict[str, DiagramGroup],
    key_lookup: Dict[str, str],
    label: str,
    group_type: Optional[str] = None,
    group_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> DiagramGroup:
    normalized_label = normalize_group_key(label)
    normalized_id = normalize_group_key(group_id)

    lookup_keys = [normalized_id, normalized_label]
    for key in lookup_keys:
        if key and key in key_lookup and key_lookup[key] in groups:
            existing_group = groups[key_lookup[key]]
            if metadata:
                existing_group.metadata.update(metadata)
            return existing_group

    resolved_id = group_id or normalized_label or f"group-{len(groups) + 1}"
    if resolved_id in groups:
        resolved_id = f"{resolved_id}-{len(groups) + 1}"

    inferred_type = infer_group_type(label, group_type)
    inferred_type = infer_group_type(label, group_type)
    default_metadata: Dict[str, Dict[str, Any]] = {
        "managementGroup": {"managementGroupId": ""},
        "subscription": {"subscriptionId": ""},
        "policyAssignment": {"policyDefinitionId": "", "scope": ""},
        "roleAssignment": {"roleDefinitionId": "", "principalId": "", "principalType": ""},
    }

    combined_metadata = {**default_metadata.get(inferred_type, {}), **(metadata or {})}

    group = DiagramGroup(
        id=resolved_id,
        label=label or resolved_id,
        group_type=inferred_type if inferred_type in GROUP_TYPE_ORDER else "default",
        metadata=combined_metadata,
        members=[],
    )
    groups[resolved_id] = group

    for key in lookup_keys:
        if key:
            key_lookup[key] = resolved_id

    return group


def build_group_structures(
    services: List[str],
    connections: List[DiagramConnection],
    raw_groups: Any = None,
) -> List[DiagramGroup]:
    groups: Dict[str, DiagramGroup] = {}
    key_lookup: Dict[str, str] = {}
    pending_parent_links: List[tuple[str, str]] = []
    pending_child_links: List[tuple[str, str]] = []

    raw_group_entries = raw_groups if isinstance(raw_groups, list) else []

    for entry in raw_group_entries:
        if not isinstance(entry, dict):
            continue

        label = entry.get("label") or entry.get("name") or entry.get("id") or f"Group {len(groups) + 1}"
        group_type = entry.get("group_type") or entry.get("type")
        group_id = entry.get("id")
        metadata = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}

        group = _register_group(groups, key_lookup, label, group_type, group_id, metadata)

        members = entry.get("members") or []
        if isinstance(members, list):
            for member in members:
                if isinstance(member, (str, int)):
                    member_str = str(member)
                    normalized_member = normalize_group_key(member_str)
                    if normalized_member:
                        pending_child_links.append((group.id, normalized_member))
                    else:
                        group.members.append(member_str)

        parent_ref = entry.get("parent_id") or entry.get("parent")
        if isinstance(parent_ref, str):
            pending_parent_links.append((group.id, normalize_group_key(parent_ref)))

    for service in services:
        inferred = infer_group_type(service)
        if inferred != "default":
            _register_group(groups, key_lookup, service, inferred)

    for child_id, parent_key in pending_parent_links:
        if not parent_key:
            continue
        parent_id = key_lookup.get(parent_key)
        if not parent_id:
            if infer_group_type(parent_key.replace("-", " ")) != "default":
                parent_group = _register_group(groups, key_lookup, parent_key.replace("-", " "))
                parent_id = parent_group.id
        if not parent_id or parent_id == child_id:
            continue
        child_group = groups.get(child_id)
        parent_group = groups.get(parent_id)
        if child_group and parent_group:
            child_group.parent_id = parent_id
            if child_group.label not in parent_group.members:
                parent_group.members.append(child_group.label)

    for parent_id, child_key in pending_child_links:
        child_id = key_lookup.get(child_key)
        if not child_id:
            if infer_group_type(child_key.replace("-", " ")) != "default":
                child_group = _register_group(groups, key_lookup, child_key.replace("-", " "))
                child_id = child_group.id
        if not child_id:
            continue
        parent_group = groups.get(parent_id)
        child_group = groups.get(child_id)
        if not parent_group or not child_group or child_group.id == parent_group.id:
            continue
        if not child_group.parent_id:
            child_group.parent_id = parent_group.id
        if child_group.label not in parent_group.members:
            parent_group.members.append(child_group.label)

    def match_group(name: str) -> Optional[DiagramGroup]:
        key = normalize_group_key(name)
        if key and key in key_lookup:
            return groups.get(key_lookup[key])
        lower = name.lower()
        for group in groups.values():
            if lower in group.label.lower() or group.label.lower() in lower:
                return group
        return None

    for connection in connections:
        from_group = match_group(connection.from_service)
        to_group = match_group(connection.to_service)

        if from_group and not to_group:
            if connection.to_service and connection.to_service not in from_group.members:
                from_group.members.append(connection.to_service)
        elif to_group and not from_group:
            if connection.from_service and connection.from_service not in to_group.members:
                to_group.members.append(connection.from_service)
        elif from_group and to_group:
            parent = _choose_parent_group(from_group, to_group)
            child = to_group if parent.id == from_group.id else from_group
            if not child.parent_id:
                child.parent_id = parent.id
            if child.label not in parent.members:
                parent.members.append(child.label)

    for group in groups.values():
        deduped = []
        seen_members = set()
        for member in group.members:
            if member in seen_members:
                continue
            seen_members.add(member)
            deduped.append(member)
        group.members = deduped

    return list(groups.values())

@router.post("/analyze-diagram", response_model=ImageAnalysisResponse)
async def analyze_diagram(request: ImageAnalysisRequest, force_model: bool = False):
    """
    Analyze an uploaded architecture diagram using OpenAI Vision API
    """
    try:
        logger.info("Received diagram analysis request")
        
        # Validate the image input
        if not request.image or not isinstance(request.image, str) or len(request.image.strip()) == 0:
            raise HTTPException(status_code=400, detail="Missing or empty image data (expected base64 string without data: prefix)")

        # Prepare the image for OpenAI Vision API
        image_data = f"data:{request.format};base64,{request.image}"

        # Create the system prompt for diagram analysis
        # Use string concatenation to avoid f-string issues with curly braces in STRUCTURED_DIAGRAM_GUIDANCE
        system_prompt = """You are an expert cloud architect analyzing architecture diagrams from multiple cloud providers.

        Your task is to:
        1. Identify every individual cloud service or feature icon visible in the diagram from Azure, AWS, or GCP — even if multiple appear inside one box (for example: Text Analytics, Translator, and Vision should each be listed separately, not grouped under 'Cognitive Services').
        2. Detect the cloud provider for each service (Azure, AWS, or GCP) based on visual branding and service names.
        3. Detect and describe all logical connections or data flows between services.
        4. Provide a concise summary of the architecture's purpose and flow.
        5. For non-Azure diagrams, suggest Azure services that could replace the detected services.
        6. **CRITICAL**: Analyze the spatial layout of services in the diagram and organize them into logical tiers (entry, app, messaging, compute, data).
        7. **GENERATE DIAGRAM JSON**: Create a complete ReactFlow Diagram JSON following the schema and positioning rules below.

        """ + STRUCTURED_DIAGRAM_GUIDANCE + """

        Return your analysis in this JSON format:
        {
            "services": [
                {
                    "name": "Service Name",
                    "provider": "azure|aws|gcp",
                    "tier": "entry|app|messaging|compute|data",
                    "position_hint": "left|center|right"
                }
            ],
            "connections": [{"from_service": "Service A", "to_service": "Service B", "label": "connection type"}],
            "description": "Brief description of the architecture",
            "suggested_services": ["Suggested Service 1", "Suggested Service 2", ...],
            "diagram_json": {
                "services": [...],
                "groups": [...],
                "connections": [...],
                "layout": "vertical|horizontal|grid"
            }
        }

        Guidelines:
        - **Multi-cloud detection**: Recognize services from Azure (blue branding), AWS (orange branding), and GCP (multi-color branding).
        - **Azure services**: Use full names (e.g., Azure Cognitive Services - Text Analytics, Azure Functions, Azure Storage, etc.).
        - **AWS services**: Use official names (e.g., AWS Lambda, Amazon S3, Amazon EC2, Amazon RDS, AWS API Gateway, etc.).
        - **GCP services**: Use official names (e.g., Google Compute Engine, Cloud Functions, Cloud Storage, Cloud SQL, BigQuery, etc.).
        - List every distinct icon or capability you see — do **not** merge icons or label groups.
        - Be specific with complete service names including provider prefix when ambiguous.
        - Use precise connection labels (Ingestion, Enrichment, Projection, Query, Indexing, Data Flow, API Call, etc.).
        - For AWS/GCP diagrams, suggest Azure equivalents in the suggested_services field.
        - **MANDATORY**: Follow all positioning rules from STRUCTURED_DIAGRAM_GUIDANCE above.
        """


        # Call OpenAI Vision API using the async client if available. We send the
        # image as an inline data:<mime>;base64,... URL in the user message text
        # so that both async OpenAI clients and simple fallbacks can process it.
        response = None
        try:
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if AsyncOpenAI is not None and openai_api_key:
                logger.info("Using AsyncOpenAI client for vision analysis")
                async_client = AsyncOpenAI(api_key=openai_api_key)
                try:
                    # Use proper OpenAI vision message format with separate image content
                    messages = [
                        {"role": "system", "content": system_prompt},
                        {
                            "role": "user", 
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Please analyze this cloud architecture diagram and:\n1. Identify all services and their connections\n2. Detect cloud provider (Azure/AWS/GCP) based on icons and branding\n3. Classify services into tiers based on their vertical position\n4. Generate a complete Diagram JSON with proper positioning following the STRUCTURED_DIAGRAM_GUIDANCE rules\n\nIMPORTANT: Ensure services in the same tier are spaced 450px apart horizontally (x-axis) and different tiers are 250px apart vertically (y-axis)."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": image_data,
                                        "detail": "high"  # Use "high" for better service recognition
                                    }
                                }
                            ]
                        }
                    ]
                    # Cast to Any to avoid strict static type mismatch with the SDK
                    from typing import Any
                    messages_any: Any = messages
                    response = await async_client.chat.completions.create(
                        model=os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07"),
                        messages=messages_any,
                        max_tokens=1500,
                        temperature=0.1
                    )
                finally:
                    # Close the async client to free resources if supported.
                    # The close helper may be sync or async depending on the SDK,
                    # so call it and await only if it returns a coroutine.
                    aclose = getattr(async_client, 'aclose', None) or getattr(async_client, 'close', None)
                    if callable(aclose):
                        try:
                            maybe_coro = aclose()
                            if asyncio.iscoroutine(maybe_coro):
                                await maybe_coro
                        except Exception:
                            pass
            else:
                # Fall back to the synchronous OpenAI client if present (best-effort)
                logger.info("AsyncOpenAI not available or OPENAI_API_KEY missing — trying sync client fallback")
                try:
                    # Some environments provide openai.OpenAI which may be sync
                    sync_client = getattr(openai, 'OpenAI', None)
                    if sync_client and os.getenv("OPENAI_API_KEY"):
                        client = sync_client(api_key=os.getenv("OPENAI_API_KEY"))
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {
                                "role": "user", 
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Please analyze this Azure architecture diagram and identify all services and their connections."
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": image_data,
                                            "detail": "low"
                                        }
                                    }
                                ]
                            }
                        ]
                        # Cast messages to Any for compatibility with different SDK shapes
                        from typing import Any
                        messages_any: Any = messages
                        response = client.chat.completions.create(
                            model=os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07"),
                            messages=messages_any,
                            max_tokens=1500,
                            temperature=0.1
                        )
                except Exception as e:
                    logger.warning("Sync OpenAI client call failed: %s", e)
                    response = None
        except Exception as e:
            logger.error("Failed to call OpenAI (vision) client: %s", e)
            response = None
        
        # Extract the response content and normalize to a string. If no model
        # response was obtained, fall back to the deterministic analyzer so the
        # frontend still receives a structured result instead of a 500.
        raw_content = None
        if response is None:
            logger.warning("No OpenAI response received — using safe deterministic fallback (no agents)")
            # Do NOT call into the agent/team code here. Return a minimal safe analysis
            # so that the frontend receives a structured payload without triggering
            # the Architect/FinalEditor agent pipelines.
            raw_content = json.dumps({
                "services": [],
                "connections": [],
                "description": "No analysis available (vision model did not return a valid response)",
                "suggested_services": [],
            })
        else:
            try:
                # Support both async/sync client shapes. Prefer structured access
                # but fall back to stringifying the response when unsure.
                choices = getattr(response, 'choices', None)
                if choices and len(choices) > 0:
                    first = choices[0]
                    msg = getattr(first, 'message', None)
                    # If message is a dict-like mapping, read keys safely
                    if isinstance(msg, dict):
                        raw_content = msg.get('content') or msg.get('text') or str(msg)
                    else:
                        # Try attribute access, otherwise stringify
                        raw_content = getattr(msg, 'content', None) or getattr(msg, 'text', None) or str(first)
                else:
                    raw_content = str(response)
            except Exception as e:
                logger.error("Failed to extract content from OpenAI response: %s", e)
                raw_content = str(response)

        def normalize_content(c):
            # If it's already a string, return it
            if isinstance(c, str):
                return c
            # If it's a list of items, extract textual parts
            if isinstance(c, (list, tuple)):
                parts = []
                for item in c:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        # Common shapes: {'type':'text','text':'...'} or {'text': '...'}
                        if 'text' in item and isinstance(item['text'], str):
                            parts.append(item['text'])
                        elif 'content' in item and isinstance(item['content'], str):
                            parts.append(item['content'])
                        else:
                            parts.append(str(item))
                    else:
                        parts.append(str(item))
                return '\n'.join(parts)
            # If it's a dict, try common keys
            if isinstance(c, dict):
                if 'content' in c and isinstance(c['content'], str):
                    return c['content']
                if 'text' in c and isinstance(c['text'], str):
                    return c['text']
                # fallback to string repr
                return json.dumps(c)
            # fallback
            return str(c)

        analysis_text = normalize_content(raw_content)
        logger.info('OpenAI Vision analysis (type=%s, len=%d): %s', type(raw_content).__name__, len(analysis_text or ''), analysis_text[:1000])

        # Parse the JSON response robustly (strip Markdown/code fences, extract JSON block)
        analysis_json = extract_json_from_text(analysis_text)
        if analysis_json is None:
            # If JSON parsing fails, avoid invoking agent/team fallbacks.
            # Produce a conservative structured response derived from the raw
            # analysis_text so the frontend can still show something useful
            # without triggering additional agent workflows.
            logger.warning("Failed to parse JSON response; returning safe structured fallback")
            # Try to heuristically extract service names if present in text
            try:
                # Find quoted fragments that look like service names
                possible = re.findall(r"\b([A-Z][A-Za-z0-9 \-\+&]+Service[s]?|AWS [A-Za-z0-9]+|Amazon [A-Za-z0-9]+|Google [A-Za-z0-9]+)\b", analysis_text or "")
                services = list(dict.fromkeys([s.strip() for s in possible if s and len(s) > 2]))
            except Exception:
                services = []
            analysis_json = {
                "services": services,
                "connections": [],
                "description": (analysis_text or "").strip()[:200] + "...",
                "suggested_services": []
            }
        # --- Expand grouped or generic service names into detailed sub-services ---
        EXPANSION_MAP = {
            "Azure Cognitive Services": [
                "Azure Cognitive Services - Text Analytics",
                "Azure Cognitive Services - Translator",
                "Azure Cognitive Services - Vision"
            ],
            "Cognitive Services": [
                "Azure Cognitive Services - Text Analytics",
                "Azure Cognitive Services - Translator",
                "Azure Cognitive Services - Vision"
            ],
            "AI Search": ["Azure AI Search (Cognitive Search)"],
            "Azure AI Search": ["Azure AI Search (Cognitive Search)"],
            "AI Document Intelligence": ["Azure AI Document Intelligence (Form Recognizer)"],
            "Document Intelligence": ["Azure AI Document Intelligence (Form Recognizer)"]
        }

        expanded_services = []
        services_list = analysis_json.get("services", [])
        
        # Handle both old format (list of strings) and new format (list of dicts)
        for s in services_list:
            # Extract service name whether it's a string or dict
            if isinstance(s, dict):
                service_name = s.get("name", "")
            else:
                service_name = str(s) if s else ""
            
            if service_name:
                expanded_services.extend(EXPANSION_MAP.get(service_name, [service_name]))

        # Deduplicate while preserving order
        analysis_json["services"] = list(dict.fromkeys(expanded_services))
        # Normalize and convert connections to the expected format
        raw_connections = normalize_connections(analysis_json)
        connections = [DiagramConnection(
            from_service=rc.get("from_service", ""),
            to_service=rc.get("to_service", ""),
            label=rc.get("label", "connection")
        ) for rc in raw_connections]

        raw_groups = analysis_json.get("groups") or analysis_json.get("groupings") or []
        groups = build_group_structures(analysis_json.get("services", []), connections, raw_groups)

        # Create the analysis result
        result = DiagramAnalysisResult(
            services=analysis_json.get("services", []),
            connections=connections,
            description=analysis_json.get("description", "Architecture diagram analyzed"),
            suggested_services=analysis_json.get("suggested_services", []),
            groups=groups
        )

        logger.info(
            "Successfully analyzed diagram: %d services, %d connections, %d groups",
            len(result.services),
            len(result.connections),
            len(result.groups),
        )

        return ImageAnalysisResponse(analysis=result)
        
    except Exception as e:
        logger.error(f"Error analyzing diagram: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze diagram: {str(e)}")
