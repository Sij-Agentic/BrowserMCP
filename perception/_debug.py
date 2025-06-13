#!/usr/bin/env python3
"""
Debug script for the Perception module.
This isolates the perception module to test for API connectivity issues.
"""

import os
import sys
import json
import asyncio
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.append(str(Path(__file__).parent.parent))

from perception import Perception, build_perception_input
from agent.contextManager import ContextManager
from agent.model_manager import ModelManager

async def test_model_directly():
    """Test the model connection directly without perception."""
    print("🧪 Testing Model Connection Directly...")
    
    model_manager = ModelManager()
    
    try:
        # Simple prompt to test connectivity
        response = await model_manager.generate_text("Hello, please respond with a simple 'Hello world!'")
        print(f"✅ Model response: {response}")
        return True
    except Exception as e:
        print(f"❌ Model connection error: {e}")
        return False

async def test_perception():
    """Test the perception module with a simple query."""
    print("🧪 Testing Perception Module...")
    
    # Create a perception instance
    perception_prompt_path = "prompts/perception_prompt.txt"
    perception = Perception(perception_prompt_path)
    
    # Create a test context
    ctx = ContextManager("test_session", "Test query")
    
    # Sample query
    query = "What is the weather today?"
    
    # Build perception input
    p_input = build_perception_input(query, None, ctx)
    
    try:
        # Run perception
        print(f"📝 Running perception with query: {query}")
        result = await perception.run(p_input)
        
        # Print the result
        print("\n🔍 Perception Result:")
        print(json.dumps(result, indent=2))
        return True
        
    except Exception as e:
        print(f"❌ Error testing perception: {e}")
        return False

async def main():
    """Run all tests."""
    print("🔍 Starting Perception Debug Tests...")
    
    # Test model connection directly
    model_ok = await test_model_directly()
    
    if model_ok:
        print("\n✅ Model connection successful!")
        
        # Test perception if model is working
        perception_ok = await test_perception()
        
        if perception_ok:
            print("\n✅ Perception test successful!")
        else:
            print("\n❌ Perception test failed but model connection works!")
            print("This suggests an issue with the perception module or prompt.")
    else:
        print("\n❌ Model connection failed!")
        print("This suggests an API key issue, network problem, or service outage.")
    
    print("\n🔍 Debug Tests Complete")

if __name__ == "__main__":
    asyncio.run(main())
