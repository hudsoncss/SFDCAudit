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
    # None check
    if text is None:
        return False
        
    # Simple case: direct substring match
    if search_term.lower() in text.lower():
        return True
    
    # Advanced case: fuzzy matching using difflib
    similarity = difflib.SequenceMatcher(None, search_term.lower(), text.lower()).ratio()
    return similarity >= threshold

def search_apex_with_tooling_api(search_term, apex_type="both", threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for Apex classes and triggers containing a search term
    
    Args:
        search_term: The text to search for in Apex code
        apex_type: Type of Apex to search - "class", "trigger", or "both"
        threshold: Minimum similarity score for fuzzy matching (0-1)
        
    Returns:
        List of matching Apex dictionaries with Name, Id, and Body
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
    
    matching_apex = []
    
    try:
        # Try each available API version starting from newest
        api_versions = [57.0, 56.0, 55.0, 54.0, 53.0, 52.0, 51.0, 50.0]
        
        for api_version in api_versions:
            # Try to use Tooling API
            url = f"{instance_url}/services/data/v{api_version}/tooling/query"
            
            apex_types_to_search = []
            if apex_type == "class" or apex_type == "both":
                apex_types_to_search.append("ApexClass")
            if apex_type == "trigger" or apex_type == "both":
                apex_types_to_search.append("ApexTrigger")
            
            for apex_object in apex_types_to_search:
                # First query: get all Apex classes/triggers by name only (lightweight)
                query = f"SELECT Id, Name FROM {apex_object}"
                params = {"q": query}
                
                print(f"Querying {apex_object} names using API v{api_version}...")
                response = requests.get(url, headers=headers, params=params)
                
                # Check if this API version works
                if response.status_code != 200:
                    print(f"Error with API v{api_version} for {apex_object}: {response.status_code}")
                    break  # Try next API version
                
                # Process the response
                result = response.json()
                
                if 'records' not in result:
                    print(f"No {apex_object} records found in response")
                    continue
                
                apex_records = result.get('records', [])
                print(f"Found {len(apex_records)} {apex_object} records")
                
                # First pass: filter by name to reduce number of bodies we need to fetch
                name_matches = []
                for record in apex_records:
                    if 'Name' in record and fuzzy_match(search_term, record['Name'], threshold):
                        name_matches.append(record)
                
                print(f"Found {len(name_matches)} {apex_object} records with matching names")
                
                # Get bodies only for the matching names
                for record in name_matches:
                    body_query = f"SELECT Id, Name, Body FROM {apex_object} WHERE Id = '{record['Id']}'"
                    body_params = {"q": body_query}
                    
                    body_response = requests.get(url, headers=headers, params=body_params)
                    if body_response.status_code != 200:
                        print(f"Error getting body for {record['Name']}: {body_response.status_code}")
                        continue
                    
                    body_result = body_response.json()
                    if 'records' in body_result and len(body_result['records']) > 0:
                        apex_record = body_result['records'][0]
                        matching_apex.append({
                            'Name': apex_record.get('Name', ''),
                            'Id': apex_record.get('Id', ''),
                            'Type': apex_object,
                            'Body': apex_record.get('Body', '')
                        })
                
                # Second pass: for items that didn't match by name, search in body
                # Get bodies in small batches to avoid query timeout
                batch_size = 10
                for i in range(0, len(apex_records), batch_size):
                    batch = apex_records[i:i+batch_size]
                    id_list = "'" + "','".join([record['Id'] for record in batch]) + "'"
                    body_query = f"SELECT Id, Name, Body FROM {apex_object} WHERE Id IN ({id_list})"
                    body_params = {"q": body_query}
                    
                    body_response = requests.get(url, headers=headers, params=body_params)
                    if body_response.status_code != 200:
                        print(f"Error getting batch bodies: {body_response.status_code}")
                        continue
                    
                    body_result = body_response.json()
                    if 'records' in body_result:
                        for apex_record in body_result['records']:
                            # Skip if we already matched this by name
                            if any(match['Id'] == apex_record['Id'] for match in matching_apex):
                                continue
                                
                            # Check body for match
                            if 'Body' in apex_record and fuzzy_match(search_term, apex_record['Body'], threshold):
                                matching_apex.append({
                                    'Name': apex_record.get('Name', ''),
                                    'Id': apex_record.get('Id', ''),
                                    'Type': apex_object,
                                    'Body': apex_record.get('Body', '')
                                })
            
            # If we got here without errors, we can break the API version loop
            break
        
        # Sort results by Type and Name
        matching_apex.sort(key=lambda x: (x.get('Type', ''), x.get('Name', '')))
        
        return matching_apex
        
    except Exception as e:
        print(f"Error searching Apex with Tooling API: {str(e)}")
        
        # Fallback to CLI approach
        print("Trying fallback approach using SFDX CLI...")
        fallback_results = search_apex_with_sfdx_cli(search_term, apex_type, threshold)
        return fallback_results

def search_apex_with_sfdx_cli(search_term, apex_type="both", threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Fallback approach to search Apex using SFDX CLI commands"""
    matching_apex = []
    
    try:
        apex_types_to_search = []
        if apex_type == "class" or apex_type == "both":
            apex_types_to_search.append("ApexClass")
        if apex_type == "trigger" or apex_type == "both":
            apex_types_to_search.append("ApexTrigger")
        
        for apex_object in apex_types_to_search:
            cmd = f"sfdx force:data:soql:query -q \"SELECT Id, Name FROM {apex_object}\" --json"
            result = run_sfdx_command(cmd)
            
            if not result or 'result' not in result or 'records' not in result['result']:
                print(f"Failed to query {apex_object} with SFDX CLI")
                continue
            
            apex_records = result['result']['records']
            print(f"Found {len(apex_records)} {apex_object} records")
            
            # First pass: filter by name
            name_matches = []
            for record in apex_records:
                if 'Name' in record and fuzzy_match(search_term, record['Name'], threshold):
                    name_matches.append(record)
            
            print(f"Found {len(name_matches)} {apex_object} records with matching names")
            
            # Get bodies for name matches
            for record in name_matches:
                body_cmd = f"sfdx force:data:soql:query -q \"SELECT Id, Name, Body FROM {apex_object} WHERE Id = '{record['Id']}'\" --json"
                body_result = run_sfdx_command(body_cmd)
                
                if body_result and 'result' in body_result and 'records' in body_result['result'] and len(body_result['result']['records']) > 0:
                    apex_record = body_result['result']['records'][0]
                    matching_apex.append({
                        'Name': apex_record.get('Name', ''),
                        'Id': apex_record.get('Id', ''),
                        'Type': apex_object,
                        'Body': apex_record.get('Body', '')
                    })
            
            # Second pass: check bodies in batches
            batch_size = 5  # Smaller batch for CLI
            for i in range(0, len(apex_records), batch_size):
                batch = apex_records[i:i+batch_size]
                
                for record in batch:
                    # Skip if we already matched by name
                    if any(match['Id'] == record['Id'] for match in matching_apex):
                        continue
                    
                    body_cmd = f"sfdx force:data:soql:query -q \"SELECT Id, Name, Body FROM {apex_object} WHERE Id = '{record['Id']}'\" --json"
                    body_result = run_sfdx_command(body_cmd)
                    
                    if body_result and 'result' in body_result and 'records' in body_result['result'] and len(body_result['result']['records']) > 0:
                        apex_record = body_result['result']['records'][0]
                        if 'Body' in apex_record and fuzzy_match(search_term, apex_record['Body'], threshold):
                            matching_apex.append({
                                'Name': apex_record.get('Name', ''),
                                'Id': apex_record.get('Id', ''),
                                'Type': apex_object,
                                'Body': apex_record.get('Body', '')
                            })
        
        # Sort results by Type and Name
        matching_apex.sort(key=lambda x: (x.get('Type', ''), x.get('Name', '')))
        
        return matching_apex
        
    except Exception as e:
        print(f"Fallback approach failed: {str(e)}")
        return []

def search_apex_multi_terms(search_terms, apex_type="both", threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for Apex classes and triggers containing multiple search terms
    
    This is a more efficient version that queries Apex only once for multiple terms.
    
    Args:
        search_terms: List of terms to search for in Apex code
        apex_type: Type of Apex to search - "class", "trigger", or "both"
        threshold: Minimum similarity score for fuzzy matching (0-1)
        
    Returns:
        Dictionary mapping search terms to lists of matching Apex dictionaries
    """
    # Check if SFDX is installed and authorized
    check_sfdx_installed()
    
    # Initialize results dictionary
    results = {term: [] for term in search_terms}
    
    # Get all Apex first (do this once for all terms)
    all_apex = []
    
    # Get Tooling API connection details
    connection = get_tooling_api_connection()
    if not connection:
        print("Could not establish Tooling API connection")
        return results
    
    instance_url = connection["instance_url"]
    access_token = connection["access_token"]
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Try each available API version starting from newest
        api_versions = [57.0, 56.0, 55.0, 54.0, 53.0, 52.0, 51.0, 50.0]
        
        for api_version in api_versions:
            url = f"{instance_url}/services/data/v{api_version}/tooling/query"
            
            apex_types_to_search = []
            if apex_type == "class" or apex_type == "both":
                apex_types_to_search.append("ApexClass")
            if apex_type == "trigger" or apex_type == "both":
                apex_types_to_search.append("ApexTrigger")
            
            for apex_object in apex_types_to_search:
                # Query in batches to avoid timeouts
                batch_size = 50
                continue_query = True
                query_locator = None
                
                first_query = True
                
                while continue_query:
                    # Construct the query
                    if first_query:
                        query = f"SELECT Id, Name, Body FROM {apex_object}"
                        params = {"q": query}
                        first_query = False
                    else:
                        # Use queryMore with the query locator
                        params = {"q": query_locator}
                    
                    print(f"Querying {apex_object} batch using API v{api_version}...")
                    
                    if query_locator:
                        url = f"{instance_url}/services/data/v{api_version}/tooling/query/{query_locator}"
                        response = requests.get(url, headers=headers)
                    else:
                        response = requests.get(url, headers=headers, params=params)
                    
                    # Check if this API version works
                    if response.status_code != 200:
                        print(f"Error with API v{api_version} for {apex_object}: {response.status_code}")
                        break  # Try next API version
                    
                    # Process the response
                    result = response.json()
                    
                    if 'records' not in result:
                        print(f"No {apex_object} records found in response")
                        break
                    
                    apex_records = result.get('records', [])
                    print(f"Retrieved {len(apex_records)} {apex_object} records in batch")
                    
                    for record in apex_records:
                        all_apex.append({
                            'Name': record.get('Name', ''),
                            'Id': record.get('Id', ''),
                            'Type': apex_object,
                            'Body': record.get('Body', '')
                        })
                    
                    # Check if there are more records to query
                    if result.get('done', True):
                        continue_query = False
                    else:
                        query_locator = result.get('nextRecordsUrl', '').split('/')[-1]
            
            # If we got here without errors with any API version, break the loop
            if all_apex:
                break
            
        # If Tooling API failed, try SFDX CLI
        if not all_apex:
            print("Tooling API approach failed, trying SFDX CLI...")
            all_apex = get_all_apex_with_sfdx(apex_type)
        
        print(f"Retrieved {len(all_apex)} total Apex items")
        
        # Now search each term against all Apex
        for search_term in search_terms:
            matching_apex = []
            
            for apex_item in all_apex:
                name_match = False
                body_match = False
                
                # Check name match
                if fuzzy_match(search_term, apex_item.get('Name', ''), threshold):
                    name_match = True
                
                # Check body match if needed
                if not name_match and fuzzy_match(search_term, apex_item.get('Body', ''), threshold):
                    body_match = True
                
                if name_match or body_match:
                    matching_apex.append(apex_item)
            
            # Store results for this term
            results[search_term] = matching_apex
            print(f"Found {len(matching_apex)} Apex items matching '{search_term}'")
        
        return results
        
    except Exception as e:
        print(f"Error in search_apex_multi_terms: {str(e)}")
        # If everything fails, return empty results
        return results

def get_all_apex_with_sfdx(apex_type="both"):
    """Get all Apex classes and triggers using SFDX CLI"""
    all_apex = []
    
    apex_types_to_search = []
    if apex_type == "class" or apex_type == "both":
        apex_types_to_search.append("ApexClass")
    if apex_type == "trigger" or apex_type == "both":
        apex_types_to_search.append("ApexTrigger")
    
    for apex_object in apex_types_to_search:
        try:
            cmd = f"sfdx force:data:soql:query -q \"SELECT Id, Name FROM {apex_object}\" --json"
            result = run_sfdx_command(cmd)
            
            if not result or 'result' not in result or 'records' not in result['result']:
                print(f"Failed to query {apex_object} with SFDX CLI")
                continue
            
            apex_records = result['result']['records']
            print(f"Found {len(apex_records)} {apex_object} records")
            
            # Get bodies in batches
            batch_size = 5
            for i in range(0, len(apex_records), batch_size):
                batch = apex_records[i:i+batch_size]
                
                for record in batch:
                    body_cmd = f"sfdx force:data:soql:query -q \"SELECT Id, Name, Body FROM {apex_object} WHERE Id = '{record['Id']}'\" --json"
                    body_result = run_sfdx_command(body_cmd)
                    
                    if body_result and 'result' in body_result and 'records' in body_result['result'] and len(body_result['result']['records']) > 0:
                        apex_record = body_result['result']['records'][0]
                        all_apex.append({
                            'Name': apex_record.get('Name', ''),
                            'Id': apex_record.get('Id', ''),
                            'Type': apex_object,
                            'Body': apex_record.get('Body', '')
                        })
        
        except Exception as e:
            print(f"Error getting {apex_object} with SFDX: {str(e)}")
    
    return all_apex

def search_apex_multi_terms_summary(search_terms, apex_type="both", threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for Apex containing multiple terms and return which terms were found
    
    Args:
        search_terms: List of terms to search for in Apex code
        apex_type: Type of Apex to search - "class", "trigger", or "both"
        threshold: Minimum similarity score for fuzzy matching (0-1)
        
    Returns:
        Dictionary mapping "Apex_{term}" to boolean existence status
    """
    # Get detailed results
    detailed_results = search_apex_multi_terms(search_terms, apex_type, threshold)
    
    # Convert to simple yes/no results
    summary_results = {}
    for term, matching_apex in detailed_results.items():
        summary_results[f"Apex_{term}"] = len(matching_apex) > 0
        
    return summary_results

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Search for Salesforce Apex code containing specific terms')
    parser.add_argument('search_term', type=str, help='Text to search for in Apex (comma-separated for multiple terms)')
    parser.add_argument('--type', '-t', type=str, choices=['class', 'trigger', 'both'], default='both',
                        help='Type of Apex to search (default: both)')
    parser.add_argument('--threshold', '-s', type=float, default=DEFAULT_SIMILARITY_THRESHOLD,
                        help=f'Minimum similarity score for fuzzy matching (0-1, default: {DEFAULT_SIMILARITY_THRESHOLD})')
    parser.add_argument('--output', '-o', type=str, choices=['text', 'json', 'csv'], default='text',
                        help='Output format (default: text)')
    parser.add_argument('--output-file', '-f', type=str, 
                        help='File to save results to (default: output to console)')
    parser.add_argument('--include-body', '-b', action='store_true',
                        help='Include full Apex body in output (default: false)')
    return parser.parse_args()

def main():
    """Main function"""
    try:
        # Parse command-line arguments
        args = parse_args()
        
        search_term = args.search_term
        apex_type = args.type
        threshold = args.threshold
        output_format = args.output
        output_file = args.output_file
        include_body = args.include_body
        
        # Check if search_term contains commas (multiple terms)
        if ',' in search_term:
            search_terms = [term.strip() for term in search_term.split(',')]
            print(f"Searching for Apex {apex_type} with terms: {', '.join(search_terms)}")
            print(f"Using similarity threshold: {threshold}")
            
            # Search for Apex matching multiple terms
            results_by_term = search_apex_multi_terms(search_terms, apex_type, threshold)
            
            # Combine all matching Apex into a single list
            all_matching_apex = []
            for term, apex_items in results_by_term.items():
                all_matching_apex.extend(apex_items)
            
            # Remove duplicates (same Apex might match multiple terms)
            unique_apex = {}
            for apex in all_matching_apex:
                # Use Id as key to identify unique apex
                if apex.get('Id'):
                    unique_apex[apex['Id']] = apex
            
            matching_apex = list(unique_apex.values())
            # Sort by Type then Name
            matching_apex.sort(key=lambda x: (x.get('Type', ''), x.get('Name', '')))
        else:
            print(f"Searching for Apex {apex_type} with term: '{search_term}'")
            print(f"Using similarity threshold: {threshold}")
            
            # Search for Apex with the single term
            matching_apex = search_apex_with_tooling_api(search_term, apex_type, threshold)
        
        if not matching_apex:
            print("No matching Apex found")
            return
        
        print(f"Found {len(matching_apex)} matching Apex items")
        
        # Format and output results
        if output_format == 'json':
            # Optionally remove body from output if not requested
            if not include_body:
                for apex in matching_apex:
                    if 'Body' in apex:
                        del apex['Body']
            
            output = json.dumps(matching_apex, indent=2)
        elif output_format == 'csv':
            import csv
            import io
            
            output_buffer = io.StringIO()
            writer = csv.writer(output_buffer)
            
            # Write header
            header = ['Name', 'Type', 'Id']
            if include_body:
                header.append('Body')
            writer.writerow(header)
            
            # Write apex data
            for apex in matching_apex:
                row = [
                    apex.get('Name', ''),
                    apex.get('Type', ''),
                    apex.get('Id', '')
                ]
                if include_body:
                    row.append(apex.get('Body', ''))
                writer.writerow(row)
            
            output = output_buffer.getvalue()
        else:  # text format
            output = "Matching Apex:\n"
            output += "-" * 80 + "\n"
            header = f"{'Name':<40} {'Type':<15} {'Id':<36}"
            output += header + "\n"
            output += "-" * 80 + "\n"
            
            for apex in matching_apex:
                line = f"{apex.get('Name', ''):<40} {apex.get('Type', ''):<15} {apex.get('Id', ''):<36}"
                output += line + "\n"
                
                # Optionally add body with indentation
                if include_body and 'Body' in apex:
                    body_lines = apex['Body'].split('\n')
                    for body_line in body_lines[:10]:  # Show first 10 lines only
                        output += f"    {body_line}\n"
                    if len(body_lines) > 10:
                        output += "    ... (truncated)\n"
                    output += "\n"
        
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