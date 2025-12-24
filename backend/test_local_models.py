"""
Test script for local model integration (Ollama or Foundry Local).

Usage:
    # Test Ollama
    USE_OLLAMA=true OLLAMA_MODEL=llama2 python test_local_models.py

    # Test Foundry Local
    USE_FOUNDRY_LOCAL=true python test_local_models.py
"""

import asyncio
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def test_local_model():
    """Test local model client initialization and basic chat."""
    print("=" * 60)
    print("Local Model Integration Test")
    print("=" * 60)
    
    # Import after path adjustment
    from app.agents.clients.local_model_client import get_local_model_client
    from app.agents.azure_architect_agent import AzureArchitectAgent
    
    # Get local model client
    print("\n1. Initializing local model client...")
    client = get_local_model_client()
    
    if not client:
        print("❌ ERROR: No local model backend enabled!")
        print("\nSet one of these environment variables:")
        print("  USE_OLLAMA=true OLLAMA_URL=http://localhost:11434 OLLAMA_MODEL=llama2")
        print("  USE_FOUNDRY_LOCAL=true FOUNDRY_LOCAL_ALIAS=qwen2.5-0.5b")
        return
    
    print(f"✓ Local model client initialized")
    print(f"  Backend: {client.backend}")
    print(f"  Model: {client.model}")
    
    # Create agent
    print("\n2. Creating Azure Architect Agent with local model...")
    agent = AzureArchitectAgent(agent_client=client)
    await agent.initialize()
    print("✓ Agent initialized successfully")
    
    # Test simple chat
    print("\n3. Testing simple chat...")
    prompt = "Explain Azure Virtual Networks in one sentence."
    print(f"Prompt: {prompt}")
    print("\nResponse:")
    
    try:
        response = await agent.chat(prompt)
        print(f"✓ {response[:200]}...")  # Print first 200 chars
    except Exception as e:
        print(f"❌ Chat failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test streaming
    print("\n4. Testing streaming chat...")
    prompt_stream = "List 3 Azure services in bullet points."
    print(f"Prompt: {prompt_stream}")
    print("\nStreaming response:")
    
    try:
        chunks = []
        async for chunk in agent.stream_chat(prompt_stream):
            print(chunk, end='', flush=True)
            chunks.append(chunk)
        print("\n✓ Streaming completed successfully")
    except Exception as e:
        print(f"\n❌ Streaming failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test diagram generation (lightweight test)
    print("\n5. Testing diagram generation (simplified prompt)...")
    diagram_prompt = (
        "Design a simple 3-tier web application with:\n"
        "- Web tier (App Service)\n"
        "- Database tier (SQL Database)\n"
        "- Include proper Diagram JSON format"
    )
    
    try:
        response = await agent.chat(diagram_prompt)
        
        # Check if Diagram JSON section exists
        if "Diagram JSON" in response or "diagram" in response.lower():
            print("✓ Diagram generation response received")
            
            # Try to find JSON block
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL | re.IGNORECASE)
            if json_match:
                import json
                try:
                    diagram_data = json.loads(json_match.group(1))
                    services_count = len(diagram_data.get('services', []))
                    connections_count = len(diagram_data.get('connections', []))
                    groups_count = len(diagram_data.get('groups', []))
                    
                    print(f"  Services: {services_count}")
                    print(f"  Connections: {connections_count}")
                    print(f"  Groups: {groups_count}")
                    
                    # Check for metadata we added in prompts
                    if services_count > 0:
                        first_service = diagram_data['services'][0]
                        has_position = 'position' in first_service
                        has_data = 'data' in first_service
                        print(f"  Position metadata: {'✓' if has_position else '❌'}")
                        print(f"  Data metadata: {'✓' if has_data else '❌'}")
                        
                    if connections_count > 0:
                        first_conn = diagram_data['connections'][0]
                        has_handles = 'sourceHandle' in first_conn and 'targetHandle' in first_conn
                        has_style = 'style' in first_conn
                        print(f"  Connection handles: {'✓' if has_handles else '❌'}")
                        print(f"  Connection style: {'✓' if has_style else '❌'}")
                        
                    print("✓ Valid Diagram JSON generated")
                except json.JSONDecodeError as e:
                    print(f"⚠ Diagram JSON parsing failed: {e}")
            else:
                print("⚠ No JSON block found in response")
        else:
            print("⚠ No diagram section found in response")
    except Exception as e:
        print(f"❌ Diagram generation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("✓ All tests completed successfully!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start the backend: uvicorn main:app --reload --port 8000")
    print("2. Open the frontend and test full multi-agent workflows")
    print("3. Monitor response quality and adjust model selection as needed")


if __name__ == "__main__":
    asyncio.run(test_local_model())
