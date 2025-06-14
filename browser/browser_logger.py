import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(exist_ok=True)

# Configure the browser agent logger
log_file = logs_dir / f"browser_agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

# Create logger
browser_logger = logging.getLogger("browser_agent")
browser_logger.setLevel(logging.DEBUG)
browser_logger.addHandler(file_handler)

# Also add console handler for visibility
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('[BROWSER_AGENT] %(message)s'))
browser_logger.addHandler(console_handler)

def log_separator(title: str = None):
    """Log a separator line with optional title"""
    if title:
        separator = f"\n{'=' * 20} {title} {'=' * 20}\n"
    else:
        separator = f"\n{'=' * 50}\n"
    browser_logger.info(separator)

def log_navigation_start(query: str):
    """Log the start of a navigation stage"""
    log_separator("NAVIGATION STAGE START")
    browser_logger.info(f"User Query: {query}")

def log_navigation_plan(plan: Dict):
    """Log the navigation plan"""
    log_separator("NAVIGATION PLAN")
    try:
        browser_logger.info(f"Plan:\n{json.dumps(plan, indent=2)}")
    except:
        browser_logger.info(f"Plan (not JSON serializable): {str(plan)}")

def log_navigation_result(result: Dict):
    """Log the navigation result"""
    log_separator("NAVIGATION RESULT")
    try:
        browser_logger.info(f"Result:\n{json.dumps(result, indent=2)}")
    except:
        browser_logger.info(f"Result (not JSON serializable): {str(result)}")

def log_interactive_elements(elements: Dict, stage: str = ""):
    """Log the interactive elements"""
    log_separator(f"INTERACTIVE ELEMENTS {stage}")
    
    # Log raw elements structure
    browser_logger.info(f"Raw elements structure: {type(elements)}")
    
    # Try to extract and log content
    if isinstance(elements, dict) and "content" in elements:
        content = elements["content"]
        browser_logger.info(f"Elements count: {len(content)}")
        
        # Log each element with its index
        for i, element in enumerate(content):
            try:
                browser_logger.info(f"[{i}] {element.get('tag', 'unknown')} - {element.get('text', '')} - {element.get('attributes', {})}")
            except:
                browser_logger.info(f"[{i}] Error logging element: {str(element)}")
    else:
        # Try to log the elements directly
        try:
            browser_logger.info(f"Elements:\n{json.dumps(elements, indent=2)}")
        except:
            browser_logger.info(f"Elements (not JSON serializable): {str(elements)}")

def log_action_start(iteration: int, max_iterations: int):
    """Log the start of an action stage"""
    log_separator(f"ACTION STAGE START - ITERATION {iteration}/{max_iterations}")

def log_action_plan(plan: Dict):
    """Log the action plan"""
    log_separator("ACTION PLAN")
    try:
        browser_logger.info(f"Plan:\n{json.dumps(plan, indent=2)}")
    except:
        browser_logger.info(f"Plan (not JSON serializable): {str(plan)}")

def log_action_result(result: Dict):
    """Log the action result"""
    log_separator("ACTION RESULT")
    try:
        browser_logger.info(f"Result:\n{json.dumps(result, indent=2)}")
    except:
        browser_logger.info(f"Result (not JSON serializable): {str(result)}")

def log_tool_execution(tool_name: str, params: Dict, result: Any):
    """Log a tool execution"""
    log_separator(f"TOOL EXECUTION: {tool_name}")
    
    # Log parameters
    try:
        browser_logger.info(f"Parameters:\n{json.dumps(params, indent=2)}")
    except:
        browser_logger.info(f"Parameters (not JSON serializable): {str(params)}")
    
    # Log result
    try:
        browser_logger.info(f"Result:\n{json.dumps(result, indent=2)}")
    except:
        browser_logger.info(f"Result (not JSON serializable): {str(result)}")

def log_error(message: str, error: Exception = None):
    """Log an error"""
    if error:
        browser_logger.error(f"{message} {str(error)}")
    else:
        browser_logger.error(message)

def log_workflow_complete(success: bool, summary: str):
    """Log workflow completion"""
    status = "SUCCESS" if success else "FAILURE"
    log_separator(f"WORKFLOW COMPLETE: {status}")
    browser_logger.info(f"Summary: {summary}")
