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

def search_reports_with_term(search_term, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for reports containing a search term
    
    Args:
        search_term: The text to search for in report names/descriptions
        threshold: Minimum similarity score for fuzzy matching (0-1)
        
    Returns:
        List of matching report dictionaries with Name, Id, and Description
    """
    # Check if SFDX is installed
    check_sfdx_installed()
    
    try:
        # Query reports using SOQL
        query = f"SELECT Id, Name, Description, FolderName FROM Report"
        cmd = f'sfdx force:data:soql:query -q "{query}" --json'
        
        result = run_sfdx_command(cmd)
        if not result or 'result' not in result:
            print("Failed to query reports")
            return []
        
        reports = result['result'].get('records', [])
        print(f"Found {len(reports)} total reports")
        
        # Filter reports using fuzzy matching
        matching_reports = []
        for report in reports:
            name_match = fuzzy_match(search_term, report.get('Name', ''), threshold)
            desc_match = fuzzy_match(search_term, report.get('Description', ''), threshold)
            folder_match = fuzzy_match(search_term, report.get('FolderName', ''), threshold)
            
            if name_match or desc_match or folder_match:
                matching_reports.append({
                    'Name': report.get('Name', ''),
                    'Id': report.get('Id', ''),
                    'Description': report.get('Description', ''),
                    'FolderName': report.get('FolderName', '')
                })
        
        return matching_reports
        
    except Exception as e:
        print(f"Error searching reports: {str(e)}")
        return []

def search_dashboards_with_term(search_term, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for dashboards containing a search term
    
    Args:
        search_term: The text to search for in dashboard titles/descriptions
        threshold: Minimum similarity score for fuzzy matching (0-1)
        
    Returns:
        List of matching dashboard dictionaries with Title, Id, and Description
    """
    # Check if SFDX is installed
    check_sfdx_installed()
    
    try:
        # Query dashboards using SOQL
        query = f"SELECT Id, Title, Description, FolderName FROM Dashboard"
        cmd = f'sfdx force:data:soql:query -q "{query}" --json'
        
        result = run_sfdx_command(cmd)
        if not result or 'result' not in result:
            print("Failed to query dashboards")
            return []
        
        dashboards = result['result'].get('records', [])
        print(f"Found {len(dashboards)} total dashboards")
        
        # Filter dashboards using fuzzy matching
        matching_dashboards = []
        for dashboard in dashboards:
            title_match = fuzzy_match(search_term, dashboard.get('Title', ''), threshold)
            desc_match = fuzzy_match(search_term, dashboard.get('Description', ''), threshold)
            folder_match = fuzzy_match(search_term, dashboard.get('FolderName', ''), threshold)
            
            if title_match or desc_match or folder_match:
                matching_dashboards.append({
                    'Title': dashboard.get('Title', ''),
                    'Id': dashboard.get('Id', ''),
                    'Description': dashboard.get('Description', ''),
                    'FolderName': dashboard.get('FolderName', '')
                })
        
        return matching_dashboards
        
    except Exception as e:
        print(f"Error searching dashboards: {str(e)}")
        return []

def search_reports_and_dashboards_multi_terms(search_terms, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for reports and dashboards containing multiple search terms
    
    Args:
        search_terms: List of terms to search for
        threshold: Minimum similarity score for fuzzy matching (0-1)
        
    Returns:
        Dictionary mapping search terms to dictionaries containing 'reports' and 'dashboards' lists
    """
    results = {}
    
    for term in search_terms:
        # Search reports and dashboards for this term
        matching_reports = search_reports_with_term(term, threshold)
        matching_dashboards = search_dashboards_with_term(term, threshold)
        
        results[term] = {
            'reports': matching_reports,
            'dashboards': matching_dashboards
        }
        
        print(f"Found {len(matching_reports)} reports and {len(matching_dashboards)} dashboards matching '{term}'")
    
    return results

def search_reports_and_dashboards_summary(search_terms, threshold=DEFAULT_SIMILARITY_THRESHOLD):
    """Search for reports and dashboards and return which terms were found
    
    Args:
        search_terms: List of terms to search for
        threshold: Minimum similarity score for fuzzy matching (0-1)
        
    Returns:
        Dictionary mapping "Report_{term}" and "Dashboard_{term}" to boolean existence status
    """
    # Get detailed results
    detailed_results = search_reports_and_dashboards_multi_terms(search_terms, threshold)
    
    # Convert to simple yes/no results
    summary_results = {}
    for term, results in detailed_results.items():
        summary_results[f"Report_{term}"] = len(results['reports']) > 0
        summary_results[f"Dashboard_{term}"] = len(results['dashboards']) > 0
    
    return summary_results

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Search for Salesforce reports and dashboards containing specific terms')
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
        
        print(f"Searching for reports and dashboards with terms: {', '.join(search_terms)}")
        print(f"Using similarity threshold: {threshold}")
        
        # Search for reports and dashboards
        results = search_reports_and_dashboards_multi_terms(search_terms, threshold)
        
        # Format and output results
        if output_format == 'json':
            output = json.dumps(results, indent=2)
        elif output_format == 'csv':
            import csv
            import io
            
            output_buffer = io.StringIO()
            writer = csv.writer(output_buffer)
            
            # Write reports
            writer.writerow(['Type', 'Term', 'Name/Title', 'Id', 'Description', 'Folder'])
            
            for term, term_results in results.items():
                # Write reports
                for report in term_results['reports']:
                    writer.writerow([
                        'Report',
                        term,
                        report.get('Name', ''),
                        report.get('Id', ''),
                        report.get('Description', ''),
                        report.get('FolderName', '')
                    ])
                
                # Write dashboards
                for dashboard in term_results['dashboards']:
                    writer.writerow([
                        'Dashboard',
                        term,
                        dashboard.get('Title', ''),
                        dashboard.get('Id', ''),
                        dashboard.get('Description', ''),
                        dashboard.get('FolderName', '')
                    ])
            
            output = output_buffer.getvalue()
        else:  # text format
            output = ""
            for term, term_results in results.items():
                output += f"\nResults for term '{term}':\n"
                output += "-" * 80 + "\n"
                
                # Reports
                output += f"\nMatching Reports ({len(term_results['reports'])}):\n"
                output += "-" * 40 + "\n"
                for report in term_results['reports']:
                    output += f"Name: {report.get('Name', '')}\n"
                    output += f"Folder: {report.get('FolderName', '')}\n"
                    if report.get('Description'):
                        output += f"Description: {report.get('Description')}\n"
                    output += f"Id: {report.get('Id', '')}\n\n"
                
                # Dashboards
                output += f"\nMatching Dashboards ({len(term_results['dashboards'])}):\n"
                output += "-" * 40 + "\n"
                for dashboard in term_results['dashboards']:
                    output += f"Title: {dashboard.get('Title', '')}\n"
                    output += f"Folder: {dashboard.get('FolderName', '')}\n"
                    if dashboard.get('Description'):
                        output += f"Description: {dashboard.get('Description')}\n"
                    output += f"Id: {dashboard.get('Id', '')}\n\n"
        
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