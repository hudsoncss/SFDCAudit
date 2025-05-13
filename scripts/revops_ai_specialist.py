#!/usr/bin/env python3

import os
import json
import glob
import inspect
import importlib.util
import re
import argparse
import time
from typing import Dict, List, Any, Optional, Callable, get_type_hints, get_origin, get_args, Union
from enum import Enum
import openai
from dotenv import load_dotenv

def load_env_file():
    """Load environment variables from .env file, checking multiple locations."""
    # Get the current working directory and script directory
    cwd = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    
    # Potential locations for .env file
    env_locations = [
        cwd,                    # Current working directory
        script_dir,             # Script directory
        parent_dir,             # Parent directory of script
        os.path.join(cwd, 'scripts'),  # scripts folder in current directory
        os.path.join(parent_dir, 'scripts')  # scripts folder in parent directory
    ]
    
    # Try to load from each location
    for location in env_locations:
        env_path = os.path.join(location, '.env')
        if os.path.isfile(env_path):
            print(f"Loading .env file from: {env_path}")
            load_dotenv(env_path)
            return True
    
    # If we reach here, we couldn't find a .env file
    print("Warning: No .env file found in any of the expected locations.")
    print(f"Searched in: {', '.join(env_locations)}")
    
    # Try to load from any location (default behavior)
    load_dotenv()
    return False

def load_python_file(file_path: str):
    """Load a Python file as a module."""
    module_name = os.path.basename(file_path).replace('.py', '')
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def get_docstring_first_sentence(docstring: Optional[str]) -> str:
    """Extract the first sentence from a docstring."""
    if not docstring:
        return "No description available."
    
    # Clean up the docstring
    docstring = docstring.strip()
    
    # Try to find the first sentence
    match = re.search(r'^(.*?\.)\s', docstring)
    if match:
        return match.group(1)
    
    # If no period is found, return the first line or a portion of it
    first_line = docstring.split('\n')[0].strip()
    if len(first_line) > 100:
        return first_line[:97] + "..."
    return first_line

def python_type_to_json_schema_type(python_type: Any) -> Dict[str, Any]:
    """Convert Python type to JSON Schema type."""
    if python_type is None or python_type == inspect.Signature.empty:
        return {"type": "string"}
    
    if python_type == str:
        return {"type": "string"}
    elif python_type == int:
        return {"type": "integer"}
    elif python_type == float:
        return {"type": "number"}
    elif python_type == bool:
        return {"type": "boolean"}
    elif python_type == list or python_type == List:
        return {"type": "array", "items": {"type": "string"}}
    elif python_type == dict or python_type == Dict:
        return {"type": "object"}
    
    # Handle Optional types (Union[Type, None])
    origin = get_origin(python_type)
    if origin is not None and origin is Optional:
        args = get_args(python_type)
        if len(args) == 2 and args[1] is type(None):
            return python_type_to_json_schema_type(args[0])
    
    # Handle List[Type]
    if origin is list or origin is List:
        args = get_args(python_type)
        if args:
            item_type = python_type_to_json_schema_type(args[0])
            return {"type": "array", "items": item_type}
    
    # If it's an Enum, extract possible values
    if inspect.isclass(python_type) and issubclass(python_type, Enum):
        return {
            "type": "string", 
            "enum": [e.value for e in python_type]
        }
    
    # Default to string for complex types
    return {"type": "string"}

def extract_function_schema(func: Callable) -> Dict[str, Any]:
    """Extract JSON Schema for a function."""
    func_name = func.__name__
    docstring = func.__doc__
    signature = inspect.signature(func)
    type_hints = get_type_hints(func)
    
    description = get_docstring_first_sentence(docstring)
    
    # Build parameters
    properties = {}
    required = []
    
    for param_name, param in signature.parameters.items():
        # Skip 'self' parameter
        if param_name == 'self':
            continue
        
        param_type = type_hints.get(param_name, param.annotation)
        param_schema = python_type_to_json_schema_type(param_type)
        
        # Add description from docstring if available
        if docstring:
            param_desc_match = re.search(rf'{param_name}\s*:\s*([^\n]+)', docstring)
            if param_desc_match:
                param_schema["description"] = param_desc_match.group(1).strip()
        
        properties[param_name] = param_schema
        
        # Add to required list if parameter has no default value
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    
    return {
        "name": func_name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required
        }
    }

def find_and_extract_functions() -> List[Dict[str, Any]]:
    """Find all search_*.py files and extract function schemas."""
    functions = []
    
    # Get all search_*.py files in the scripts directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_files = glob.glob(os.path.join(script_dir, "search_*.py"))
    
    for file_path in search_files:
        module = load_python_file(file_path)
        if not module:
            continue
        
        # Find all callable functions in the module
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            # Skip private functions
            if name.startswith('_'):
                continue
            
            # Extract function schema
            function_schema = extract_function_schema(obj)
            functions.append(function_schema)
    
    return functions

def load_all_search_functions() -> Dict[str, Callable]:
    """Load all functions from search_*.py files."""
    function_dict = {}
    
    # Get all search_*.py files in the scripts directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    search_files = glob.glob(os.path.join(script_dir, "search_*.py"))
    
    for file_path in search_files:
        module = load_python_file(file_path)
        if not module:
            continue
        
        # Find all callable functions in the module
        for name, obj in inspect.getmembers(module, inspect.isfunction):
            # Skip private functions
            if name.startswith('_'):
                continue
            
            # Add function to dictionary
            function_dict[name] = obj
    
    return function_dict

def create_system_prompt() -> str:
    """Create the RevOps AI specialist system prompt."""
    return """You are a senior Revenue Operations (RevOps) engineer specializing in Salesforce audits. Your goal is to thoroughly analyze and identify gaps, inefficiencies, and opportunities for improvement in a Salesforce organization.

EXPERTISE:
- Salesforce configuration, customization, and administration
- Sales and marketing automation workflows
- CRM data quality, integrity, and governance 
- Security and permission models
- Reporting, analytics, and dashboards
- Integration patterns and API usage

METHODOLOGY:
1. Systematically examine each area of the Salesforce instance
2. Identify and document configuration gaps, inefficiencies, and risks
3. Ruthlessly flag data quality and process issues
4. Suggest concrete, actionable improvements with clear priorities
5. Identify blockers to optimal performance and escalate critical findings

COMMUNICATION STYLE:
- Methodical and structured in your analysis
- Ruthless in identifying gaps that impact business performance
- Solution-oriented, always recommending practical improvements
- Clear about blockers and urgent issues requiring immediate attention
- Technical yet able to explain implications to business stakeholders

TOOLS AT YOUR DISPOSAL:
You have access to several Python scripts for Salesforce metadata inspection:
- search_objects.py: Inspect standard and custom objects
- search_fields.py: Analyze field definitions, usage, and metadata
- search_apex.py: Examine Apex code and automations
- search_flows.py: Inspect Flow definitions and configurations
- search_reports.py: Analyze reports and dashboards
- search_packages.py: Review installed packages and dependencies
- search_fieldUsage.py: Check field usage patterns and quality
- search_influencesetting.py: Examine attribution and influence settings

Use these tools to gather detailed information about the Salesforce organization structure, then provide comprehensive analysis and recommendations for improvement.

When providing recommendations, consider:
- Business impact and value
- Implementation effort
- Risk level
- Best practices alignment
- Scalability and future-proofing

Be specific in your recommendations, suggesting concrete steps, configuration changes, or process improvements. Always prioritize findings based on business impact.
"""

def generate_revops_specialist_config():
    """Generate the RevOps AI specialist configuration as JSON."""
    # Create system prompt
    system_prompt = create_system_prompt()
    
    # Extract function definitions
    functions = find_and_extract_functions()
    
    # Build the final configuration
    config = {
        "system_prompt": system_prompt,
        "functions": functions
    }
    
    return config

def execute_tool_call(tool_call, available_functions):
    """Execute a tool call and return the result.
    
    Args:
        tool_call: The tool call object from OpenAI
        available_functions: Dictionary of available functions
        
    Returns:
        Result of the function call
    """
    function_name = tool_call.function.name
    
    try:
        function_args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        return f"Error: Invalid JSON in function arguments for '{function_name}'"
    
    print(f"  - Executing: {function_name}({json.dumps(function_args)})")
    
    # Check if function exists
    if function_name not in available_functions:
        return f"Error: Function '{function_name}' not found."
    
    # Get the function
    function = available_functions[function_name]
    
    try:
        # Call the function with the parsed arguments
        result = function(**function_args)
        
        # For extremely large datasets, apply stricter limits
        # Maximum allowed size for any response (bytes)
        MAX_RESPONSE_SIZE = 40000  # ~10K tokens
        
        # Handle various result types
        if isinstance(result, (dict, list)):
            # For structured data, convert to JSON string
            if isinstance(result, list) and len(result) > 30:
                # For large lists, truncate aggressively
                truncated_items = result[:30]  # Keep first 30 items
                truncated_result = {
                    "truncated_response": True,
                    "original_length": len(result),
                    "truncated_items": truncated_items,
                    "message": f"Response was truncated from {len(result)} items to {len(truncated_items)} items due to token limits."
                }
                return json.dumps(truncated_result, indent=2)
            elif isinstance(result, dict) and len(str(result)) > MAX_RESPONSE_SIZE:
                # For large dicts, just return the keys
                truncated_result = {
                    "truncated_response": True,
                    "original_size_bytes": len(str(result)),
                    "keys_available": list(result.keys()),
                    "message": "Response was truncated due to token limits. Here are the available keys."
                }
                return json.dumps(truncated_result, indent=2)
            
            # Regular JSON conversion for smaller results
            json_result = json.dumps(result, indent=2)
            if len(json_result) > MAX_RESPONSE_SIZE:
                print(f"  - Warning: Result is large ({len(json_result)} chars), truncating...")
                return json_result[:MAX_RESPONSE_SIZE-100] + "\n\n... [truncated due to size]"
            return json_result
        elif result is None:
            # Handle None values
            return "Function executed successfully but returned no data."
        else:
            # For other results, convert to string and truncate if needed
            str_result = str(result)
            if len(str_result) > MAX_RESPONSE_SIZE:
                print(f"  - Warning: Result is large ({len(str_result)} chars), truncating...")
                return str_result[:MAX_RESPONSE_SIZE-100] + "\n\n... [truncated due to size]"
            return str_result
    except Exception as e:
        # Return error message
        return f"Error executing function '{function_name}': {str(e)}"

def process_conversation_with_openai(client, messages, tools, max_turns=10):
    """Process a conversation with OpenAI, handling tool calls.
    
    Args:
        client: OpenAI client
        messages: List of message objects
        tools: List of tool definitions
        max_turns: Maximum conversation turns
        
    Returns:
        Final assistant response
    """
    # Load all available functions
    available_functions = load_all_search_functions()
    
    # Keep track of total message size for token management
    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    
    # Conversation loop
    turn_count = 0
    while turn_count < max_turns:
        turn_count += 1
        
        print(f"\nTurn {turn_count}: Sending request to OpenAI...")
        
        try:
            # Choose model based on message size
            model = "gpt-4o"
            # If we have a large conversation, use a model with larger context
            if total_chars > 100000:
                print("  - Using gpt-4-turbo model due to large context size")
                model = "gpt-4-turbo"
            
            # Clean messages of any tool_calls fields that might cause issues
            clean_messages = []
            for msg in messages:
                clean_msg = {"role": msg["role"], "content": msg.get("content", "")}
                if msg["role"] == "tool":
                    clean_msg["tool_call_id"] = msg["tool_call_id"]
                    clean_msg["name"] = msg["name"]
                clean_messages.append(clean_msg)
            
            # Make the OpenAI API call
            response = client.chat.completions.create(
                model=model,
                messages=clean_messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=4000
            )
            
            # Get the assistant's response
            assistant_message = response.choices[0].message
            
            # Add the assistant's message to the conversation history
            assistant_msg_for_history = {
                "role": "assistant",
                "content": assistant_message.content if assistant_message.content is not None else ""
            }
            messages.append(assistant_msg_for_history)
            
            # Update total character count
            total_chars += len(assistant_msg_for_history["content"])
            
            # Check if there are tool calls
            if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls:
                print(f"Assistant requested {len(assistant_message.tool_calls)} tool calls:")
                
                # Process tool calls
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    
                    print(f"  - Executing: {function_name}({function_args})")
                    
                    # Execute the tool call
                    result = execute_tool_call(tool_call, available_functions)
                    
                    # Ensure result is a string
                    if result is None:
                        result = "No result returned from function."
                    
                    # Add the function result to messages
                    tool_message = {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": result
                    }
                    messages.append(tool_message)
                    
                    # Update total character count
                    total_chars += len(result)
                
                # If we're getting close to token limits, prune older messages
                if total_chars > 300000:
                    print("  - Conversation getting large, pruning older function results...")
                    # Keep system prompt and most recent messages
                    system_prompt = messages[0]
                    user_prompt = messages[1]  # Original user query
                    recent_messages = messages[-10:]  # Keep the 10 most recent messages
                    
                    # Reset messages to system prompt and recent messages
                    messages = [system_prompt, user_prompt] + recent_messages[-8:]  # Keep system, user, and 8 recent messages
                    
                    # Recalculate total characters
                    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
                
                # Continue the conversation with the tool results
                continue
            else:
                # No tool calls, conversation is complete
                return assistant_message.content or "No response from assistant."
                
        except Exception as e:
            print(f"Error in conversation turn {turn_count}: {str(e)}")
            
            # If we hit token limits, try to recover by pruning the conversation
            if "context_length_exceeded" in str(e) or "maximum context length" in str(e):
                print("  - Token limit exceeded, pruning conversation and trying again...")
                
                # Keep system prompt and most recent messages
                if len(messages) > 3:
                    system_prompt = messages[0]
                    user_prompt = messages[1]
                    
                    # Keep just a few recent messages to reduce context length dramatically
                    recent_messages = []
                    if len(messages) > 2:
                        recent_messages = [messages[-1]]  # Just keep the very last message
                    
                    # Reset messages to system prompt and recent messages
                    messages = [system_prompt, user_prompt] + recent_messages
                    
                    # Recalculate total characters
                    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
                    
                    # Try again with the pruned conversation
                    continue
            
            # Return error message for other exceptions
            return f"Error: {str(e)}"
    
    # If we reach max turns, return the last message
    return "Analysis exceeded maximum number of turns. Here are the partial results:\n\n" + (messages[-1].get("content", "") or "No final content available.")

def send_to_openai(config: Dict[str, Any], user_query: str) -> str:
    """Send the configuration and user query to OpenAI and get a response.
    
    Args:
        config: The configuration with system prompt and functions
        user_query: The user's query
        
    Returns:
        The OpenAI response text
    """
    # Load environment variables from .env file
    load_env_file()
    
    # Get OpenAI API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    
    # If not found, check for OPEN_API_KEY (common typo)
    if not api_key:
        api_key = os.getenv("OPEN_API_KEY")
    
    # If still not found, print informative error
    if not api_key:
        raise ValueError("""
OpenAI API key not found in environment variables. 
Please set OPENAI_API_KEY in your .env file or environment.

Your .env file should include a line like:
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx

Make sure the .env file is in one of these locations:
- The current working directory
- The scripts directory
- The parent directory of the scripts directory
""")
    
    # Initialize the OpenAI client
    client = openai.OpenAI(api_key=api_key)
    
    try:
        # Prepare tools from functions
        tools = [{"type": "function", "function": func} for func in config["functions"]]
        
        # Set up initial messages
        messages = [
            {"role": "system", "content": config["system_prompt"]},
            {"role": "user", "content": user_query}
        ]
        
        # Track conversation state manually
        available_functions = load_all_search_functions()
        max_turns = 10
        turn_count = 0
        
        while turn_count < max_turns:
            turn_count += 1
            print(f"\nTurn {turn_count}: Sending request to OpenAI...")
            
            try:
                # Make the OpenAI API call
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=4000
                )
                
                # Get the assistant's response
                assistant_message = response.choices[0].message
                assistant_content = assistant_message.content if assistant_message.content is not None else ""
                
                # Add assistant message to history
                messages.append({"role": "assistant", "content": assistant_content})
                
                # Handle tool calls if present
                if assistant_message.tool_calls:
                    print(f"Assistant requested {len(assistant_message.tool_calls)} tool calls:")
                    
                    # We need to remove the last added assistant message and replace it
                    # with one that includes the tool_calls field
                    messages.pop()
                    
                    # Add the correct assistant message with tool_calls field
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            } for tc in assistant_message.tool_calls
                        ]
                    })
                    
                    # Execute each tool call and add the result to messages
                    for tool_call in assistant_message.tool_calls:
                        function_name = tool_call.function.name
                        
                        # Execute the function
                        result = execute_tool_call(tool_call, available_functions)
                        
                        # Add the result to messages
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": function_name,
                            "content": result
                        })
                    
                    # Continue the conversation loop
                    continue
                else:
                    # No tool calls, return the response
                    return assistant_content or "No response from assistant."
                
            except Exception as e:
                print(f"Error in conversation turn {turn_count}: {str(e)}")
                
                # Handle context length exceeded error
                if "context_length_exceeded" in str(e):
                    print("Context length exceeded, pruning conversation...")
                    # Keep system and user messages, discard the rest
                    if len(messages) > 2:
                        messages = messages[:2]
                    continue
                
                return f"Error: {str(e)}"
        
        # If we exit the loop, we've reached max turns
        return "Analysis exceeded maximum number of turns."
        
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        return f"Error: {str(e)}"

def main():
    """Main function to generate config and optionally run it through OpenAI."""
    parser = argparse.ArgumentParser(description="Generate RevOps AI specialist configuration")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--query", "-q", help="User query to send to OpenAI")
    parser.add_argument("--env-file", "-e", help="Path to .env file")
    parser.add_argument("--max-turns", "-m", type=int, default=10, help="Maximum conversation turns")
    args = parser.parse_args()
    
    # Load environment variables
    if args.env_file and os.path.isfile(args.env_file):
        print(f"Loading environment from specified file: {args.env_file}")
        load_dotenv(args.env_file)
    else:
        load_env_file()
    
    # Generate the configuration
    config = generate_revops_specialist_config()
    
    # Save to file if specified
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Configuration saved to {args.output}")
    
    # If no query, just print config
    if not args.query:
        print(json.dumps(config, indent=2))
        return
        
    # If a query was provided, send to OpenAI
    print(f"\nSending query to OpenAI: '{args.query}'")
    print("\n" + "-" * 80 + "\n")
    
    response = send_to_openai(config, args.query)
    
    print("\n" + "-" * 80 + "\n")
    print("AI ANALYSIS COMPLETE:\n")
    print(response)

if __name__ == "__main__":
    main() 