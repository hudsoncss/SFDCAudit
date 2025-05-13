#!/usr/bin/env python3

import os
import json
import argparse
import openai
from dotenv import load_dotenv
from notion_sender import create_notion_page, NotionSender

def load_text_from_file(file_path):
    """Load text content from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {str(e)}")
        return None

def get_openai_response(input_text, example_schema=None):
    """
    Send a request to OpenAI to format the input text for Notion.
    
    Args:
        input_text: The text to format
        example_schema: Optional example schema to guide the formatting
        
    Returns:
        Formatted response from OpenAI
    """
    # Load environment variables from .env file
    load_dotenv()
    
    # Get OpenAI API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables. Please set OPENAI_API_KEY in your .env file.")
    
    # Initialize the OpenAI client
    client = openai.OpenAI(api_key=api_key)
    
    # Create the prompt
    system_prompt = """
    You are a text formatting assistant specialized in preparing content for Notion pages. 
    Your task is to take the input text and format it into a structured JSON response that follows Notion's API format for blocks.
    
    Follow these guidelines:
    1. Preserve the original meaning and content
    2. Use appropriate Notion block types (paragraph, heading_1, heading_2, heading_3, bulleted_list_item, numbered_list_item, quote, callout, etc.)
    3. Maintain hierarchy and structure from the original text
    4. Add proper formatting like bold, italic, and code where appropriate
    5. Return ONLY valid JSON that matches the expected format - no explanations, just the JSON
    6. IMPORTANT: Every block must have the required properties according to Notion's API
       - All heading blocks must have "rich_text" array with at least one text object
       - All paragraph blocks must have "rich_text" array with at least one text object
       - All list items must have "rich_text" array with at least one text object
    
    Your output should be a JSON array of blocks, each with the structure matching Notion's API requirements.
    """
    
    if example_schema:
        system_prompt += f"\n\nHere's an example schema for reference:\n{example_schema}"
    
    # Example schema to help OpenAI understand the format
    example_schema = """
    [
      {
        "object": "block",
        "type": "heading_1",
        "heading_1": {
          "rich_text": [
            {
              "type": "text",
              "text": {
                "content": "This is a heading 1"
              }
            }
          ]
        }
      },
      {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
          "rich_text": [
            {
              "type": "text",
              "text": {
                "content": "This is a normal paragraph with some "
              }
            },
            {
              "type": "text",
              "text": {
                "content": "bold"
              },
              "annotations": {
                "bold": true
              }
            },
            {
              "type": "text",
              "text": {
                "content": " and some "
              }
            },
            {
              "type": "text",
              "text": {
                "content": "italic"
              },
              "annotations": {
                "italic": true
              }
            },
            {
              "type": "text",
              "text": {
                "content": " text."
              }
            }
          ]
        }
      },
      {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
          "rich_text": [
            {
              "type": "text",
              "text": {
                "content": "This is a bullet point"
              }
            }
          ]
        }
      }
    ]
    """
    
    try:
        # Make the OpenAI API call
        response = client.chat.completions.create(
            model="gpt-4",  # or another appropriate model
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Format the following text for Notion:\n\n{input_text}\n\nExample format:\n{example_schema}"}
            ],
            temperature=0.2,
            max_tokens=4000
        )
        
        # Extract and parse the response
        content = response.choices[0].message.content
        
        # Try to extract just the JSON part if the model includes explanations
        try:
            # Look for JSON array indicators
            if content.strip().startswith('[') and content.strip().endswith(']'):
                blocks = json.loads(content)
            else:
                # Try to find JSON array in the response
                start_idx = content.find('[')
                end_idx = content.rfind(']') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = content[start_idx:end_idx]
                    blocks = json.loads(json_str)
                else:
                    # If we can't find clear JSON indicators, try to parse the whole thing
                    blocks = json.loads(content)
            
            # Validate and fix blocks
            return validate_and_fix_blocks(blocks)
            
        except json.JSONDecodeError:
            print("Error: Could not parse OpenAI response as valid JSON.")
            print("Raw response:", content)
            return None
        
    except Exception as e:
        print(f"Error calling OpenAI API: {str(e)}")
        return None

def validate_and_fix_blocks(blocks):
    """
    Validate and fix blocks to ensure they follow Notion's API requirements.
    
    Args:
        blocks: List of block objects
        
    Returns:
        Fixed blocks list
    """
    if not isinstance(blocks, list):
        print("Error: Blocks should be a list")
        return []
    
    fixed_blocks = []
    
    for block in blocks:
        if not isinstance(block, dict):
            continue
            
        # Ensure object property is set
        if "object" not in block:
            block["object"] = "block"
            
        # Skip if no type
        if "type" not in block:
            continue
            
        block_type = block["type"]
        
        # Check if the type property exists in the block
        if block_type not in block:
            # Create an empty object for the type
            block[block_type] = {}
        
        # Handle different block types
        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", 
                         "bulleted_list_item", "numbered_list_item", "quote"]:
            # Ensure rich_text exists and is valid
            type_obj = block[block_type]
            
            if not isinstance(type_obj, dict):
                type_obj = {}
                
            if "rich_text" not in type_obj or not isinstance(type_obj["rich_text"], list) or len(type_obj["rich_text"]) == 0:
                # Create a valid rich_text array with content from the block type
                type_obj["rich_text"] = [
                    {
                        "type": "text",
                        "text": {
                            "content": block.get("content", "") or f"Empty {block_type}"
                        }
                    }
                ]
            
            # Ensure each rich_text item has required properties
            for i, text_item in enumerate(type_obj["rich_text"]):
                if not isinstance(text_item, dict):
                    type_obj["rich_text"][i] = {
                        "type": "text",
                        "text": {"content": str(text_item)}
                    }
                    continue
                    
                if "type" not in text_item:
                    text_item["type"] = "text"
                    
                if "text" not in text_item or not isinstance(text_item["text"], dict):
                    text_item["text"] = {"content": ""}
                    
                if "content" not in text_item["text"]:
                    text_item["text"]["content"] = ""
            
            # Update the block
            block[block_type] = type_obj
        
        # Add the fixed block
        fixed_blocks.append(block)
    
    # If no valid blocks, create a simple paragraph
    if not fixed_blocks:
        fixed_blocks = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {
                                "content": "No valid content found."
                            }
                        }
                    ]
                }
            }
        ]
    
    return fixed_blocks

def create_notion_page_with_formatted_content(database_id, title, content_blocks, notion_token=None):
    """
    Create a new page in Notion with the formatted content.
    
    Args:
        database_id: The ID of the Notion database
        title: Title for the new page
        content_blocks: Formatted content blocks
        notion_token: Optional Notion API token
        
    Returns:
        Response from Notion API
    """
    # Create properties with the title
    properties = {
        "Name": {  # Assuming "Name" is the title property in your database
            "title": [
                {
                    "text": {
                        "content": title
                    }
                }
            ]
        }
    }
    
    # Create the page with content
    result = create_notion_page(
        database_id=database_id,
        properties=properties,
        content=content_blocks,
        notion_token=notion_token
    )
    
    return result

def main():
    """Main function to process arguments and execute the workflow."""
    parser = argparse.ArgumentParser(description="Format text and create a Notion page")
    parser.add_argument("--input-file", required=True, help="Path to the input text file")
    parser.add_argument("--database-id", required=True, help="Notion database ID")
    parser.add_argument("--title", required=True, help="Title for the Notion page")
    parser.add_argument("--output-file", help="Path to save the formatted JSON (optional)")
    args = parser.parse_args()
    
    # Load the input text
    input_text = load_text_from_file(args.input_file)
    if not input_text:
        print(f"Could not load text from {args.input_file}")
        return
    
    print(f"Loaded {len(input_text)} characters from {args.input_file}")
    
    # Get formatted content from OpenAI
    print("Sending text to OpenAI for formatting...")
    formatted_blocks = get_openai_response(input_text)
    
    if not formatted_blocks:
        print("Failed to format text with OpenAI")
        return
    
    print(f"Successfully formatted text into {len(formatted_blocks)} Notion blocks")
    
    # Optionally save the formatted JSON
    if args.output_file:
        try:
            with open(args.output_file, 'w', encoding='utf-8') as file:
                json.dump(formatted_blocks, file, indent=2)
            print(f"Saved formatted JSON to {args.output_file}")
        except Exception as e:
            print(f"Error saving formatted JSON: {str(e)}")
    
    # Create the Notion page
    print(f"Creating Notion page in database {args.database_id}...")
    result = create_notion_page_with_formatted_content(
        database_id=args.database_id,
        title=args.title,
        content_blocks=formatted_blocks
    )
    
    if result:
        print(f"Successfully created Notion page: {result.get('url', result.get('id'))}")
    else:
        print("Failed to create Notion page")

if __name__ == "__main__":
    main() 