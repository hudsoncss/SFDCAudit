#!/usr/bin/env python3

import json
import os
import sys
from openai import OpenAI
from typing import Dict, Any, Optional, Callable
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def load_json_file(filename: str) -> Optional[Dict[str, Any]]:
    """Load data from a JSON file.
    
    Args:
        filename: Path to the JSON file
        
    Returns:
        Dictionary containing the JSON data or None if file not found/invalid
    """
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: '{filename}' is not a valid JSON file.")
        return None
    except Exception as e:
        print(f"Error loading file: {str(e)}")
        return None

def analyze_with_openai(
    data: Dict[str, Any],
    api_key: str,
    prompt_generator: Callable[[Dict[str, Any]], str],
    system_prompt: str,
    model: str = "gpt-4",
    temperature: float = 0.7,
    max_tokens: int = 2000
) -> Optional[str]:
    """Send data to OpenAI for analysis.
    
    Args:
        data: Dictionary containing the data to analyze
        api_key: OpenAI API key
        prompt_generator: Function that generates the prompt from the data
        system_prompt: System prompt for the AI
        model: OpenAI model to use
        temperature: Temperature setting for the model
        max_tokens: Maximum tokens for the response
        
    Returns:
        Analysis response from OpenAI or None if analysis failed
    """
    try:
        # Initialize OpenAI client
        client = OpenAI(api_key=api_key)
        
        # Generate the prompt
        prompt = prompt_generator(data)
        
        # Call OpenAI API
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Extract and return the analysis
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"Error analyzing with OpenAI: {str(e)}")
        return None

def save_analysis(analysis: str, output_filename: str) -> None:
    """Save the OpenAI analysis to a file.
    
    Args:
        analysis: The analysis text from OpenAI
        output_filename: Name of the output file
    """
    try:
        with open(output_filename, 'w') as f:
            f.write(analysis)
        print(f"\nAnalysis saved to: {output_filename}")
    except Exception as e:
        print(f"Error saving analysis: {str(e)}")

def main():
    """Main function to run the OpenAI analysis."""
    # Check if API key is provided
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment variables or .env file.")
        print("Please either:")
        print("1. Set the environment variable:")
        print("   export OPENAI_API_KEY='your-api-key'")
        print("2. Or create a .env file in the same directory with:")
        print("   OPENAI_API_KEY=your-api-key")
        sys.exit(1)
    
    # Get the input file from command line
    if len(sys.argv) < 2:
        print("Error: No input file specified.")
        print("Usage: python openai_sender.py <input_file> [output_file]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Load input data
    print(f"Loading data from: {input_file}")
    data = load_json_file(input_file)
    if not data:
        sys.exit(1)
    
    # Import the prompt generator and system prompt
    try:
        from attribution_prompt import get_attribution_prompt, get_system_prompt
        prompt_generator = get_attribution_prompt
        system_prompt = get_system_prompt()
    except ImportError:
        print("Error: Could not import prompt generator.")
        print("Please ensure attribution_prompt.py is in the same directory.")
        sys.exit(1)
    
    # Analyze with OpenAI
    print("\nAnalyzing data with OpenAI...")
    analysis = analyze_with_openai(
        data=data,
        api_key=api_key,
        prompt_generator=prompt_generator,
        system_prompt=system_prompt
    )
    if not analysis:
        sys.exit(1)
    
    # Determine output filename
    if not output_file:
        # Use company name from data if available, otherwise use input filename
        company_name = data.get('company_name', os.path.splitext(os.path.basename(input_file))[0])
        output_file = f"{company_name}_analysis.txt"
    
    # Save the analysis
    save_analysis(analysis, output_file)

if __name__ == '__main__':
    main() 