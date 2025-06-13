#!/usr/bin/env python3
"""
Test script for the Browser agent.
This allows testing the Browser agent in isolation.
"""

import os
import sys
import json
import yaml
import asyncio
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.append(str(Path(__file__).parent.parent))

from browser import Browser, build_browser_input
from agent.contextManager import ContextManager
from mcp_servers.multiMCP import MultiMCP

async def test_browser_agent():
    """Test the Browser agent with a sample query."""
    print("🧪 Testing Browser Agent...")
    
    # Load MCP server configs
    with open(Path(__file__).parent.parent / "config" / "mcp_server_config.yaml", "r") as f:
        profile = yaml.safe_load(f)
        mcp_servers_list = profile.get("mcp_servers", [])
        configs = list(mcp_servers_list)

    # Initialize MultiMCP
    multi_mcp = MultiMCP(server_configs=configs)
    await multi_mcp.initialize()
    
    try:
        # Create a browser agent with navigation and action prompts
        navigation_prompt_path = "prompts/browser_navigation_prompt.txt"
        action_prompt_path = "prompts/browser_action_prompt.txt"
        browser_agent = Browser(navigation_prompt_path, action_prompt_path, multi_mcp)
        
        # Create a test context
        ctx = ContextManager("test_session", "Test query")
        ctx.globals["current_url"] = "https://example.com"
        
        # Sample query
        query = "Go to Google and search for 'Python programming'"
        
        try:
            # Build browser input
            b_input = build_browser_input(query, ctx)
            
            # Run the browser agent
            print(f"📝 Running browser agent with query: {query}")
            result = await browser_agent.run(b_input)
            
            # Print the result
            print("\n🔍 Browser Agent Result:")
            # Convert result to JSON-serializable format if needed
            result_serializable = {}
            for key, value in result.items():
                if key == "results":
                    # Handle results list specially
                    result_serializable[key] = []
                    for item in value:
                        item_serializable = {}
                        for k, v in item.items():
                            # Convert any non-serializable objects to strings
                            if k == "result" and not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                                item_serializable[k] = str(v)
                            else:
                                item_serializable[k] = v
                        result_serializable[key].append(item_serializable)
                else:
                    result_serializable[key] = value
            
            print(json.dumps(result_serializable, indent=2))
            
        except Exception as e:
            print(f"❌ Error testing browser agent: {e}")
    finally:
        # Ensure MultiMCP is always shut down properly
        try:
            # Use a new event loop for shutdown to avoid cancel scope issues
            await asyncio.shield(multi_mcp.shutdown())
        except Exception as e:
            print(f"⚠️ Warning: Error during MultiMCP shutdown: {e}")
            # Continue execution even if shutdown fails

if __name__ == "__main__":
    asyncio.run(test_browser_agent())
