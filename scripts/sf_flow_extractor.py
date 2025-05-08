#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from typing import Dict, List, Optional, Any

import requests

def get_sfdx_auth() -> Dict[str, str]:
    """Get authentication details from SFDX CLI"""
    try:
        # Run SFDX command to get org info
        result = subprocess.run(
            ["sfdx", "force:org:display", "--json"],
            capture_output=True,
            text=True,
            check=True,
            shell=True
        )
        
        # Parse JSON output
        org_data = json.loads(result.stdout)
        
        if org_data.get("status") == 0:
            instance_url = org_data["result"].get("instanceUrl")
            access_token = org_data["result"].get("accessToken")
            
            if not instance_url or not access_token:
                raise ValueError("Missing instanceUrl or accessToken in SFDX response")
                
            return {
                "instance_url": instance_url,
                "access_token": access_token
            }
        else:
            raise ValueError(f"SFDX command failed: {org_data.get('message')}")
    
    except subprocess.CalledProcessError as e:
        print(f"Error executing SFDX command: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing SFDX output: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

def query_tooling_api(auth: Dict[str, str], query: str) -> List[Dict[str, Any]]:
    """Execute a SOQL query against the Tooling API with pagination handling"""
    headers = {
        "Authorization": f"Bearer {auth['access_token']}",
        "Content-Type": "application/json"
    }
    
    url = f"{auth['instance_url']}/services/data/v53.0/tooling/query"
    params = {"q": query}
    
    print(f"Making API request to: {url}")
    print(f"Query: {query}")
    
    all_records = []
    
    try:
        # Initial request
        response = requests.get(url, headers=headers, params=params)
        
        # Print response details for debugging
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error response: {response.text}")
            
        response.raise_for_status()
        
        result = response.json()
        all_records.extend(result.get("records", []))
        
        # Handle pagination if needed
        next_records_url = result.get("nextRecordsUrl")
        while next_records_url:
            next_url = f"{auth['instance_url']}{next_records_url}"
            response = requests.get(next_url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            all_records.extend(result.get("records", []))
            next_records_url = result.get("nextRecordsUrl")
        
        return all_records
    
    except requests.RequestException as e:
        print(f"API request failed: {e}")
        print(f"Response details (if available): {getattr(e.response, 'text', 'No response text')}")
        sys.exit(1)

def get_flow_definitions_for_opportunity(auth: Dict[str, str]) -> List[str]:
    """Get all FlowDefinition IDs for flows on the Opportunity object"""
    # Use only name-based filtering without ProcessType field
    query = """
    SELECT Id, DeveloperName 
    FROM FlowDefinition 
    WHERE DeveloperName LIKE '%Opportunity%' 
    OR DeveloperName LIKE '%Opp%'
    """
    
    results = query_tooling_api(auth, query)
    
    # Extract just the IDs from the results
    flow_def_ids = [record["Id"] for record in results]
    
    print(f"Found {len(flow_def_ids)} flow definitions for Opportunity")
    return flow_def_ids

def get_active_flow_versions(auth: Dict[str, str], flow_def_ids: List[str]) -> List[Dict[str, Any]]:
    """Get all active FlowVersion records for the given FlowDefinition IDs"""
    if not flow_def_ids:
        print("No flow definitions found")
        return []
    
    # Format list of IDs for the IN clause
    formatted_ids = "'" + "','".join(flow_def_ids) + "'"
    
    # Use minimal fields that are known to work
    query = f"""
        SELECT Id, Status 
        FROM Flow 
        WHERE DefinitionId IN ({formatted_ids}) 
        AND Status = 'Active'
    """
    
    results = query_tooling_api(auth, query)
    print(f"Found {len(results)} active flow versions")
    return results

def get_flow_metadata(auth: Dict[str, str], flow_id: str) -> Optional[Dict[str, Any]]:
    """Get the metadata for a specific flow"""
    headers = {
        "Authorization": f"Bearer {auth['access_token']}",
        "Content-Type": "application/json"
    }
    
    # Use the tooling API to retrieve the flow definition document
    url = f"{auth['instance_url']}/services/data/v53.0/tooling/sobjects/Flow/{flow_id}"
    
    try:
        print(f"Retrieving metadata for flow: {flow_id}")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error retrieving flow metadata: {e}")
        return None

def save_flow_metadata(flow_metadata: Dict[str, Any], flows_dir: str) -> None:
    """Save the flow metadata to an XML file in the flows directory"""
    if "Metadata" not in flow_metadata:
        print(f"No metadata found for flow: {flow_metadata.get('Id')}")
        return
    
    # Extract the flow metadata
    metadata = flow_metadata.get("Metadata")
    
    # Create a meaningful filename
    flow_id = flow_metadata.get("Id")
    flow_name = metadata.get("fullName", flow_id)
    
    # Save the metadata to a file
    filename = os.path.join(flows_dir, f"{flow_name}.json")
    with open(filename, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Saved metadata for flow {flow_name} to {filename}")

def main():
    """Main execution function"""
    print("Getting SFDX authentication...")
    auth = get_sfdx_auth()
    
    print("Querying flow definitions for Opportunity...")
    flow_def_ids = get_flow_definitions_for_opportunity(auth)
    
    print("Fetching active flow versions...")
    flow_versions = get_active_flow_versions(auth, flow_def_ids)
    
    # Save the initial results
    output_file = "opportunity_flows.json"
    with open(output_file, 'w') as f:
        json.dump(flow_versions, f, indent=2)
    print(f"Basic flow information saved to {output_file}")
    
    # Create a directory to store flow metadata
    flows_dir = "flows"
    if not os.path.exists(flows_dir):
        os.makedirs(flows_dir)
        print(f"Created directory: {flows_dir}")
    
    # For each flow, get its metadata and save it
    print(f"Retrieving detailed metadata for {len(flow_versions)} flows...")
    for flow in flow_versions:
        flow_id = flow.get("Id")
        # Get the detailed metadata for this flow
        detailed_metadata = get_flow_metadata(auth, flow_id)
        if detailed_metadata:
            # Save the flow metadata to a file
            save_flow_metadata(detailed_metadata, flows_dir)
    
    print(f"All flow metadata has been saved to the '{flows_dir}' directory")

if __name__ == "__main__":
    main() 