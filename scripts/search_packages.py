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

def get_installed_packages():
    """Get list of installed packages from Package Manager"""
    cmd = "sfdx force:package:installed:list --json"
    result = run_sfdx_command(cmd)
    
    if not result or 'result' not in result:
        return []
    
    return result['result']

def get_namespace_registry():
    """Get namespaces from NamespaceRegistry using Tooling API"""
    connection = get_tooling_api_connection()
    if not connection:
        return []
    
    instance_url = connection["instance_url"]
    access_token = connection["access_token"]
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        url = f"{instance_url}/services/data/v57.0/tooling/query"
        query = "SELECT Id, NamespacePrefix FROM NamespaceRegistry"
        params = {"q": query}
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            result = response.json()
            return result.get('records', [])
    except Exception as e:
        print(f"Error querying NamespaceRegistry: {str(e)}")
    
    return []

def get_custom_fields_with_namespace():
    """Get custom fields that have namespace prefixes"""
    try:
        # Query for custom fields using Tooling API
        cmd = "sfdx force:mdapi:listmetadata -m CustomField --json"
        result = run_sfdx_command(cmd)
        
        if not result or not isinstance(result.get('result'), list):
            return []
        
        # Filter for fields with namespace prefixes
        namespace_fields = []
        for field in result['result']:
            if isinstance(field, dict) and 'fullName' in field:
                field_name = field['fullName']
                if '__' in field_name:
                    namespace = field_name.split('__')[0]
                    if namespace:
                        namespace_fields.append({
                            'namespace': namespace,
                            'field': field_name,
                            'type': 'CustomField'
                        })
        
        return namespace_fields
    except Exception as e:
        print(f"Error getting custom fields: {str(e)}")
        return []

def get_custom_objects_with_namespace():
    """Get custom objects that have namespace prefixes"""
    try:
        # Query for custom objects using Tooling API
        cmd = "sfdx force:mdapi:listmetadata -m CustomObject --json"
        result = run_sfdx_command(cmd)
        
        if not result or not isinstance(result.get('result'), list):
            return []
        
        # Filter for objects with namespace prefixes
        namespace_objects = []
        for obj in result['result']:
            if isinstance(obj, dict) and 'fullName' in obj:
                obj_name = obj['fullName']
                if '__' in obj_name:
                    namespace = obj_name.split('__')[0]
                    if namespace:
                        namespace_objects.append({
                            'namespace': namespace,
                            'object': obj_name,
                            'type': 'CustomObject'
                        })
        
        return namespace_objects
    except Exception as e:
        print(f"Error getting custom objects: {str(e)}")
        return []

def search_packages_with_term(search_term, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for packages and namespaces matching a search term
    
    Args:
        search_term: Term to search for in package/namespace names
        threshold: Minimum similarity score for fuzzy matching
        
    Returns:
        Boolean indicating if the package/namespace was found
    """
    # Check installed packages
    installed_packages = get_installed_packages()
    for pkg in installed_packages:
        if not isinstance(pkg, dict):
            continue
            
        # Check package name and namespace
        pkg_name = pkg.get('Package', pkg.get('PackageName', ''))
        namespace = pkg.get('NamespacePrefix', '')
        
        if (fuzzy_match(search_term, pkg_name, threshold) or 
            fuzzy_match(search_term, namespace, threshold)):
            return True
    
    # Check NamespaceRegistry
    namespace_records = get_namespace_registry()
    for record in namespace_records:
        namespace = record.get('NamespacePrefix', '')
        if fuzzy_match(search_term, namespace, threshold):
            return True
    
    # Check custom fields
    namespace_fields = get_custom_fields_with_namespace()
    for field in namespace_fields:
        if fuzzy_match(search_term, field['namespace'], threshold):
            return True
    
    # Check custom objects
    namespace_objects = get_custom_objects_with_namespace()
    for obj in namespace_objects:
        if fuzzy_match(search_term, obj['namespace'], threshold):
            return True
    
    return False

def search_packages_multi_terms(search_terms, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for packages and namespaces matching multiple search terms
    
    Args:
        search_terms: List of terms to search for
        threshold: Minimum similarity score for fuzzy matching
        
    Returns:
        Dictionary mapping terms to boolean existence status
    """
    results = {}
    
    for term in search_terms:
        exists = search_packages_with_term(term, threshold)
        results[term] = exists
        print(f"Package '{term}': {'Found' if exists else 'Not found'}")
    
    return results

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Search for installed Salesforce packages and namespace usage')
    parser.add_argument('search_term', type=str, help='Text to search for (comma-separated for multiple terms)')
    parser.add_argument('--threshold', '-t', type=float, default=DEFAULT_SIMILARITY_THRESHOLD,
                        help=f'Minimum similarity score for fuzzy matching (0-1, default: {DEFAULT_SIMILARITY_THRESHOLD})')
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
        output_format = args.output
        output_file = args.output_file
        
        # Check if search_term contains commas (multiple terms)
        if ',' in search_term:
            search_terms = [term.strip() for term in search_term.split(',')]
        else:
            search_terms = [search_term]
        
        print(f"Searching for packages: {', '.join(search_terms)}")
        print(f"Using similarity threshold: {threshold}")
        
        # Search for packages
        results = search_packages_multi_terms(search_terms, threshold)
        
        # Format and output results
        if output_format == 'json':
            output = json.dumps(results, indent=2)
        elif output_format == 'csv':
            import csv
            import io
            
            output_buffer = io.StringIO()
            writer = csv.writer(output_buffer)
            
            # Write header and results
            writer.writerow(['Package', 'Found'])
            for term, exists in results.items():
                writer.writerow([term, exists])
            
            output = output_buffer.getvalue()
        else:  # text format
            output = "\nPackage Search Results:\n"
            output += "-" * 40 + "\n"
            for term, exists in results.items():
                output += f"{term}: {'Found' if exists else 'Not found'}\n"
        
        # Output results
        if output_file:
            with open(output_file, 'w') as f:
                f.write(output)
            print(f"\nResults saved to {output_file}")
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