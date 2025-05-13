#!/usr/bin/env python3

import os
import json
from typing import Dict, Any, Optional, Union
from dotenv import load_dotenv
from notion_client import Client

class NotionSender:
    """
    A class to handle sending data to Notion via the API.
    Uses the notion-sdk-py library for API communication.
    """
    
    def __init__(self, notion_token: Optional[str] = None):
        """
        Initialize the NotionSender with authentication.
        
        Args:
            notion_token: Optional Notion API token. If not provided, will try to load from environment.
        """
        # Load environment variables from .env file
        load_dotenv()
        
        # Use provided token or get from environment
        # Try multiple possible environment variable names
        self.token = notion_token or os.getenv("NOTION_TOKEN") or os.getenv("NOTION_API_KEY") or os.getenv("NOTION_API_TOKEN")
        
        if not self.token:
            raise ValueError("Notion API token not provided and not found in environment variables. Please set NOTION_TOKEN in your .env file.")
        
        # Initialize the Notion client
        self.client = Client(auth=self.token)
    
    def create_page(self, 
                   database_id: str, 
                   properties: Dict[str, Any],
                   content: Optional[list] = None,
                   icon: Optional[Dict[str, str]] = None,
                   cover: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Create a new page in a specified Notion database.
        
        Args:
            database_id: The ID of the Notion database where the page will be created
            properties: Dict of page properties following Notion API format
            content: Optional list of block objects to add as page content
            icon: Optional icon object (emoji or external URL)
            cover: Optional cover object (external URL)
            
        Returns:
            Dict containing the API response with the created page data
        """
        # Prepare the page data
        page_data = {
            "parent": {"database_id": database_id},
            "properties": properties
        }
        
        # Add optional parameters if provided
        if icon:
            page_data["icon"] = icon
        
        if cover:
            page_data["cover"] = cover
            
        # Create the page first
        response = self.client.pages.create(**page_data)
        
        # If content blocks are provided, add them to the page
        if content and len(content) > 0:
            page_id = response["id"]
            self.client.blocks.children.append(
                block_id=page_id,
                children=content
            )
            
            # Refresh the page data to include the new content
            response = self.client.pages.retrieve(page_id=page_id)
            
        return response
    
    def update_page(self, 
                   page_id: str, 
                   properties: Optional[Dict[str, Any]] = None,
                   archived: Optional[bool] = None,
                   icon: Optional[Dict[str, str]] = None,
                   cover: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Update an existing page in Notion.
        
        Args:
            page_id: The ID of the page to update
            properties: Optional dict of properties to update
            archived: Optional boolean to archive or unarchive the page
            icon: Optional icon object (emoji or external URL)
            cover: Optional cover object (external URL)
            
        Returns:
            Dict containing the API response with the updated page data
        """
        # Prepare the update data
        update_data = {}
        
        if properties:
            update_data["properties"] = properties
            
        if archived is not None:
            update_data["archived"] = archived
            
        if icon:
            update_data["icon"] = icon
            
        if cover:
            update_data["cover"] = cover
            
        # Update the page
        return self.client.pages.update(page_id=page_id, **update_data)
    
    def add_content_to_page(self, page_id: str, content: list) -> Dict[str, Any]:
        """
        Add content blocks to an existing page.
        
        Args:
            page_id: The ID of the page to add content to
            content: List of block objects to add
            
        Returns:
            Dict containing the API response
        """
        return self.client.blocks.children.append(
            block_id=page_id,
            children=content
        )


def create_notion_page(database_id: str, 
                      properties: Dict[str, Any],
                      content: Optional[list] = None,
                      icon: Optional[Dict[str, str]] = None,
                      cover: Optional[Dict[str, str]] = None,
                      notion_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Convenience function to create a new page in a Notion database.
    
    Args:
        database_id: The ID of the Notion database where the page will be created
        properties: Dict of page properties following Notion API format
        content: Optional list of block objects to add as page content
        icon: Optional icon object (emoji or external URL)
        cover: Optional cover object (external URL)
        notion_token: Optional Notion API token. If not provided, will try to load from environment.
        
    Returns:
        Dict containing the API response with the created page data
    """
    sender = NotionSender(notion_token)
    return sender.create_page(
        database_id=database_id,
        properties=properties,
        content=content,
        icon=icon,
        cover=cover
    )


if __name__ == "__main__":
    # Example usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Create a new page in a Notion database")
    parser.add_argument("--database-id", required=True, help="Notion database ID")
    parser.add_argument("--properties", required=True, help="JSON string of page properties")
    parser.add_argument("--content", help="JSON string of page content blocks")
    parser.add_argument("--token", help="Notion API token (optional, can use NOTION_API_TOKEN env var)")
    
    args = parser.parse_args()
    
    # Parse JSON strings
    properties = json.loads(args.properties)
    content = json.loads(args.content) if args.content else None
    
    # Create the page
    result = create_notion_page(
        database_id=args.database_id,
        properties=properties,
        content=content,
        notion_token=args.token
    )
    
    # Print the result
    print(json.dumps(result, indent=2)) 