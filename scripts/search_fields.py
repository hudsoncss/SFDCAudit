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

def get_object_fields(object_name):
    """Get all fields for a specific object
    
    Args:
        object_name: API name of the Salesforce object
        
    Returns:
        List of field dictionaries with name, label, type, etc.
    """
    try:
        cmd = f'sfdx force:schema:sobject:describe -s {object_name} --json'
        result = run_sfdx_command(cmd)
        
        if not result or 'result' not in result or 'fields' not in result['result']:
            print(f"Failed to get fields for object: {object_name}")
            return []
        
        return result['result']['fields']
    except Exception as e:
        print(f"Error getting fields for {object_name}: {str(e)}")
        return []

def search_fields_in_object(object_name, search_term, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for fields in an object matching a search term
    
    Args:
        object_name: API name of the Salesforce object
        search_term: Term to search for in field names/labels
        threshold: Minimum similarity score for fuzzy matching
        
    Returns:
        List of matching field dictionaries
    """
    fields = get_object_fields(object_name)
    matching_fields = []
    
    for field in fields:
        # Check field name
        name_match = fuzzy_match(search_term, field.get('name', ''), threshold)
        
        # Check field label
        label_match = fuzzy_match(search_term, field.get('label', ''), threshold)
        
        # Check field description
        desc_match = fuzzy_match(search_term, field.get('description', ''), threshold)
        
        if name_match or label_match or desc_match:
            # Add object name to the field info
            field['objectName'] = object_name
            matching_fields.append(field)
    
    return matching_fields

def search_fields_multi_objects(objects, search_term, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for fields matching a term across multiple objects
    
    Args:
        objects: List of object API names to search
        search_term: Term to search for in field names/labels
        threshold: Minimum similarity score for fuzzy matching
        
    Returns:
        Dictionary mapping object names to lists of matching fields
    """
    results = {}
    
    for obj in objects:
        matching_fields = search_fields_in_object(obj, search_term, threshold)
        if matching_fields:
            results[obj] = matching_fields
            print(f"Found {len(matching_fields)} matching fields in {obj}")
        else:
            print(f"No matching fields found in {obj}")
    
    return results

def search_fields_multi_terms(objects, search_terms, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for fields matching multiple terms across multiple objects
    
    Args:
        objects: List of object API names to search
        search_terms: List of terms to search for
        threshold: Minimum similarity score for fuzzy matching
        
    Returns:
        Dictionary mapping search terms to dictionaries of object results
    """
    results = {}
    
    for term in search_terms:
        print(f"\nSearching for term: {term}")
        results[term] = search_fields_multi_objects(objects, term, threshold)
    
    return results

def search_fields_summary(objects, search_terms, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for fields and return which terms were found in which objects
    
    Args:
        objects: List of object API names to search
        search_terms: List of terms to search for
        threshold: Minimum similarity score for fuzzy matching
        
    Returns:
        Dictionary mapping "Field_{term}_{object}" to boolean existence status
    """
    # Get detailed results
    detailed_results = search_fields_multi_terms(objects, search_terms, threshold)
    
    # Convert to simple yes/no results
    summary_results = {}
    for term, obj_results in detailed_results.items():
        for obj in objects:
            key = f"Field_{term}_{obj}"
            summary_results[key] = obj in obj_results and len(obj_results[obj]) > 0
    
    return summary_results

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Search for fields in Salesforce objects')
    parser.add_argument('search_term', type=str, help='Text to search for (comma-separated for multiple terms)')
    parser.add_argument('--objects', '-o', type=str, required=True,
                        help='Objects to search (comma-separated)')
    parser.add_argument('--threshold', '-t', type=float, default=DEFAULT_SIMILARITY_THRESHOLD,
                        help=f'Minimum similarity score for fuzzy matching (0-1, default: {DEFAULT_SIMILARITY_THRESHOLD})')
    parser.add_argument('--output', '-f', type=str, choices=['text', 'json', 'csv'], default='text',
                        help='Output format (default: text)')
    parser.add_argument('--output-file', type=str, 
                        help='File to save results to (default: output to console)')
    return parser.parse_args()

def main():
    """Main function"""
    try:
        # Parse command-line arguments
        args = parse_args()
        
        # Split search terms and objects
        search_terms = [term.strip() for term in args.search_term.split(',')]
        objects = [obj.strip() for obj in args.objects.split(',')]
        
        print(f"Searching for fields with terms: {', '.join(search_terms)}")
        print(f"In objects: {', '.join(objects)}")
        print(f"Using similarity threshold: {args.threshold}")
        
        # Search for fields
        results = search_fields_multi_terms(objects, search_terms, args.threshold)
        
        # Format and output results
        if args.output == 'json':
            output = json.dumps(results, indent=2)
        elif args.output == 'csv':
            import csv
            import io
            
            output_buffer = io.StringIO()
            writer = csv.writer(output_buffer)
            
            # Write header
            writer.writerow(['Search Term', 'Object', 'Field Name', 'Field Label', 'Field Type', 'Description'])
            
            # Write results
            for term, obj_results in results.items():
                for obj, fields in obj_results.items():
                    for field in fields:
                        writer.writerow([
                            term,
                            obj,
                            field.get('name', ''),
                            field.get('label', ''),
                            field.get('type', ''),
                            field.get('description', '')
                        ])
            
            output = output_buffer.getvalue()
        else:  # text format
            output = ""
            for term, obj_results in results.items():
                output += f"\nResults for term '{term}':\n"
                output += "=" * 80 + "\n"
                
                if not obj_results:
                    output += "No matching fields found in any object\n"
                    continue
                
                for obj, fields in obj_results.items():
                    output += f"\nObject: {obj}\n"
                    output += "-" * 40 + "\n"
                    
                    for field in fields:
                        output += f"Name: {field.get('name', '')}\n"
                        output += f"Label: {field.get('label', '')}\n"
                        output += f"Type: {field.get('type', '')}\n"
                        if field.get('description'):
                            output += f"Description: {field.get('description')}\n"
                        output += "\n"
        
        # Output results
        if args.output_file:
            with open(args.output_file, 'w') as f:
                f.write(output)
            print(f"\nResults saved to {args.output_file}")
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