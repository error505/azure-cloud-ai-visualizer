import json
from typing import Annotated

from datetime import datetime

from pydantic import Field

def analyze_image_for_architecture(
    image_url: Annotated[str, Field(description="URL of the architecture diagram image")],
    target_region: Annotated[str, Field(description="Target Azure region")] = "westeurope"
) -> str:
    """Analyze an uploaded architecture diagram image and create a properly spaced ReactFlow Diagram JSON.
    
    CRITICAL POSITIONING RULES when generating Diagram JSON from the analyzed image:
    - Services in the same tier MUST be spaced at least 450px apart horizontally (x-axis)
    - Different tiers MUST be spaced at least 250px apart vertically (y-axis)
    - Use exact tier coordinates: entry (y=100), app (y=350), messaging (y=600), compute (y=850), data (y=1100)
    - Horizontal formula: x = 150 + (service_index_in_tier * 450)
    - Example: 3 services in same tier should be at x = 150, 600, 1050
    - Services must be distributed horizontally, NOT stacked vertically in the same tier
    """
    try:
        # This function will be used with vision-capable models
        # The actual image analysis will be done by the LLM with vision capabilities
        analysis = {
            "image_url": image_url,
            "target_region": target_region,
            "analysis_type": "architecture_diagram",
            "timestamp": datetime.now().isoformat(),
            "positioning_rules": {
                "min_horizontal_spacing": 450,
                "min_vertical_spacing": 250,
                "tier_y_coordinates": {"entry": 100, "app": 350, "messaging": 600, "compute": 850, "data": 1100},
                "horizontal_formula": "x = 150 + (index * 450)"
            },
            "note": "Image analysis will be performed by the AI model with vision capabilities. Ensure proper spacing in the generated Diagram JSON."
        }
        
        return json.dumps(analysis, indent=2)
        
    except Exception as e:
        return f"Error analyzing image: {str(e)}"

