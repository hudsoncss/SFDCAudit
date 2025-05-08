#!/usr/bin/env python3

import subprocess
import json
import argparse
import sys
import difflib
import re

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

def get_all_objects(include_custom=True, include_standard=False):
    """Get all Salesforce objects
    
    Args:
        include_custom: Whether to include custom objects
        include_standard: Whether to include standard objects
        
    Returns:
        List of object API names
    """
    # Check if SFDX is installed
    check_sfdx_installed()
    
    cmd = "sfdx force:schema:sobject:list --json"
    result = run_sfdx_command(cmd)
    
    if not result:
        return []
    
    # Handle different response formats
    sobjects = []
    if isinstance(result.get("result", []), list):
        for obj in result.get("result", []):
            if isinstance(obj, dict) and "name" in obj:
                sobjects.append(obj["name"])
            elif isinstance(obj, str):
                sobjects.append(obj)
    elif isinstance(result.get("result", {}), dict) and "sobjects" in result["result"]:
        # Alternative format where sobjects is a key in result
        sobjects = [obj["name"] for obj in result["result"]["sobjects"] if isinstance(obj, dict) and "name" in obj]
    
    # Filter objects based on parameters
    filtered_objects = []
    for obj in sobjects:
        if not isinstance(obj, str):
            continue
            
        is_custom = obj.endswith("__c")
        if (include_custom and is_custom) or (include_standard and not is_custom):
            filtered_objects.append(obj)
    
    return filtered_objects

def get_object_details(object_name):
    """Get detailed information about a specific object
    
    Args:
        object_name: API name of the Salesforce object
        
    Returns:
        Dictionary with object details or None if not found
    """
    cmd = f"sfdx force:schema:sobject:describe -s {object_name} --json"
    result = run_sfdx_command(cmd)
    
    if not result or 'result' not in result:
        return None
        
    return result['result']

def search_objects_with_terms(search_terms, search_type="custom", use_fuzzy=False, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for objects that match the given search terms
    
    Args:
        search_terms: List of terms to search for in object names
        search_type: Type of objects to search - "custom", "standard", or "all"
        use_fuzzy: Whether to use fuzzy matching
        threshold: Similarity threshold for fuzzy matching (0-1)
        
    Returns:
        Dictionary mapping search terms to lists of matching object names
    """
    # Determine which objects to include
    include_custom = search_type in ["custom", "all"]
    include_standard = search_type in ["standard", "all"]
    
    # Get all objects
    all_objects = get_all_objects(include_custom=include_custom, include_standard=include_standard)
    
    print(f"Found {len(all_objects)} {search_type} objects")
    
    # Search each term against all objects
    results = {}
    
    for term in search_terms:
        matching_objects = []
        
        for obj_name in all_objects:
            # Check if the object name matches the search term
            if use_fuzzy:
                if fuzzy_match(term, obj_name, threshold):
                    matching_objects.append(obj_name)
            else:
                # Simple substring match
                if term.lower() in obj_name.lower():
                    matching_objects.append(obj_name)
        
        results[term] = matching_objects
        print(f"Found {len(matching_objects)} objects matching '{term}'")
    
    return results

def search_objects_multi_terms_summary(search_terms, search_type="custom", use_fuzzy=False, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for objects matching multiple terms and return which terms were found
    
    Args:
        search_terms: List of terms to search for in object names
        search_type: Type of objects to search - "custom", "standard", or "all"
        use_fuzzy: Whether to use fuzzy matching
        threshold: Similarity threshold for fuzzy matching (0-1)
        
    Returns:
        Dictionary mapping "Object_{term}" to boolean existence status
    """
    # Get detailed results
    detailed_results = search_objects_with_terms(search_terms, search_type, use_fuzzy, threshold)
    
    # Convert to simple yes/no results
    summary_results = {}
    for term, matching_objects in detailed_results.items():
        summary_results[f"Object_{term}"] = len(matching_objects) > 0
        
    return summary_results

def search_custom_objects_for_attribution(search_terms, use_fuzzy=False, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for custom objects related to attribution or other specified terms
    
    Args:
        search_terms: List of terms to search for in object names
        use_fuzzy: Whether to use fuzzy matching
        threshold: Similarity threshold for fuzzy matching (0-1)
        
    Returns:
        List of custom object names that match the search terms
    """
    # Get all custom objects
    custom_objects = get_all_objects(include_custom=True, include_standard=False)
    
    # Find custom objects related to the search terms
    matching_objects = []
    
    for obj in custom_objects:
        obj_lower = obj.lower()
        
        if use_fuzzy:
            # Check for fuzzy matches
            if any(fuzzy_match(term, obj, threshold) for term in search_terms):
                matching_objects.append(obj)
        else:
            # Check for substring matches
            if any(term.lower() in obj_lower for term in search_terms):
                matching_objects.append(obj)
    
    return matching_objects

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Search for Salesforce objects containing specific terms')
    parser.add_argument('search_term', type=str, help='Text to search for in object names (comma-separated for multiple terms)')
    parser.add_argument('--type', '-t', type=str, choices=['custom', 'standard', 'all'], default='custom',
                        help='Type of objects to search (default: custom)')
    parser.add_argument('--fuzzy', '-f', action='store_true',
                        help='Use fuzzy matching instead of substring matching')
    parser.add_argument('--threshold', '-s', type=float, default=DEFAULT_SIMILARITY_THRESHOLD,
                        help=f'Minimum similarity score for fuzzy matching (0-1, default: {DEFAULT_SIMILARITY_THRESHOLD})')
    parser.add_argument('--output', '-o', type=str, choices=['text', 'json', 'csv'], default='text',
                        help='Output format (default: text)')
    parser.add_argument('--output-file', '-of', type=str, 
                        help='File to save results to (default: output to console)')
    parser.add_argument('--details', '-d', action='store_true',
                        help='Include detailed information about matching objects')
    return parser.parse_args()

def main():
    """Main function"""
    try:
        # Parse command-line arguments
        args = parse_args()
        
        search_term = args.search_term
        search_type = args.type
        use_fuzzy = args.fuzzy
        threshold = args.threshold
        output_format = args.output
        output_file = args.output_file
        include_details = args.details
        
        # Check if search_term contains commas (multiple terms)
        if ',' in search_term:
            search_terms = [term.strip() for term in search_term.split(',')]
        else:
            search_terms = [search_term]
        
        print(f"Searching for {search_type} objects with terms: {', '.join(search_terms)}")
        print(f"Using {'fuzzy' if use_fuzzy else 'substring'} matching")
        if use_fuzzy:
            print(f"Similarity threshold: {threshold}")
        
        # Search for objects matching the terms
        results = search_objects_with_terms(search_terms, search_type, use_fuzzy, threshold)
        
        # Combine all matching objects into a single list, removing duplicates
        all_matching_objects = []
        for term, objects in results.items():
            all_matching_objects.extend(objects)
        
        # Remove duplicates
        unique_objects = sorted(list(set(all_matching_objects)))
        
        # Get detailed information if requested
        object_details = {}
        if include_details:
            print("Getting detailed information for matching objects...")
            for obj_name in unique_objects:
                details = get_object_details(obj_name)
                if details:
                    object_details[obj_name] = details
        
        # Format and output results
        if output_format == 'json':
            if include_details:
                output_data = {
                    "search_terms": search_terms,
                    "results_by_term": results,
                    "unique_objects": unique_objects,
                    "object_details": object_details
                }
            else:
                output_data = {
                    "search_terms": search_terms,
                    "results_by_term": results,
                    "unique_objects": unique_objects
                }
            
            output = json.dumps(output_data, indent=2)
        
        elif output_format == 'csv':
            import csv
            import io
            
            output_buffer = io.StringIO()
            writer = csv.writer(output_buffer)
            
            # Write header
            if include_details:
                writer.writerow(['Object', 'Custom', 'Label', 'Field Count', 'Matching Terms'])
            else:
                writer.writerow(['Object', 'Custom', 'Matching Terms'])
            
            # Write object data
            for obj_name in unique_objects:
                # Determine which terms matched this object
                matching_terms = [term for term, objects in results.items() if obj_name in objects]
                matching_terms_str = ', '.join(matching_terms)
                
                if include_details and obj_name in object_details:
                    details = object_details[obj_name]
                    writer.writerow([
                        obj_name,
                        'Yes' if obj_name.endswith('__c') else 'No',
                        details.get('label', ''),
                        len(details.get('fields', [])),
                        matching_terms_str
                    ])
                else:
                    writer.writerow([
                        obj_name,
                        'Yes' if obj_name.endswith('__c') else 'No',
                        matching_terms_str
                    ])
            
            output = output_buffer.getvalue()
        
        else:  # text format
            output = f"Found {len(unique_objects)} matching objects:\n\n"
            
            for obj_name in unique_objects:
                # Determine which terms matched this object
                matching_terms = [term for term, objects in results.items() if obj_name in objects]
                matching_terms_str = ', '.join(matching_terms)
                
                output += f"{obj_name} (Matches: {matching_terms_str})\n"
                
                if include_details and obj_name in object_details:
                    details = object_details[obj_name]
                    output += f"  Label: {details.get('label', '')}\n"
                    output += f"  Fields: {len(details.get('fields', []))}\n"
                    output += f"  Custom: {'Yes' if obj_name.endswith('__c') else 'No'}\n"
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