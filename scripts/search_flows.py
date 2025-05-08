#!/usr/bin/env python3

import subprocess
import json
import argparse
import sys
import requests
import difflib

# The minimum similarity score (0-1) required for a fuzzy match
DEFAULT_SIMILARITY_THRESHOLD = 0.6

def run_sfdx_command(command, capture_json=True):
    """Run an SFDX command and return the result"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=False,  # Don't raise exception on non-zero return code
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'  # Replace invalid characters instead of failing
        )
        
        if result.returncode != 0:
            print(f"Error executing command: {command}")
            print(f"Error: {result.stderr}")
            return None
        
        if capture_json:
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON from command: {command}")
                print(f"Error details: {str(e)}")
                print(f"Output (first 1000 chars): {result.stdout[:1000]}")
                return None
        else:
            return result.stdout
    except Exception as e:
        print(f"Error executing command: {command}")
        print(f"Exception: {str(e)}")
        return None

def check_sfdx_installed():
    """Check if SFDX CLI is installed and authorized"""
    try:
        # Check if SFDX is installed
        subprocess.run(
            "sfdx --version",
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Check if there's an authorized org
        result = run_sfdx_command("sfdx force:org:display --json")
        if not result or 'result' not in result:
            print("No authorized Salesforce org found.")
            print("Please authorize an org using: sfdx force:auth:web:login")
            sys.exit(1)
            
        return True
    except subprocess.CalledProcessError:
        print("SFDX CLI not found or not properly installed.")
        print("Please install SFDX CLI from: https://developer.salesforce.com/tools/sfdxcli")
        sys.exit(1)
    except Exception as e:
        print(f"Error checking SFDX installation: {e}")
        sys.exit(1)

def get_tooling_api_connection():
    """Get connection information for the Tooling API"""
    try:
        # Get org authentication details
        auth_result = run_sfdx_command("sfdx force:org:display --json")
        if not auth_result or 'result' not in auth_result:
            print("Failed to get org authentication details")
            return None
        
        # Extract instance URL and access token
        instance_url = auth_result["result"].get("instanceUrl")
        access_token = auth_result["result"].get("accessToken")
        
        if not instance_url or not access_token:
            print("Missing instanceUrl or accessToken in SFDX response")
            return None
            
        return {
            "instance_url": instance_url,
            "access_token": access_token
        }
    except Exception as e:
        print(f"Error getting Tooling API connection: {str(e)}")
        return None

def fuzzy_match(search_term, text, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Check if the search term fuzzy matches the text"""
    # Simple case: direct substring match
    if search_term.lower() in text.lower():
        return True
    
    # Advanced case: fuzzy matching using difflib
    similarity = difflib.SequenceMatcher(None, search_term.lower(), text.lower()).ratio()
    return similarity >= threshold

def search_flows_with_tooling_api(search_term, threshold=DEFAULT_SIMILARITY_THRESHOLD, status_filter=None):
    """Search for flows containing a fuzzy match to the search term in the MasterLabel field
    
    Args:
        search_term: The text to search for in flow labels
        threshold: Minimum similarity score for fuzzy matching (0-1)
        status_filter: Optional filter for flow status (e.g., 'Active', 'Draft')
        
    Returns:
        List of matching flow dictionaries with MasterLabel, DefinitionId, and Status
    """
    # Check if SFDX is installed and authorized
    check_sfdx_installed()
    
    # Get Tooling API connection details
    connection = get_tooling_api_connection()
    if not connection:
        print("Could not establish Tooling API connection")
        return []
    
    instance_url = connection["instance_url"]
    access_token = connection["access_token"]
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Try each available API version starting from newest
        # Most reliable approach to handle different API versions
        api_versions = [57.0, 56.0, 55.0, 54.0, 53.0, 52.0, 51.0, 50.0]
        
        for api_version in api_versions:
            # Try to get a list of all active flows using Tooling API
            url = f"{instance_url}/services/data/v{api_version}/tooling/query"
            
            # Build query with or without status filter
            if status_filter:
                query = f"SELECT Id, MasterLabel, DefinitionId, Status FROM Flow WHERE Status = '{status_filter}'"
            else:
                query = "SELECT Id, MasterLabel, DefinitionId, Status FROM Flow"
                
            params = {"q": query}
            
            print(f"Querying flows using API v{api_version}...")
            response = requests.get(url, headers=headers, params=params)
            
            # Check if this API version works
            if response.status_code == 200:
                print(f"Successfully connected to Tooling API using v{api_version}")
                break
            elif response.status_code == 404:
                print(f"API v{api_version} not available, trying older version...")
                continue
            else:
                print(f"Error with API v{api_version}: {response.status_code}")
                print(response.text[:500])  # Show first 500 chars of error
                continue
        
        else:  # This executes if the loop completes without a break
            print("Could not find a working API version")
            return []
        
        # Process the response
        result = response.json()
        
        if 'records' not in result:
            print("No flow records found in response")
            return []
        
        # Get all flows
        all_flows = result.get('records', [])
        print(f"Found {len(all_flows)} total flows")
        
        # Filter flows using fuzzy matching on MasterLabel
        matching_flows = []
        for flow in all_flows:
            if 'MasterLabel' in flow and fuzzy_match(search_term, flow['MasterLabel'], threshold):
                # Create simplified flow record with just the fields we want
                matching_flow = {
                    'MasterLabel': flow.get('MasterLabel', ''),
                    'DefinitionId': flow.get('DefinitionId', ''),
                    'Status': flow.get('Status', ''),
                    'Id': flow.get('Id', '')
                }
                matching_flows.append(matching_flow)
        
        # Sort results by MasterLabel
        matching_flows.sort(key=lambda x: x.get('MasterLabel', ''))
        
        return matching_flows
        
    except Exception as e:
        print(f"Error searching flows with Tooling API: {str(e)}")
        
        # Fallback to CLI approach
        print("Trying fallback approach...")
        try:
            cmd = "sfdx force:data:soql:query -q \"SELECT Id, MasterLabel, Status FROM Flow\" --json"
            result = run_sfdx_command(cmd)
            
            if not result or 'result' not in result or 'records' not in result['result']:
                print("Fallback approach failed")
                return []
            
            # Process CLI results
            flows = result['result']['records']
            
            # Filter flows using fuzzy matching on MasterLabel
            matching_flows = []
            for flow in flows:
                if 'MasterLabel' in flow and fuzzy_match(search_term, flow['MasterLabel'], threshold):
                    # Check status filter if provided
                    if status_filter and flow.get('Status') != status_filter:
                        continue
                        
                    # Create simplified flow record with just the fields we want
                    matching_flow = {
                        'MasterLabel': flow.get('MasterLabel', ''),
                        'Id': flow.get('Id', ''),
                        'Status': flow.get('Status', ''),
                        # No DefinitionId available in this approach
                        'DefinitionId': 'N/A'
                    }
                    matching_flows.append(matching_flow)
            
            # Sort results by MasterLabel
            matching_flows.sort(key=lambda x: x.get('MasterLabel', ''))
            
            return matching_flows
            
        except Exception as e2:
            print(f"Fallback approach failed: {str(e2)}")
            return []

def search_flows_multi_terms(search_terms, threshold=DEFAULT_SIMILARITY_THRESHOLD, status_filter=None):
    """Search for flows containing fuzzy matches to multiple search terms in the MasterLabel field
    
    This is a more efficient version that queries flows only once for multiple terms.
    
    Args:
        search_terms: List of terms to search for in flow labels
        threshold: Minimum similarity score for fuzzy matching (0-1)
        status_filter: Optional filter for flow status (e.g., 'Active', 'Draft')
        
    Returns:
        Dictionary mapping search terms to lists of matching flow dictionaries
    """
    # Check if SFDX is installed and authorized
    check_sfdx_installed()
    
    # Get Tooling API connection details
    connection = get_tooling_api_connection()
    if not connection:
        print("Could not establish Tooling API connection")
        return {term: [] for term in search_terms}
    
    instance_url = connection["instance_url"]
    access_token = connection["access_token"]
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Initialize results dictionary
    results = {term: [] for term in search_terms}
    
    try:
        # Try each available API version starting from newest
        api_versions = [57.0, 56.0, 55.0, 54.0, 53.0, 52.0, 51.0, 50.0]
        
        for api_version in api_versions:
            # Try to get a list of all flows using Tooling API
            url = f"{instance_url}/services/data/v{api_version}/tooling/query"
            
            # Build query with or without status filter
            if status_filter:
                query = f"SELECT Id, MasterLabel, DefinitionId, Status FROM Flow WHERE Status = '{status_filter}'"
            else:
                query = "SELECT Id, MasterLabel, DefinitionId, Status FROM Flow"
                
            params = {"q": query}
            
            print(f"Querying flows using API v{api_version}...")
            response = requests.get(url, headers=headers, params=params)
            
            # Check if this API version works
            if response.status_code == 200:
                print(f"Successfully connected to Tooling API using v{api_version}")
                break
            elif response.status_code == 404:
                print(f"API v{api_version} not available, trying older version...")
                continue
            else:
                print(f"Error with API v{api_version}: {response.status_code}")
                print(response.text[:500])  # Show first 500 chars of error
                continue
        
        else:  # This executes if the loop completes without a break
            print("Could not find a working API version")
            return {term: [] for term in search_terms}
        
        # Process the response
        result = response.json()
        
        if 'records' not in result:
            print("No flow records found in response")
            return {term: [] for term in search_terms}
        
        # Get all flows
        all_flows = result.get('records', [])
        print(f"Found {len(all_flows)} total flows")
        
        # For each search term, find matching flows
        for search_term in search_terms:
            matching_flows = []
            
            # Filter flows using fuzzy matching on MasterLabel
            for flow in all_flows:
                if 'MasterLabel' in flow and fuzzy_match(search_term, flow['MasterLabel'], threshold):
                    # Create simplified flow record with just the fields we want
                    matching_flow = {
                        'MasterLabel': flow.get('MasterLabel', ''),
                        'DefinitionId': flow.get('DefinitionId', ''),
                        'Status': flow.get('Status', ''),
                        'Id': flow.get('Id', '')
                    }
                    matching_flows.append(matching_flow)
            
            # Sort results by MasterLabel
            matching_flows.sort(key=lambda x: x.get('MasterLabel', ''))
            
            # Store in results dictionary
            results[search_term] = matching_flows
            print(f"Found {len(matching_flows)} flows matching '{search_term}'")
            
        return results
        
    except Exception as e:
        print(f"Error searching flows with Tooling API: {str(e)}")
        
        # Fallback to CLI approach
        print("Trying fallback approach...")
        try:
            cmd = "sfdx force:data:soql:query -q \"SELECT Id, MasterLabel, Status FROM Flow\" --json"
            result = run_sfdx_command(cmd)
            
            if not result or 'result' not in result or 'records' not in result['result']:
                print("Fallback approach failed")
                return {term: [] for term in search_terms}
            
            # Process CLI results
            flows = result['result']['records']
            
            # For each search term, find matching flows
            for search_term in search_terms:
                matching_flows = []
                
                # Filter flows using fuzzy matching on MasterLabel
                for flow in flows:
                    if 'MasterLabel' in flow and fuzzy_match(search_term, flow['MasterLabel'], threshold):
                        # Check status filter if provided
                        if status_filter and flow.get('Status') != status_filter:
                            continue
                            
                        # Create simplified flow record with just the fields we want
                        matching_flow = {
                            'MasterLabel': flow.get('MasterLabel', ''),
                            'Id': flow.get('Id', ''),
                            'Status': flow.get('Status', ''),
                            # No DefinitionId available in this approach
                            'DefinitionId': 'N/A'
                        }
                        matching_flows.append(matching_flow)
                
                # Sort results by MasterLabel
                matching_flows.sort(key=lambda x: x.get('MasterLabel', ''))
                
                # Store in results dictionary
                results[search_term] = matching_flows
                print(f"Found {len(matching_flows)} flows matching '{search_term}'")
            
            return results
            
        except Exception as e2:
            print(f"Fallback approach failed: {str(e2)}")
            return {term: [] for term in search_terms}

def search_flows_multi_terms_summary(search_terms, threshold=DEFAULT_SIMILARITY_THRESHOLD, status_filter=None):
    """Search for flows containing multiple terms and return which terms were found
    
    Args:
        search_terms: List of terms to search for in flow labels
        threshold: Minimum similarity score for fuzzy matching (0-1)
        status_filter: Optional filter for flow status (e.g., 'Active', 'Draft')
        
    Returns:
        Dictionary mapping "Term_{term}" to boolean existence status
    """
    # Get detailed results
    detailed_results = search_flows_multi_terms(search_terms, threshold, status_filter)
    
    # Convert to simple yes/no results
    summary_results = {}
    for term, matching_flows in detailed_results.items():
        summary_results[f"Flow_{term}"] = len(matching_flows) > 0
        
    return summary_results

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Search for Salesforce flows containing a search term in their name')
    parser.add_argument('search_term', type=str, help='Text to search for in flow labels (comma-separated for multiple terms)')
    parser.add_argument('--threshold', '-t', type=float, default=DEFAULT_SIMILARITY_THRESHOLD,
                        help=f'Minimum similarity score for fuzzy matching (0-1, default: {DEFAULT_SIMILARITY_THRESHOLD})')
    parser.add_argument('--status', '-s', type=str, choices=['Active', 'Draft', 'Obsolete', 'InvalidDraft'],
                        help='Filter flows by status')
    parser.add_argument('--output', '-o', type=str, choices=['text', 'json', 'csv'], default='text',
                        help='Output format (default: text)')
    parser.add_argument('--output-file', '-f', type=str, 
                        help='File to save results to (default: output to console)')
    return parser.parse_args()

def main():
    """Main function"""
    try:
        # Parse command-line arguments
        args = parse_args()
        
        search_term = args.search_term
        threshold = args.threshold
        status_filter = args.status
        output_format = args.output
        output_file = args.output_file
        
        # Check if search_term contains commas (multiple terms)
        if ',' in search_term:
            search_terms = [term.strip() for term in search_term.split(',')]
            print(f"Searching for flows with labels similar to any of: {', '.join(search_terms)}")
            if status_filter:
                print(f"Filtering for flows with status: {status_filter}")
            print(f"Using similarity threshold: {threshold}")
            
            # Search for flows matching multiple terms
            results_by_term = search_flows_multi_terms(search_terms, threshold, status_filter)
            
            # Combine all matching flows into a single list
            all_matching_flows = []
            for term, flows in results_by_term.items():
                all_matching_flows.extend(flows)
            
            # Remove duplicates (same flow might match multiple terms)
            unique_flows = {}
            for flow in all_matching_flows:
                # Use DefinitionId or Id as key to identify unique flows
                key = flow.get('DefinitionId') or flow.get('Id')
                if key:
                    unique_flows[key] = flow
            
            matching_flows = list(unique_flows.values())
            # Sort by MasterLabel
            matching_flows.sort(key=lambda x: x.get('MasterLabel', ''))
        else:
            print(f"Searching for flows with labels similar to: '{search_term}'")
            if status_filter:
                print(f"Filtering for flows with status: {status_filter}")
            print(f"Using similarity threshold: {threshold}")
            
            # Search for flows with the single term
            matching_flows = search_flows_with_tooling_api(search_term, threshold, status_filter)
        
        if not matching_flows:
            print("No matching flows found")
            return
        
        print(f"Found {len(matching_flows)} matching flows")
        
        # Format and output results
        if output_format == 'json':
            output = json.dumps(matching_flows, indent=2)
        elif output_format == 'csv':
            import csv
            import io
            
            output_buffer = io.StringIO()
            writer = csv.writer(output_buffer)
            
            # Write header
            writer.writerow(['MasterLabel', 'DefinitionId', 'Status', 'Id'])
            
            # Write flow data
            for flow in matching_flows:
                writer.writerow([
                    flow.get('MasterLabel', ''),
                    flow.get('DefinitionId', ''),
                    flow.get('Status', ''),
                    flow.get('Id', '')
                ])
            
            output = output_buffer.getvalue()
        else:  # text format
            output = "Matching Flows:\n"
            output += "-" * 80 + "\n"
            output += f"{'MasterLabel':<40} {'Status':<15} {'DefinitionId':<36}\n"
            output += "-" * 80 + "\n"
            
            for flow in matching_flows:
                output += f"{flow.get('MasterLabel', ''):<40} {flow.get('Status', ''):<15} {flow.get('DefinitionId', ''):<36}\n"
        
        # Output results
        if output_file:
            with open(output_file, 'w') as f:
                f.write(output)
            print(f"Results saved to {output_file}")
        else:
            print(output)
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 