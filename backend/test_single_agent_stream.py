"""
Test script to verify token streaming from a single agent.
Run: python test_single_agent_stream.py
"""
import asyncio
import sys
import logging
from app.core.azure_client import AzureClientManager
from app.core.config import settings

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


async def test_single_agent_streaming():
    """Test streaming with a single agent to verify token-by-token output."""
    
    print("\n" + "="*80)
    print("STREAMING TEST: Single Agent Token-by-Token Verification")
    print("="*80 + "\n")
    
    # Initialize Azure clients
    print("[1/4] Initializing Azure client manager...")
    azure_clients = AzureClientManager()
    await azure_clients.initialize()
    
    # Get the architect agent
    print("[2/4] Getting Azure Architect Agent...")
    agent = azure_clients.get_azure_architect_agent()
    
    if not agent:
        print("❌ ERROR: Failed to get agent instance")
        return
    
    print(f"✓ Agent instance: {type(agent).__name__}")
    print(f"✓ Agent has stream_chat method: {hasattr(agent, 'stream_chat')}")
    
    # Simple test prompt
    test_prompt = "Explain Azure App Service in 2 sentences."
    
    print(f"\n[3/4] Test prompt: '{test_prompt}'")
    print("[4/4] Starting streaming run...\n")
    print("-" * 80)
    
    try:
        # Check if agent has stream_chat method
        if not hasattr(agent, 'stream_chat'):
            print("❌ ERROR: Agent does not have 'stream_chat' method")
            print(f"Available methods: {[m for m in dir(agent) if not m.startswith('_')]}")
            return
        
        token_count = 0
        full_response = ""
        
        print("STREAMING OUTPUT:")
        print("-" * 80)
        
        # Stream tokens
        async for chunk in agent.stream_chat(test_prompt):
            token_count += 1
            
            # stream_chat yields string chunks directly
            print(f"\n[CHUNK {token_count}] Type: {type(chunk)}")
            print(f"[CHUNK {token_count}] Content: {repr(chunk[:200] if isinstance(chunk, str) else chunk)}")
            
            if isinstance(chunk, str):
                full_response += chunk
                # Print the token inline (no newline)
                sys.stdout.write(chunk)
                sys.stdout.flush()
            else:
                print(f"[CHUNK {token_count}] ⚠ Unexpected type: {type(chunk)}")
        
        print("\n" + "-" * 80)
        print(f"\n✓ Streaming completed!")
        print(f"✓ Total tokens/events received: {token_count}")
        print(f"✓ Full response length: {len(full_response)} characters")
        print(f"\nFull response:\n{full_response}")
        
    except Exception as e:
        print(f"\n❌ ERROR during streaming: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(test_single_agent_streaming())
