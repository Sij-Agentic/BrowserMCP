# browser/browser.py
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.append('/Users/sijpapi/codebase/eag/S12')

from agent.agentSession import AgentSession
from utils.utils import log_step, log_error
from utils.json_parser import parse_llm_json
from agent.model_manager import ModelManager

class Browser:
    def __init__(self, navigation_prompt_path: str, action_prompt_path: str, multi_mcp):
        self.navigation_prompt_path = navigation_prompt_path
        self.action_prompt_path = action_prompt_path
        self.multi_mcp = multi_mcp
        self.model = ModelManager()

    async def run(self, b_input: dict, session: Optional[AgentSession] = None) -> dict:
        # STAGE 1: Navigation and Element Discovery
        log_step("[STARTING NAVIGATION STAGE...]", symbol="→")
        navigation_result = await self._execute_navigation_stage(b_input, session)
        if not navigation_result.get("success", False):
            return navigation_result
            
        # Get interactive elements after navigation
        log_step("[RETRIEVING INTERACTIVE ELEMENTS...]", symbol="→")
        elements = await self._get_interactive_elements(session)
        log_step(f"[FOUND {len(elements['context'])} INTERACTIVE ELEMENTS]", symbol="←")
        
        # STAGE 2: Action Planning and Execution
        log_step("[STARTING ACTION STAGE...]", symbol="→")
        action_result = await self._execute_action_stage(b_input, elements, session)
        
        # Combine results
        return {
            "success": navigation_result.get("success", False) and action_result.get("success", False),
            "navigation_results": navigation_result.get("results", []),
            "action_results": action_result.get("results", []),
            "summary": self._generate_summary(
                navigation_result.get("results", []) + action_result.get("results", [])
            )
        }
        
    async def _execute_navigation_stage(self, b_input: dict, session: Optional[AgentSession] = None) -> dict:
        """Execute the navigation stage to open the page and prepare for actions"""
        prompt_template = Path(self.navigation_prompt_path).read_text(encoding="utf-8")
        full_prompt = (
            f"{prompt_template.strip()}\n\n"
            "```json\n"
            f"{json.dumps(b_input, indent=2)}\n"
            "```"
        )
        
        log_step("[SENDING NAVIGATION PROMPT TO BROWSER AGENT...]", symbol="→")
        response = await self.model.generate_text(prompt=full_prompt)
        log_step("[RECEIVED NAVIGATION PLAN FROM BROWSER AGENT...]", symbol="←")
        
        try:
            print("Navigation response:", response)
            navigation_plan = parse_llm_json(response)
            print("Navigation plan:", json.dumps(navigation_plan, indent=2))
            return await self._execute_browser_plan(navigation_plan, session)
        except Exception as e:
            log_error("🛑 EXCEPTION IN NAVIGATION STAGE:", e)
            return {
                "success": False,
                "error": str(e),
                "result": "Navigation stage failed."
            }
            
    async def _get_interactive_elements(self, session: Optional[AgentSession] = None) -> list:
        """Get interactive elements from the current page"""
        try:
            result = await self.multi_mcp.call_tool("get_interactive_elements", {})
            # Make sure the result is serializable
            serializable_result = self._make_serializable(result)
            print("Interactive elements:", json.dumps(serializable_result, indent=2))
            return serializable_result
        except Exception as e:
            log_error("🛑 ERROR GETTING INTERACTIVE ELEMENTS:", e)
            return []
            
    async def _execute_action_stage(self, b_input: dict, elements: list, session: Optional[AgentSession] = None) -> dict:
        """Execute the action stage using the actual elements on the page"""
        # Combine original input with elements
        action_input = {
            **b_input,
            "interactive_elements": elements
        }
        
        prompt_template = Path(self.action_prompt_path).read_text(encoding="utf-8")
        full_prompt = (
            f"{prompt_template.strip()}\n\n"
            "```json\n"
            f"{json.dumps(action_input, indent=2)}\n"
            "```"
        )
        
        log_step("[SENDING ACTION PROMPT TO BROWSER AGENT...]", symbol="→")
        response = await self.model.generate_text(prompt=full_prompt)
        log_step("[RECEIVED ACTION PLAN FROM BROWSER AGENT...]", symbol="←")
        
        try:
            print("Action response:", response)
            action_plan = parse_llm_json(response)
            print("Action plan:", json.dumps(action_plan, indent=2))
            return await self._execute_browser_plan(action_plan, session)
        except Exception as e:
            log_error("🛑 EXCEPTION IN ACTION STAGE:", e)
            return {
                "success": False,
                "error": str(e),
                "result": "Action stage failed."
            }
    
    async def _execute_browser_plan(self, browser_plan: dict, session: Optional[AgentSession] = None) -> dict:
        """Execute the browser plan using existing MCP tools"""
        results = []
        
        log_step("🔍 Browser plan to execute:", symbol="→")
        log_step(json.dumps(browser_plan, indent=2), symbol="")
        
        # Execute each step in the plan
        for step in browser_plan.get("steps", []):
            tool_name = step.get("tool")
            params = step.get("params", {})
            
            log_step(f"📡 Executing browser tool: {tool_name}", symbol="→")
            log_step(f"📡 With params: {json.dumps(params, indent=2)}", symbol="")
            
            try:
                # Use existing MCP infrastructure to call browser tools directly
                # Convert params dict to the arguments format expected by call_tool
                log_step(f"📡 Calling MultiMCP.call_tool({tool_name}, {params})", symbol="→")
                result = await self.multi_mcp.call_tool(tool_name, params)
                log_step(f"📡 Tool result received: {type(result)}", symbol="←")
                
                # Convert non-serializable objects to strings
                serializable_result = self._make_serializable(result)
                
                results.append({
                    "step": step,
                    "success": True,
                    "result": serializable_result
                })
            except Exception as e:
                log_error(f"🛑 Error executing browser tool {tool_name}:", e)
                results.append({
                    "step": step,
                    "success": False,
                    "error": str(e)
                })
                
                # Check if we should continue on error
                if not browser_plan.get("continue_on_error", False):
                    break
        
        return {
            "success": all(r.get("success", False) for r in results),
            "results": results,
            "summary": self._generate_summary(results)
        }
    
    def _make_serializable(self, obj):
        """Convert non-serializable objects to serializable formats"""
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        # Special handling for CallToolResult objects
        elif hasattr(obj, '__dict__'):
            # Convert object to dictionary and then make it serializable
            obj_dict = {}
            for k, v in obj.__dict__.items():
                if not k.startswith('_'):  # Skip private attributes
                    obj_dict[k] = self._make_serializable(v)
            return obj_dict
        else:
            # Convert any other type to string representation
            return str(obj)
    
    def _generate_summary(self, results: list) -> str:
        """Generate a summary of the browser actions"""
        successful_steps = sum(1 for r in results if r.get("success", False))
        total_steps = len(results)
        
        if successful_steps == total_steps:
            return f"Successfully completed all {total_steps} browser actions."
        else:
            return f"Completed {successful_steps} of {total_steps} browser actions. Some actions failed."

def build_browser_input(query, ctx):
    """Build input for the browser agent"""
    return {
        "query": query,
        "browser_context": ctx.globals.get("browser_context", {}),
        "current_url": ctx.globals.get("current_url", ""),
        "available_tools": [
            "open_tab", "go_to_url", "go_back", "search_google",
            "click_element_by_index", "input_text", "send_keys",
            "scroll_down", "scroll_up", "scroll_to_text",
            "switch_tab", "close_tab", "get_dropdown_options",
            "select_dropdown_option", "drag_drop",
            "get_enhanced_page_structure", "get_comprehensive_markdown",
            "save_pdf", "wait", "done", "get_session_snapshot",
            "take_screenshot", "get_interactive_elements"
        ]
    }