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
from browser.browser_logger import (
    log_separator, log_navigation_start, log_navigation_plan, 
    log_navigation_result, log_interactive_elements, log_action_start, 
    log_action_plan, log_action_result, log_tool_execution, 
    log_error as browser_log_error, log_workflow_complete
)

class Browser:
    def __init__(self, navigation_prompt_path: str, action_prompt_path: str, multi_mcp):
        self.navigation_prompt_path = navigation_prompt_path
        self.action_prompt_path = action_prompt_path
        self.multi_mcp = multi_mcp
        self.model = ModelManager()

    async def run(self, b_input: dict, session: Optional[AgentSession] = None, max_iterations: int = 10) -> dict:
        # Log the input request
        log_separator("BROWSER AGENT RUN START")
        log_navigation_start(b_input.get("query", "No query provided"))
        
        # STAGE 1: Navigation and Element Discovery
        log_step("[STARTING NAVIGATION STAGE...]", symbol="→")
        navigation_result = await self._execute_navigation_stage(b_input, session)
        if not navigation_result.get("success", False):
            log_workflow_complete(False, "Navigation stage failed")
            return navigation_result
            
        # Get interactive elements after navigation
        log_step("[RETRIEVING INTERACTIVE ELEMENTS...]", symbol="→")
        elements = await self._get_interactive_elements(session)
        log_step(f"[FOUND {len(elements['content'])} INTERACTIVE ELEMENTS]", symbol="←")
        # Log the interactive elements
        log_interactive_elements(elements, "AFTER NAVIGATION")
        
        # Initialize results collection
        all_results = []
        all_results.extend(navigation_result.get("results", []))
        
        # STAGE 2: Iterative Action Planning and Execution
        # We'll run multiple iterations to handle multi-step UI workflows
        current_iteration = 0
        b_input_with_history = b_input.copy()
        b_input_with_history["action_history"] = []
        task_complete = False
        
        while current_iteration < max_iterations and not task_complete:
            current_iteration += 1
            log_step(f"[STARTING ACTION STAGE (ITERATION {current_iteration}/{max_iterations})...]", symbol="→")
            # Log the start of this action iteration
            log_action_start(current_iteration, max_iterations)
            
            # Add previous actions to context for the LLM
            if current_iteration > 1:
                log_step(f"[PROVIDING CONTEXT FROM {len(b_input_with_history['action_history'])} PREVIOUS ACTIONS]", symbol="→")
            
            # Execute action stage with current elements
            action_result = await self._execute_action_stage(b_input_with_history, elements, session)
            
            # Store results
            if "results" in action_result:
                all_results.extend(action_result.get("results", []))
            
            # Update action history
            if "steps" in action_result:
                b_input_with_history["action_history"].append({
                    "iteration": current_iteration,
                    "steps": action_result.get("steps", [])
                })
            
            # Check if we need to continue
            if not action_result.get("success", False):
                log_step(f"[ACTION STAGE FAILED ON ITERATION {current_iteration}]", symbol="❌")
                break
            
            # Check if the action plan indicates completion
            # This could be explicit in the action_result or determined by analyzing the steps
            last_steps = action_result.get("steps", [])
            
            # Check if the last step is not get_interactive_elements or wait
            # If so, we assume the task is complete
            if last_steps and len(last_steps) > 0:
                last_step = last_steps[-1]
                last_tool = last_step.get("tool", "")
                if last_tool not in ["get_interactive_elements", "wait"]:
                    task_complete = True
                    log_step(f"[TASK COMPLETED ON ITERATION {current_iteration}]", symbol="✅")
                    break
            
            if current_iteration < max_iterations and not task_complete:
                # Get updated interactive elements for next iteration
                log_step("[RETRIEVING UPDATED INTERACTIVE ELEMENTS...]", symbol="→")
                elements = await self._get_interactive_elements(session)
                log_step(f"[FOUND {len(elements['content'])} UPDATED INTERACTIVE ELEMENTS]", symbol="←")
                # Log the updated interactive elements
                log_interactive_elements(elements, f"AFTER ITERATION {current_iteration}")
        
        # Combine results
        success = navigation_result.get("success", False) and (task_complete or current_iteration >= max_iterations)
        summary = self._generate_summary(all_results)
        
        # Log workflow completion
        log_workflow_complete(success, summary)
        
        return {
            "success": success,
            "iterations_completed": current_iteration,
            "results": all_results,
            "summary": summary
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
            
            # Log the navigation plan
            log_navigation_plan(navigation_plan)
            
            # Execute the plan
            result = await self._execute_browser_plan(navigation_plan, session)
            
            # Log the navigation result
            log_navigation_result(result)
            
            return result
        except Exception as e:
            log_error("🛑 EXCEPTION IN NAVIGATION STAGE:", e)
            browser_log_error("EXCEPTION IN NAVIGATION STAGE", e)
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
            
            # Log the interactive elements
            log_interactive_elements(serializable_result, "RAW ELEMENTS")
            
            return serializable_result
        except Exception as e:
            log_error("🛑 ERROR GETTING INTERACTIVE ELEMENTS:", e)
            browser_log_error("ERROR GETTING INTERACTIVE ELEMENTS", e)
            return []
            
    async def _execute_action_stage(self, b_input: dict, elements: dict, session: Optional[AgentSession] = None) -> dict:
        """Execute the action stage using the actual elements on the page"""
        # Process the interactive elements to make them more usable for the LLM
        processed_elements = self._process_interactive_elements(elements)
        
        # Combine original input with processed elements
        action_input = {
            **b_input,
            "interactive_elements": processed_elements
        }
        
        # Add iteration context if available
        iteration_context = ""
        if "action_history" in b_input and len(b_input["action_history"]) > 0:
            iteration_context = "\n\nPrevious actions:\n" + json.dumps(b_input["action_history"], indent=2)
        
        # Remove action_history from the JSON to avoid making the prompt too large
        if "action_history" in action_input:
            del action_input["action_history"]
        
        prompt_template = Path(self.action_prompt_path).read_text(encoding="utf-8")
        full_prompt = (
            f"{prompt_template.strip()}\n\n"
            "```json\n"
            f"{json.dumps(action_input, indent=2)}\n"
            "```"
            f"{iteration_context}"
        )
        
        log_step("[SENDING ACTION PROMPT TO BROWSER AGENT...]", symbol="→")
        response = await self.model.generate_text(prompt=full_prompt)
        log_step("[RECEIVED ACTION PLAN FROM BROWSER AGENT...]", symbol="←")
        
        try:
            print("Action response:", response)
            action_plan = parse_llm_json(response)
            print("Action plan:", json.dumps(action_plan, indent=2))
            
            # Log the action plan
            log_action_plan(action_plan)
            
            # Execute the browser plan
            result = await self._execute_browser_plan(action_plan, session)
            
            # Add steps to the result for tracking
            result["steps"] = action_plan.get("steps", [])
            
            # Log the action result
            log_action_result(result)
            
            return result
        except Exception as e:
            log_error("🛑 EXCEPTION IN ACTION STAGE:", e)
            browser_log_error("EXCEPTION IN ACTION STAGE", e)
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
                
                # Log the tool execution
                log_tool_execution(tool_name, params, serializable_result)
                
                results.append({
                    "step": step,
                    "success": True,
                    "result": serializable_result
                })
            except Exception as e:
                log_error(f"🛑 Error executing browser tool {tool_name}:", e)
                browser_log_error(f"Error executing browser tool {tool_name}", e)
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
        elif hasattr(obj, "model_dump"):
            return self._make_serializable(obj.model_dump())
        elif hasattr(obj, "to_dict"):
            return self._make_serializable(obj.to_dict())
        elif hasattr(obj, "__dict__"):
            # Convert object to dictionary and then make it serializable
            obj_dict = {}
            for k, v in obj.__dict__.items():
                if not k.startswith('_'):  # Skip private attributes
                    obj_dict[k] = self._make_serializable(v)
            return obj_dict
        # For any other types, convert to string
        return str(obj)
        
    def _process_interactive_elements(self, elements):
        """Process interactive elements to make them more usable for the LLM"""
        try:
            # If elements is already a well-structured object, return it
            if isinstance(elements, dict) and "content" in elements:
                content = elements.get("content", [])
                
                # If content is a list of objects with text fields, extract and parse them
                if isinstance(content, list) and len(content) > 0:
                    # Extract the text content from each element
                    elements_text = ""
                    for item in content:
                        if isinstance(item, dict) and "text" in item:
                            elements_text += item["text"] + "\n"
                    
                    # Parse the text into structured elements
                    structured_elements = []
                    lines = elements_text.strip().split("\n")
                    
                    for line in lines:
                        # Look for pattern like [2]<div>Text />
                        if "[" in line and "<" in line and ">" in line:
                            try:
                                index = int(line.split("[")[1].split("]")[0])
                                tag = line.split("<")[1].split(">")[0]
                                text = line.split(">")[1].split("/>")[0].strip()
                                
                                element_info = {
                                    "index": index,
                                    "tag": tag,
                                    "text": text
                                }
                                
                                # Extract attributes if present
                                if " " in tag:
                                    base_tag = tag.split(" ")[0]
                                    attrs_text = tag[len(base_tag):].strip()
                                    element_info["tag"] = base_tag
                                    
                                    # Parse attributes like type='text'
                                    attrs = {}
                                    for attr in attrs_text.split(" "):
                                        if "=" in attr:
                                            key, value = attr.split("=", 1)
                                            attrs[key] = value.strip("'").strip('"')
                                    
                                    element_info["attributes"] = attrs
                                
                                structured_elements.append(element_info)
                            except Exception as e:
                                print(f"Error parsing element line: {line}, error: {e}")
                    
                    return {
                        "elements": structured_elements,
                        "raw_text": elements_text
                    }
            
            # If we couldn't parse it, return the original elements
            return elements
        except Exception as e:
            log_error("Error processing interactive elements:", e)
            return elements
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