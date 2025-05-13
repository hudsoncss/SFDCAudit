#!/usr/bin/env python3

import subprocess
import json
import sys
import requests
import os
from typing import Dict, Any, Optional, Tuple

def run_sfdx(cmd: str) -> Optional[Dict[str, Any]]:
    """Execute an SFDX command and return the parsed JSON response.
    
    Args:
        cmd: Command to execute
        
    Returns:
        Parsed JSON response as dictionary or None if error
    """
    try:
        print(f"Executing SFDX command: {cmd}")
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='replace',  # Replace invalid characters instead of failing
            shell=True,
            check=False  # Don't raise exception on non-zero return code
        )
        
        if result.returncode != 0:
            print(f"Error executing SFDX command: {result.stderr}")
            return None
        
        try:    
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from SFDX command: {e}")
            print(f"Command: {cmd}")
            print(f"Output (first 1000 chars): {result.stdout[:1000]}")
            return None
    except Exception as e:
        print(f"Error executing command: {cmd}")
        print(f"Exception: {str(e)}")
        return None

def get_org_auth_details() -> Tuple[Optional[Tuple[str, str]], Optional[str]]:
    """Get org authentication details (instance URL and access token).
    
    Returns:
        Tuple of (auth_tuple, error_message) where auth_tuple is (instance_url, access_token) or None
    """
    print("Getting org authentication details...")
    
    # Try both the old and new SFDX commands
    commands = [
        "sfdx force:org:display --json",
        "sf org display --json"
    ]
    
    for cmd in commands:
        print(f"Trying command: {cmd}")
        auth_result = run_sfdx(cmd)
        
        if auth_result and 'result' in auth_result:
            # Extract instance URL and access token
            instance_url = auth_result['result'].get('instanceUrl')
            access_token = auth_result['result'].get('accessToken')
            
            if instance_url and access_token:
                print(f"Successfully retrieved authentication for {instance_url}")
                return (instance_url, access_token), None
    
    # If we get here, none of the commands worked
    return None, "Could not retrieve Salesforce authentication. Make sure you're authenticated and a default org is set."

def save_report(results: Dict[str, Any], filename: str = "campaign_influence_settings.json") -> None:
    """Save results to JSON file and print status."""
    try:
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {filename}")
    except Exception as e:
        print(f"Error saving results: {str(e)}")

def check_campaign_influence(instance_url: str, access_token: str) -> Dict[str, Any]:
    """Check Campaign Influence by directly querying CampaignInfluenceModel.
    
    Args:
        instance_url: Salesforce instance URL
        access_token: Salesforce access token
        
    Returns:
        Dictionary indicating if Campaign Influence is enabled
    """
    print("\nChecking Campaign Influence...")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Query for CampaignInfluenceModel to check if it exists
        query_url = f"{instance_url}/services/data/v57.0/query?q=SELECT+Id+FROM+CampaignInfluenceModel+LIMIT+1"
        print(f"Querying CampaignInfluenceModel: {query_url}")
        
        model_response = requests.get(query_url, headers=headers)
        
        if model_response.status_code == 200:
            # CampaignInfluenceModel exists
            model_result = model_response.json()
            has_model_records = model_result.get('totalSize', 0) > 0
            
            return {
                "campaign_influence_enabled": True
            }
        else:
            print(f"Error or CampaignInfluenceModel object does not exist: {model_response.status_code}")
            print(f"Response: {model_response.text[:200]}")
            
            # If we get here, CampaignInfluenceModel doesn't exist or is not accessible
            return {
                "campaign_influence_enabled": False
            }
        
    except Exception as e:
        print(f"Error checking Campaign Influence: {str(e)}")
        return {
            "campaign_influence_enabled": False
        }

def main():
    """Main function to check Campaign Influence settings."""
    print("\n===== CHECKING CAMPAIGN INFLUENCE SETTINGS =====\n")
    
    # Try to get org auth details
    auth_details, error_message = get_org_auth_details()
    
    if not auth_details:
        # Create result with specific error message
        results = {
            "campaign_influence_enabled": False
        }
        print("\nCould not authenticate with Salesforce.")
        save_report(results)
        return results
    
    # If we get here, we have authenticated successfully
    instance_url, access_token = auth_details
    
    # Check Campaign Influence directly
    results = check_campaign_influence(instance_url, access_token)
    
    # Save results to JSON file
    save_report(results)
    return results

if __name__ == '__main__':
    main() 
