"""Simple OpenAI-based IaC generation endpoint (no agent-framework dependency).

AI-ONLY endpoint. If OPENAI_API_KEY is set, this endpoint will call the OpenAI API directly
with a structured prompt containing the diagram JSON and extract a JSON
object with bicep_code/terraform_code. NO DETERMINISTIC FALLBACKS.
"""
from __future__ import annotations
import os, json, logging
from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter()

class IaCGenerateRequest(BaseModel):
    diagram_data: Dict[str, Any]
    target_format: str = "bicep"
    include_monitoring: bool = True
    include_security: bool = True
    resource_naming_convention: str = "standard"
    service_configs: Dict[str, Any] | None = None

class IaCResponse(BaseModel):
    id: str
    format: str
    content: str
    parameters: Dict[str, Any]
    created_at: datetime
    project_id: str | None = None


@router.post("/generate", response_model=IaCResponse)
async def generate_iac_simple(req: IaCGenerateRequest) -> IaCResponse:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
    
    if not api_key or not OpenAI:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured or OpenAI package not available")

    diagram = req.diagram_data if isinstance(req.diagram_data, dict) else {}
    target = (req.target_format or 'bicep').lower()
    
    # Merge service_configs into node data
    if req.service_configs and isinstance(diagram.get('nodes'), list):
        for n in diagram.get('nodes', []):
            nid = n.get('id') or (n.get('data') or {}).get('id')
            if not nid:
                continue
            sc = req.service_configs.get(nid)
            if sc and isinstance(n.get('data'), dict):
                n['data'].update(sc)

    content = ""
    parameters: Dict[str, Any] = {}
    
    try:
        client = OpenAI(api_key=api_key)
        
        if target == 'bicep':
            instruction = (
                "You are an Azure IaC generator. Given the JSON under 'diagram', generate a comprehensive Bicep template. "
                "Return ONLY JSON with keys 'bicep_code' (string) and 'parameters' (object). Do not include markdown fences."
            )
            code_key = 'bicep_code'
        elif target == 'terraform':
            instruction = (
                "You are an Azure IaC generator. Given the JSON under 'diagram', generate a comprehensive Terraform (HCL) configuration. "
                "Return ONLY JSON with keys 'terraform_code' (string) and 'parameters' (object). Do not include markdown fences."
            )
            code_key = 'terraform_code'
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported target format: {target}")
            
        payload = {"diagram": diagram, "requirements": {"include_monitoring": req.include_monitoring, "include_security": req.include_security}}
        messages = [
            {"role": "system", "content": instruction},
            {"role": "user", "content": json.dumps(payload)}
        ]
        resp = client.chat.completions.create(model=model, messages=messages, temperature=0.2)
        text = resp.choices[0].message.content if resp.choices else ""
        
        if not text:
            raise HTTPException(status_code=500, detail="AI generation failed - no response from model")
            
        logger.debug("Raw OpenAI response: %s", text[:2000])

        # Try parse JSON
        def extract_json(txt: str):
            start = txt.find("{")
            if start == -1: return None
            depth = 0
            for i, ch in enumerate(txt[start:]):
                if ch == '{': depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = start + i + 1
                        try:
                            return json.loads(txt[start:end])
                        except Exception:
                            return None
            return None
            
        parsed = extract_json(text)
        if not parsed:
            try:
                parsed = json.loads(text) if text.strip().startswith('{') else None
            except:
                parsed = None
                
        if parsed and isinstance(parsed, dict) and parsed.get(code_key):
            content = parsed.get(code_key, "")
            parameters = parsed.get("parameters", {})
            parameters["generation_path"] = "openai"
        else:
            raise HTTPException(status_code=500, detail=f"AI generation failed - no valid {code_key} in response")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

    return IaCResponse(
        id="simple-openai",
        format=target,
        content=content,
        parameters=parameters,
        created_at=datetime.utcnow(),
        project_id=None,
    )
