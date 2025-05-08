#!/usr/bin/env python3

import requests
import json
import logging
import sys
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Webhook configuration
WEBHOOK_URL = "https://3a3ae7d8-9ac1-49b7-9b0d-bd321e1c56c3.trayapp.io"

def send_to_webhook(data: Dict[str, Any], source: Optional[str] = None) -> bool:
    """Send JSON data to the configured webhook.
    
    Args:
        data: Dictionary containing the data to send
        source: Optional identifier for the source of the data (e.g., 'attribution_audit')
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Add source information if provided
        if source:
            data['webhook_source'] = source
            
        # Send POST request to webhook
        response = requests.post(
            WEBHOOK_URL,
            json=data,
            headers={'Content-Type': 'application/json'}
        )
        
        # Check response
        if response.status_code == 200:
            logger.info(f"Successfully sent data to webhook from {source or 'unknown source'}")
            return True
        else:
            logger.error(f"Failed to send data to webhook. Status code: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending data to webhook: {str(e)}")
        return False

def send_json_file(file_path: str, source: Optional[str] = None) -> bool:
    """Send contents of a JSON file to the webhook.
    
    Args:
        file_path: Path to the JSON file
        source: Optional identifier for the source of the data
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return send_to_webhook(data, source)
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        return False
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in file: {file_path}")
        return False
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # If file path provided as argument, send that file
        file_path = sys.argv[1]
        source = sys.argv[2] if len(sys.argv) > 2 else None
        send_json_file(file_path, source)
    else:
        # Example usage with test data
        test_data = {
            'test': True,
            'message': 'Testing webhook sender'
        }
        send_to_webhook(test_data, 'test') 