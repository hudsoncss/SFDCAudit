#!/usr/bin/env python3
# REQUIRES sf_field_usage_single.py to be in the same directory
# REQUIRES search_flows.py to be in the same directory
# REQUIRES search_apex.py to be in the same directory
# REQUIRES search_objects.py to be in the same directory
# REQUIRES search_fieldUsage.py to be in the same directory
# REQUIRES search_packages.py to be in the same directory
# REQUIRES search_fields.py to be in the same directory
# REQUIRES search_reports.py to be in the same directory
# REQUIRES webhook_sender.py to be in the same directory

import subprocess
import json
import sys
import requests
import os
from importlib import util

# =============================================================================
#                              GLOBAL CONSTANTS
# =============================================================================

# Attribution-related keywords used for various searches throughout the script
ATTRIBUTION_KEYWORDS = [
    'attribution',
    'touch',
    'touchpoint',
    'influence',
    'model',
    'campaign',
    'source',
    'conversion',
    'utm'
]

# Package namespaces to check for attribution solutions
ATTRIBUTION_PACKAGES = [
    'biz',
    'scaleMatters',
    'fcir',
    'pi'
]

# Standard Campaign Type values provided by Salesforce
STANDARD_CAMPAIGN_TYPES = [
    "Conference",
    "Webinar",
    "Trade Show",
    "Public Relations",
    "Partners",
    "Referral Program",
    "Advertisement",
    "Banner Ads",
    "Direct Mail",
    "Email",
    "Telemarketing",
    "Other"
]

# Standard CampaignMemberStatus values
STANDARD_MEMBER_STATUSES = [
    "sent",
    "responded"
]

# Standard objects to check for attribution-related fields
STANDARD_OBJECTS_TO_CHECK = [
    "Account", 
    "Opportunity", 
    "Lead", 
    "Contact", 
    "Campaign"
]

# =============================================================================
#                      MODULE IMPORTS AND INITIALIZATION
# =============================================================================

# Import functions from search_fieldUsage.py
try:
    # Get the path to search_fieldUsage.py in the same directory as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    field_usage_path = os.path.join(script_dir, 'search_fieldUsage.py')
    
    # Import the module using importlib
    spec = util.spec_from_file_location("search_fieldUsage", field_usage_path)
    field_usage_module = util.module_from_spec(spec)
    spec.loader.exec_module(field_usage_module)
    
    # Get the necessary functions
    get_field_usage = field_usage_module.get_field_usage
    analyze_fields = field_usage_module.analyze_fields
    check_sfdx_installed = field_usage_module.check_sfdx_installed
    HAS_FIELD_USAGE_MODULE = True
except ImportError as e:
    print(f"Warning: Could not import search_fieldUsage.py: {e}")
    print("Field usage analysis will be disabled.")
    HAS_FIELD_USAGE_MODULE = False

# Import functions from search_apex.py
try:
    # Get the path to search_apex.py in the same directory as this script
    search_apex_path = os.path.join(script_dir, 'search_apex.py')
    
    # Import the module using importlib
    spec = util.spec_from_file_location("search_apex", search_apex_path)
    search_apex_module = util.module_from_spec(spec)
    spec.loader.exec_module(search_apex_module)
    
    # Get the necessary functions
    search_apex_multi_terms_summary = search_apex_module.search_apex_multi_terms_summary
    HAS_SEARCH_APEX_MODULE = True
except ImportError as e:
    print(f"Warning: Could not import search_apex.py: {e}")
    print("Advanced Apex code search will be disabled.")
    HAS_SEARCH_APEX_MODULE = False

# Import functions from search_objects.py
try:
    # Get the path to search_objects.py in the same directory as this script
    search_objects_path = os.path.join(script_dir, 'search_objects.py')
    
    # Import the module using importlib
    spec = util.spec_from_file_location("search_objects", search_objects_path)
    search_objects_module = util.module_from_spec(spec)
    spec.loader.exec_module(search_objects_module)
    
    # Get the necessary functions
    search_custom_objects_for_attribution = search_objects_module.search_custom_objects_for_attribution
    HAS_SEARCH_OBJECTS_MODULE = True
except ImportError as e:
    print(f"Warning: Could not import search_objects.py: {e}")
    print("Advanced object search will be disabled.")
    HAS_SEARCH_OBJECTS_MODULE = False

# Import functions from search_reports.py
try:
    # Get the path to search_reports.py in the same directory as this script
    search_reports_path = os.path.join(script_dir, 'search_reports.py')
    
    # Import the module using importlib
    spec = util.spec_from_file_location("search_reports", search_reports_path)
    search_reports_module = util.module_from_spec(spec)
    spec.loader.exec_module(search_reports_module)
    
    # Get the necessary functions
    search_reports_and_dashboards_summary = search_reports_module.search_reports_and_dashboards_summary
    HAS_SEARCH_REPORTS_MODULE = True
except ImportError as e:
    print(f"Warning: Could not import search_reports.py: {e}")
    print("Advanced report and dashboard search will be disabled.")
    HAS_SEARCH_REPORTS_MODULE = False

# Import functions from search_packages.py
try:
    # Get the path to search_packages.py in the same directory as this script
    search_packages_path = os.path.join(script_dir, 'search_packages.py')
    
    # Import the module using importlib
    spec = util.spec_from_file_location("search_packages", search_packages_path)
    search_packages_module = util.module_from_spec(spec)
    spec.loader.exec_module(search_packages_module)
    
    # Get the necessary functions
    search_packages_multi_terms = search_packages_module.search_packages_multi_terms
    HAS_SEARCH_PACKAGES_MODULE = True
except ImportError as e:
    print(f"Warning: Could not import search_packages.py: {e}")
    print("Advanced package search will be disabled.")
    HAS_SEARCH_PACKAGES_MODULE = False

# Import functions from search_fields.py
try:
    # Get the path to search_fields.py in the same directory as this script
    search_fields_path = os.path.join(script_dir, 'search_fields.py')
    
    # Import the module using importlib
    spec = util.spec_from_file_location("search_fields", search_fields_path)
    search_fields_module = util.module_from_spec(spec)
    spec.loader.exec_module(search_fields_module)
    
    # Get the necessary functions
    search_fields_multi_terms = search_fields_module.search_fields_multi_terms
    HAS_SEARCH_FIELDS_MODULE = True
except ImportError as e:
    print(f"Warning: Could not import search_fields.py: {e}")
    print("Advanced field search will be disabled.")
    HAS_SEARCH_FIELDS_MODULE = False

# Try to import webhook_sender
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    webhook_path = os.path.join(script_dir, 'webhook_sender.py')
    spec = util.spec_from_file_location("webhook_sender", webhook_path)
    webhook_module = util.module_from_spec(spec)
    spec.loader.exec_module(webhook_module)
    HAS_WEBHOOK_MODULE = True
except ImportError as e:
    print(f"Warning: Could not import webhook_sender.py: {e}")
    print("Webhook integration will be disabled.")
    HAS_WEBHOOK_MODULE = False


def run_sfdx(cmd):
    """Execute an SFDX command and return the parsed JSON response.
    
    Args:
        cmd: List of command parts to execute
        
    Returns:
        Parsed JSON response as dictionary or None if error
    """
    try:
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
            print(f"Command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
            print(f"Output (first 1000 chars): {result.stdout[:1000]}")
            return None
    except Exception as e:
        print(f"Error executing command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        print(f"Exception: {str(e)}")
        return None


def check_sfdx_installed():
    """Check if SFDX is installed and in the PATH."""
    try:
        cmd = ["sfdx", "--version"]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)
        
        if result.returncode != 0:
            print("SFDX CLI not found. Please install SFDX CLI and ensure it's in your PATH.")
            print("Visit https://developer.salesforce.com/tools/sfdxcli for installation instructions.")
            sys.exit(1)
        print(f"Using SFDX CLI: {result.stdout.strip()}")
    except Exception as e:
        print(f"Error checking SFDX installation: {str(e)}")
        print("Please ensure SFDX CLI is installed and in your PATH.")
        sys.exit(1)


def check_object_exists(object_name):
    """Check if an object exists in the org
    
    Args:
        object_name: Name of the object to check
        
    Returns:
        Boolean indicating if the object exists
    """
    cmd = [
        "sfdx",
        "force:schema:sobject:list",
        "--json"
    ]
    
    result = run_sfdx(cmd)
    if not result:
        return False
    
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
    
    return object_name in sobjects


def check_campaign_influence_enabled():
    """Check if Campaign Influence is enabled in the org by directly querying CampaignInfluenceModel
    
    Returns:
        True if Campaign Influence is enabled, False otherwise
    """
    print("Checking Campaign Influence settings...")
    
    # Get org auth details first
    auth_cmd = "sfdx force:org:display --json"
    auth_result = run_sfdx(auth_cmd)
    
    if not auth_result or 'result' not in auth_result:
        print("Could not get org authentication details")
        return False
    
    # Extract instance URL and access token
    instance_url = auth_result['result'].get('instanceUrl')
    access_token = auth_result['result'].get('accessToken')
    
    if not instance_url or not access_token:
        print("Missing instanceUrl or accessToken in auth response")
        return False
    
    # Use REST API to directly check for CampaignInfluenceModel
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
            # CampaignInfluenceModel exists, which means Campaign Influence is enabled
            print("Campaign Influence is enabled - CampaignInfluenceModel object exists")
            return True
        else:
            print(f"CampaignInfluenceModel object does not exist or is not accessible: {model_response.status_code}")
            return False
    except Exception as e:
        print(f"Error checking Campaign Influence settings: {str(e)}")
        return False


def check_installed_packages(namespaces):
    """Check which attribution-related packages are installed.
    
    Args:
        namespaces: List of package namespaces to check
        
    Returns:
        Dictionary mapping namespace to installation status
    """
    print("Checking for attribution-related packages...")
    
    if not HAS_SEARCH_PACKAGES_MODULE:
        print("Advanced package search is not available - search_packages.py module not loaded")
        # Return all packages as not found if module isn't available
        return {namespace: False for namespace in namespaces}
    
    try:
        # Use the search_packages_multi_terms function from the imported module
        results = search_packages_multi_terms(namespaces)
        return results
        
    except Exception as e:
        print(f"Error using search_packages.py: {str(e)}")
        # Return all packages as not found on error
        return {namespace: False for namespace in namespaces}


def check_custom_schema(keywords):
    """Check for attribution-related fields in standard objects.
    
    Args:
        keywords: List of keywords to look for in field names
        
    Returns:
        Dictionary mapping object names to lists of matching field names
    """
    print("\nChecking for attribution-related fields in standard objects...")
    
    if not HAS_SEARCH_FIELDS_MODULE:
        print("Advanced field search is not available - search_fields.py module not loaded")
        return {obj: [] for obj in STANDARD_OBJECTS_TO_CHECK}
    
    try:
        # Use the search_fields_multi_terms function from the imported module
        results = search_fields_multi_terms(
            objects=STANDARD_OBJECTS_TO_CHECK,
            search_terms=keywords
        )
        
        # Convert the results to match the expected format
        formatted_results = {}
        for obj in STANDARD_OBJECTS_TO_CHECK:
            matching_fields = set()
            # Check each search term's results for this object
            for term_results in results.values():
                if obj in term_results:
                    # Add the field names to our set
                    matching_fields.update(
                        field['name'] for field in term_results[obj]
                    )
            formatted_results[obj] = sorted(list(matching_fields))
            
            # Print summary for this object
            if matching_fields:
                print(f"Found {len(matching_fields)} matching fields in {obj}")
            else:
                print(f"No matching fields found in {obj}")
        
        return formatted_results
        
    except Exception as e:
        print(f"Error using search_fields.py: {str(e)}")
        print("Falling back to simple field search...")
        return check_custom_schema_fallback(keywords)


def check_custom_schema_fallback(keywords):
    """Fallback method to check for attribution-related fields in standard objects.
    
    Args:
        keywords: List of keywords to look for in field names
        
    Returns:
        Dictionary mapping object names to lists of matching field names
    """
    results = {}
    
    for obj in STANDARD_OBJECTS_TO_CHECK:
        cmd = [
            "sfdx",
            "force:schema:sobject:describe",
            "-s", obj,
            "--json"
        ]
        
        result = run_sfdx(cmd)
        if not result:
            results[obj] = []
            continue
        
        matching_fields = []
        for field in result["result"]["fields"]:
            field_name = field["name"].lower()
            if any(kw.lower() in field_name for kw in keywords):
                matching_fields.append(field["name"])
        
        results[obj] = matching_fields
    
    return results


def analyze_field_usage_for_objects(custom_schema):
    """Analyze the usage percentages for fields in the custom schema
    
    Args:
        custom_schema: Dictionary mapping object names to lists of field names
        
    Returns:
        Dictionary mapping object names to dictionaries of field usage data
    """
    if not HAS_FIELD_USAGE_MODULE:
        print("Field usage analysis is not available - search_fieldUsage.py module not loaded")
        return None
    
    results = {}
    
    for object_name, fields in custom_schema.items():
        if not fields:  # Skip if no fields found for this object
            continue
            
        print(f"\nAnalyzing field usage for {len(fields)} fields in {object_name}...")
        
        # Only analyze fields if there are any to analyze
        if fields:
            # Use batch processing via the analyze_fields function, which will use the batch method if pandas is available
            try:
                # Try to use the batch processing from the imported module - use full dataset for accuracy
                fields_data = field_usage_module.analyze_fields(object_name, fields, use_full_dataset=True)
                
                if fields_data:
                    # Sort fields by usage percentage (highest first)
                    fields_data = sorted(fields_data, key=lambda x: x.get('usage_pct', 0), reverse=True)
                    results[object_name] = fields_data
            except Exception as e:
                print(f"Error analyzing fields for {object_name}: {str(e)}")
                print("Falling back to individual field processing...")
                
                # Fallback to individual processing if batch processing fails
                fields_data = []
                
                # Get total record count once for efficiency
                try:
                    total_records = field_usage_module.get_total_record_count(object_name)
                    print(f"Total {object_name} records: {total_records}")
                    
                    if total_records == 0:
                        print(f"Skipping {object_name} - no records found")
                        continue
                except Exception as e:
                    print(f"Error getting record count for {object_name}: {str(e)}")
                    print(f"Skipping {object_name}")
                    continue
                
                # Process each field individually to prevent one error from stopping all fields
                for field_name in fields:
                    print(f"Analyzing field: {field_name}")
                    try:
                        field_result = field_usage_module.get_field_usage(object_name, field_name, total_records)
                        if field_result:
                            fields_data.append(field_result)
                    except Exception as e:
                        print(f"Error analyzing field {field_name} on {object_name}: {str(e)}")
                        print("Continuing with next field...")
                
                if fields_data:
                    # Sort fields by usage percentage (highest first)
                    fields_data = sorted(fields_data, key=lambda x: x.get('usage_pct', 0), reverse=True)
                    results[object_name] = fields_data
    
    return results


def search_custom_objects_for_attribution_fallback():
    """Fallback method to search for custom objects related to attribution
    when search_objects.py is not available
    
    Returns:
        List of custom object names that might be related to attribution
    """
    # Use the global keywords list instead of a local one
    attribution_keywords = ATTRIBUTION_KEYWORDS
    
    cmd = [
        "sfdx",
        "force:schema:sobject:list",
        "--json"
    ]
    
    result = run_sfdx(cmd)
    if not result:
        return []
    
    # The format of the result might vary - handle both formats
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
    
    # Filter for custom objects (ending with __c)
    custom_objects = [obj for obj in sobjects if isinstance(obj, str) and obj.endswith("__c")]
    
    # Find custom objects related to attribution
    attribution_objects = []
    for obj in custom_objects:
        obj_lower = obj.lower()
        if any(keyword in obj_lower for keyword in attribution_keywords):
            attribution_objects.append(obj)
    
    return attribution_objects


def check_reports_dashboards(keywords):
    """Check for attribution-related reports and dashboards.
    
    Args:
        keywords: List of keywords to search for in reports and dashboards
        
    Returns:
        Dictionary mapping "Report_{keyword}" and "Dashboard_{keyword}" to existence status
    """
    print("Checking for attribution-related reports and dashboards...")
    
    if not HAS_SEARCH_REPORTS_MODULE:
        print("Advanced report and dashboard search is not available - search_reports.py module not loaded")
        # Return empty results if module not available
        return {f"Report_{kw}": False for kw in keywords} | {f"Dashboard_{kw}": False for kw in keywords}
    
    try:
        # Use the search_reports_and_dashboards_summary function from the imported module
        results = search_reports_module.search_reports_and_dashboards_summary(keywords)
        return results
        
    except Exception as e:
        print(f"Error using search_reports.py: {str(e)}")
        # Return empty results on error
        return {f"Report_{kw}": False for kw in keywords} | {f"Dashboard_{kw}": False for kw in keywords}


def check_apex_references(keywords):
    """Check for attribution-related references in Apex code using search_apex.py.
    
    Args:
        keywords: List of keywords to search for in Apex classes and triggers
        
    Returns:
        Dictionary mapping "Apex_{keyword}" to existence status
    """
    print("Checking for attribution-related Apex code using search_apex.py...")
    
    if not HAS_SEARCH_APEX_MODULE:
        print("Advanced Apex search is not available - search_apex.py module not loaded")
        # Fall back to simpler approach without detailed searching
        return {f"Apex_{kw}": False for kw in keywords}
    
    try:
        # Create comma-separated list of keywords for display purposes
        keywords_str = ", ".join(keywords)
        print(f"Searching for Apex code with keywords: {keywords_str}")
        
        # Use the search_apex_multi_terms_summary function from the imported module
        # This function returns a dict mapping "Apex_{term}" to boolean values
        results = search_apex_module.search_apex_multi_terms_summary(keywords)
        
        # The results already have the right format for MTAAudit.py
        return results
        
    except Exception as e:
        print(f"Error using search_apex.py: {str(e)}")
        print("Falling back to simpler Apex search method...")
        return check_apex_references_fallback(keywords)


def check_apex_references_fallback(keywords):
    """Fallback method to check for attribution-related references in Apex code.
    
    Args:
        keywords: List of keywords to search for in Apex code
        
    Returns:
        Dictionary mapping "Apex_{keyword}" to existence status
    """
    # Simple fallback implementation
    print("Using fallback approach for Apex searching...")
    
    results = {}
    
    for kw in keywords:
        # Check Apex classes by name (since Body can't be filtered)
        class_query = f"SELECT Id FROM ApexClass WHERE Name LIKE '%{kw}%' LIMIT 1"
        class_cmd = [
            "sfdx",
            "force:data:soql:query",
            "-q", class_query,
            "-r", "json"
        ]
        
        class_result = run_sfdx(class_cmd)
        class_found = class_result and class_result["result"]["totalSize"] > 0
        
        # Check Apex triggers by name
        trigger_query = f"SELECT Id FROM ApexTrigger WHERE Name LIKE '%{kw}%' LIMIT 1"
        trigger_cmd = [
            "sfdx",
            "force:data:soql:query",
            "-q", trigger_query,
            "-r", "json"
        ]
        
        trigger_result = run_sfdx(trigger_cmd)
        trigger_found = trigger_result and trigger_result["result"]["totalSize"] > 0
        
        # Combine the results
        results[f"Apex_{kw}"] = class_found or trigger_found
    
    return results


def check_flow_references(keywords):
    """Check for attribution-related references in Flow automations using search_flows.py.
    
    Args:
        keywords: List of keywords to search for in Flow definitions
        
    Returns:
        Dictionary mapping "Flow_{keyword}" to existence status
    """
    results = {}
    for kw in keywords:
        results[f"Flow_{kw}"] = False
    
    print("Checking flows using search_flows.py...")
    
    try:
        # Get the directory where the current script (MTAAudit.py) is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        search_flows_path = os.path.join(script_dir, 'search_flows.py')
        
        if not os.path.exists(search_flows_path):
            print(f"search_flows.py not found at {search_flows_path}")
            print("Falling back to simpler flow search method...")
            return check_flow_references_fallback(keywords)
        
        # Create comma-separated list of keywords
        keywords_str = ", ".join(keywords)
        print(f"Searching for flows with keywords: {keywords_str}")
        
        # Run search_flows.py as a subprocess from the same directory
        try:
            # Use sys.executable to get the current Python interpreter path
            # This ensures we use the same Python environment as the current script
            python_executable = sys.executable
            
            # Run the search_flows.py script using the full path
            cmd = f'"{python_executable}" "{search_flows_path}" "{keywords_str}"'
            
            # Print the command for debugging
            print(f"Running command: {cmd}")
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            # Check if the command was successful
            if result.returncode != 0:
                print(f"Error running search_flows.py: {result.stderr}")
                print("Falling back to simpler flow search method...")
                return check_flow_references_fallback(keywords)
            
            # Parse the output to determine which keywords had matches
            output = result.stdout
            print("Search results:")
            print(output)
            
            # Check which keywords had matches
            for kw in keywords:
                # Look for lines like "Found X flows matching 'Keyword'"
                match_line = f"Found 0 flows matching '{kw}'"
                if match_line not in output:
                    # If we don't see "Found 0 flows", then matches were found
                    results[f"Flow_{kw}"] = True
                else:
                    results[f"Flow_{kw}"] = False
            
            return results
            
        except Exception as e:
            print(f"Error running search_flows.py: {str(e)}")
            print("Falling back to simpler flow search method...")
            return check_flow_references_fallback(keywords)
        
    except Exception as e:
        print(f"Error using search_flows.py: {str(e)}")
        print("Falling back to simpler flow search method...")
        return check_flow_references_fallback(keywords)


def check_flow_references_fallback(keywords):
    """Fallback method to check for attribution-related references in Flow automations.
    
    Args:
        keywords: List of keywords to search for in Flow definitions
        
    Returns:
        Dictionary mapping "Flow_{keyword}" to existence status
    """
    results = {}
    for kw in keywords:
        results[f"Flow_{kw}"] = False
    
    print("Using fallback approach for flow searching...")
    
    try:
        # Try the simplest possible approach - just get all flow names
        # This avoids all API/query complexity
        flow_cmd = "sfdx force:schema:sobject:list --json"
        
        result = run_sfdx(flow_cmd)
        if not result or 'result' not in result:
            print("Could not retrieve object list")
            return results
        
        # First, check if Flow object is available in this org
        flow_object_exists = False
        sobjects = result['result']
        
        # Handle different result formats
        object_names = []
        if isinstance(sobjects, list):
            for obj in sobjects:
                if isinstance(obj, dict) and 'name' in obj:
                    object_names.append(obj['name'])
                elif isinstance(obj, str):
                    object_names.append(obj)
        elif isinstance(sobjects, dict) and 'sobjects' in sobjects:
            object_names = [obj.get('name', '') for obj in sobjects['sobjects']]
        
        # Check if Flow object exists
        flow_object_exists = 'Flow' in object_names
        
        if not flow_object_exists:
            print("Flow object not found in this org's schema")
            return results
        
        # Just get a list of all flows with a simple describe command
        # This avoids complex SOQL queries that might fail
        print("Getting Flow metadata...")
        
        # Use schema:sobject:describe which is more reliable than direct SOQL
        describe_cmd = [
            "sfdx",
            "force:schema:sobject:describe",
            "-s", "Flow",
            "--json"
        ]
        
        describe_result = run_sfdx(describe_cmd)
        if not describe_result or 'result' not in describe_result:
            print("Could not describe Flow object")
            return results
        
        # Check if the Flow object has a DeveloperName field
        flow_fields = describe_result['result']['fields']
        has_developer_name = any(field['name'] == 'DeveloperName' for field in flow_fields)
        
        if not has_developer_name:
            print("Flow object does not have a DeveloperName field")
            return results
        
        # Now try a very simple query with no filters
        print("Querying Flow names...")
        simple_cmd = [
            "sfdx",
            "force:data:soql:query",
            "-q", "SELECT DeveloperName FROM Flow",
            "--json"
        ]
        
        simple_result = run_sfdx(simple_cmd)
        if not simple_result or 'result' not in simple_result:
            print("Could not query Flow object")
            return results
        
        # Get flow names
        flow_records = simple_result['result'].get('records', [])
        flow_names = [record.get('DeveloperName', '') for record in flow_records if 'DeveloperName' in record]
        
        print(f"Found {len(flow_names)} flows")
        
        # Check each keyword against all flow names
        for kw in keywords:
            kw_lower = kw.lower()
            found = any(kw_lower in name.lower() for name in flow_names if name)
            results[f"Flow_{kw}"] = found
            
    except Exception as e:
        print(f"Error checking flows: {str(e)}")
        print("Trying a backup approach...")
        
        # Backup approach - check for FlowDefinition object
        try:
            # First check if FlowDefinition exists
            list_cmd = [
                "sfdx",
                "force:schema:sobject:list",
                "--json"
            ]
            
            list_result = run_sfdx(list_cmd)
            if not list_result or 'result' not in list_result:
                print("Could not retrieve object list")
                return results
            
            # Parse the object list
            sobjects = list_result['result']
            object_names = []
            
            if isinstance(sobjects, list):
                for obj in sobjects:
                    if isinstance(obj, dict) and 'name' in obj:
                        object_names.append(obj['name'])
                    elif isinstance(obj, str):
                        object_names.append(obj)
            elif isinstance(sobjects, dict) and 'sobjects' in sobjects:
                object_names = [obj.get('name', '') for obj in sobjects['sobjects']]
            
            # Look for any object that might relate to flows
            flow_related_objects = [name for name in object_names if 'flow' in name.lower()]
            
            if flow_related_objects:
                print(f"Found these flow-related objects: {', '.join(flow_related_objects)}")
                # Just return that we found some flow-related objects
                for kw in keywords:
                    results[f"Flow_{kw}"] = True
            else:
                print("No flow-related objects found")
        except Exception as e2:
            print(f"Backup approach also failed: {str(e2)}")
    
    return results


def check_campaign_member_statuses():
    """Check for custom CampaignMemberStatus values beyond standard ones
    
    Returns:
        Dictionary with information about custom campaign member statuses
    """
    print("Checking for custom CampaignMemberStatus values...")
    
    # Use standard statuses from constants
    standard_statuses = STANDARD_MEMBER_STATUSES
    
    # Query CampaignMemberStatus to get all status values
    query = "SELECT Id, Label, CampaignId FROM CampaignMemberStatus"
    cmd = f'sfdx force:data:soql:query -q "{query}" --json'
    
    result = run_sfdx(cmd)
    if not result or 'result' not in result:
        print("Could not query CampaignMemberStatus object")
        return {
            "has_custom_statuses": False,
            "custom_statuses": [],
            "error": "Failed to query CampaignMemberStatus"
        }
    
    # Collect all status labels
    records = result['result'].get('records', [])
    if not records:
        print("No CampaignMemberStatus records found")
        return {
            "has_custom_statuses": False,
            "custom_statuses": [],
            "total_status_count": 0
        }
    
    # Count all statuses and find custom ones
    all_statuses = set()
    custom_statuses = set()
    
    for record in records:
        label = record.get('Label', '')
        if label:
            label_lower = label.lower()
            all_statuses.add(label)
            
            # If the label is not a standard status, it's custom
            if all(std_status not in label_lower for std_status in standard_statuses):
                custom_statuses.add(label)
    
    # Convert sets to sorted lists for consistent output
    all_statuses_list = sorted(list(all_statuses))
    custom_statuses_list = sorted(list(custom_statuses))
    
    print(f"Found {len(all_statuses_list)} total campaign member statuses")
    print(f"Found {len(custom_statuses_list)} custom campaign member statuses")
    
    if custom_statuses_list:
        print("Custom statuses found:")
        for status in custom_statuses_list:
            print(f"  - {status}")
    
    return {
        "has_custom_statuses": len(custom_statuses_list) > 0,
        "custom_statuses": custom_statuses_list,
        "all_statuses": all_statuses_list,
        "total_status_count": len(all_statuses_list)
    }


def check_campaign_type_values():
    """Check for custom values in the Campaign Type field
    
    Returns:
        Dictionary with information about custom Campaign Type values
    """
    print("Checking for custom Campaign Type values...")
    
    # Use standard types from constants
    standard_types = STANDARD_CAMPAIGN_TYPES
    
    # Query field metadata using Tooling API
    # Get org auth details first
    auth_cmd = "sfdx force:org:display --json"
    auth_result = run_sfdx(auth_cmd)
    
    if not auth_result or 'result' not in auth_result:
        print("Could not get org authentication details")
        return {
            "has_custom_types": False,
            "custom_types": [],
            "error": "Failed to authenticate"
        }
    
    # Extract instance URL and access token
    instance_url = auth_result['result'].get('instanceUrl')
    access_token = auth_result['result'].get('accessToken')
    
    if not instance_url or not access_token:
        print("Missing instanceUrl or accessToken in auth response")
        return {
            "has_custom_types": False,
            "custom_types": [],
            "error": "Missing authentication details"
        }
    
    # Use REST API to get field metadata
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # First get the describe for Campaign object
        url = f"{instance_url}/services/data/v53.0/sobjects/Campaign/describe"
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"Error getting Campaign metadata: {response.status_code}")
            return {
                "has_custom_types": False,
                "custom_types": [],
                "error": f"API Error: {response.status_code}"
            }
        
        # Parse the response to get Type field metadata
        campaign_metadata = response.json()
        type_field = None
        
        for field in campaign_metadata.get('fields', []):
            if field.get('name') == 'Type':
                type_field = field
                break
        
        if not type_field:
            print("Could not find Type field in Campaign metadata")
            return {
                "has_custom_types": False,
                "custom_types": [],
                "error": "Type field not found"
            }
        
        # Get picklist values
        picklist_values = []
        custom_types = []
        
        for value in type_field.get('picklistValues', []):
            label = value.get('label')
            if label:
                picklist_values.append(label)
                # Check if this is a custom value
                if label not in standard_types:
                    custom_types.append(label)
        
        # Return results
        has_custom_types = len(custom_types) > 0
        
        if has_custom_types:
            print(f"Found {len(custom_types)} custom Campaign Type values:")
            for custom_type in custom_types:
                print(f"  - {custom_type}")
        else:
            print("No custom Campaign Type values found")
        
        return {
            "has_custom_types": has_custom_types,
            "custom_types": custom_types,
            "all_types": picklist_values
        }
        
    except Exception as e:
        print(f"Error checking Campaign Type values: {str(e)}")
        
        # Fallback to SFDX describe if REST API fails
        try:
            print("Attempting fallback method using SFDX...")
            cmd = "sfdx force:schema:sobject:describe -s Campaign --json"
            result = run_sfdx(cmd)
            
            if not result or 'result' not in result:
                print("Could not get Campaign metadata")
                return {
                    "has_custom_types": False,
                    "custom_types": [],
                    "error": "Failed to get metadata"
                }
            
            # Find Type field in the response
            type_field = None
            for field in result['result'].get('fields', []):
                if field.get('name') == 'Type':
                    type_field = field
                    break
            
            if not type_field:
                print("Could not find Type field in Campaign metadata")
                return {
                    "has_custom_types": False,
                    "custom_types": [],
                    "error": "Type field not found"
                }
            
            # Get picklist values
            picklist_values = []
            custom_types = []
            
            for value in type_field.get('picklistValues', []):
                label = value.get('label')
                if label:
                    picklist_values.append(label)
                    # Check if this is a custom value
                    if label not in standard_types:
                        custom_types.append(label)
            
            # Return results
            has_custom_types = len(custom_types) > 0
            
            if has_custom_types:
                print(f"Found {len(custom_types)} custom Campaign Type values:")
                for custom_type in custom_types:
                    print(f"  - {custom_type}")
            else:
                print("No custom Campaign Type values found")
            
            return {
                "has_custom_types": has_custom_types,
                "custom_types": custom_types,
                "all_types": picklist_values
            }
            
        except Exception as e2:
            print(f"Fallback method also failed: {str(e2)}")
            return {
                "has_custom_types": False,
                "custom_types": [],
                "error": f"Both methods failed: {str(e)}, {str(e2)}"
            }


def get_company_name():
    """Get the company name from Salesforce org
    
    Returns:
        A clean version of the company name suitable for filenames
    """
    print("Getting company name for output file...")
    
    # Try to query Organization object first
    query = "SELECT Name FROM Organization LIMIT 1"
    cmd = f'sfdx force:data:soql:query -q "{query}" --json'
    
    result = run_sfdx(cmd)
    if result and 'result' in result and 'records' in result['result'] and len(result['result']['records']) > 0:
        company_name = result['result']['records'][0].get('Name')
        if company_name:
            return clean_filename(company_name)
    
    # If that fails, try getting it from the org display
    cmd = "sfdx force:org:display --json"
    result = run_sfdx(cmd)
    
    if result and 'result' in result:
        # Try to extract company name from org display
        org_name = result['result'].get('name')
        username = result['result'].get('username')
        
        if org_name and not org_name.startswith('00D'):  # Avoid org IDs
            return clean_filename(org_name)
        elif username:
            # Extract domain from username as fallback
            domain = username.split('@')[1].split('.')[0]
            return clean_filename(domain)
    
    # Default name if we couldn't get the company name
    print("Could not determine company name, using 'salesforce_org'")
    return "salesforce_org"

def clean_filename(name):
    """Clean a string to be used in a filename"""
    # Replace spaces and special characters with underscores
    import re
    cleaned = re.sub(r'[^\w\s-]', '', name)
    cleaned = re.sub(r'[\s-]+', '_', cleaned)
    return cleaned.lower()

def main():
    """Run all audit checks and output results as JSON file."""
    # Check if SFDX is installed
    check_sfdx_installed()
    
    # Use constants for various keyword lists
    package_namespaces = ATTRIBUTION_PACKAGES
    schema_keywords = [kw.title() for kw in ATTRIBUTION_KEYWORDS]  # Title case for schema search
    report_keywords = ['Attribution', 'Touch', 'Influence']
    code_keywords = ['CampaignInfluence', 'Attribution', 'Touchpoint']
    flow_keywords = ['CampaignInfluence', 'Attribution', 'Touch', 'Influence', 'Credit']
    
    # Get company name for output file
    company_name = get_company_name()
    
    # Initialize audit results with company name and purpose
    audit_results = {
        'company_name': company_name,
        'purpose': 'Attribution Audit',
        'campaign_influence_enabled': False,
        'installed_packages': {namespace: False for namespace in package_namespaces},
        'custom_schema_matches': {},
        'attribution_custom_objects': [],
        'report_dashboard_usage': {},
        'apex_references': {},
        'flow_references': {},
        'campaign_member_statuses': {},
        'campaign_type_values': {}
    }
    
    field_usage_data = None
    
    # Collect audit results with error handling for each section
    try:
        # Find custom objects that might be related to attribution
        print("\nSearching for attribution-related custom objects...")
        try:
            if HAS_SEARCH_OBJECTS_MODULE:
                print("Using search_objects.py module for advanced object search...")
                attribution_custom_objects = search_custom_objects_for_attribution(ATTRIBUTION_KEYWORDS)
            else:
                print("Using fallback method for object search...")
                attribution_custom_objects = search_custom_objects_for_attribution_fallback()
                
            audit_results['attribution_custom_objects'] = attribution_custom_objects
        except Exception as e:
            print(f"Error searching for custom objects: {str(e)}")
        
        # Check for Campaign Influence
        print("\nChecking Campaign Influence configuration...")
        try:
            audit_results['campaign_influence_enabled'] = check_campaign_influence_enabled()
        except Exception as e:
            print(f"Error checking Campaign Influence: {str(e)}")
        
        # Check installed packages
        print("\nChecking for attribution-related packages...")
        try:
            audit_results['installed_packages'] = check_installed_packages(package_namespaces)
        except Exception as e:
            print(f"Error checking installed packages: {str(e)}")
        
        # Check for attribution-related fields in standard objects
        print("\nChecking for attribution-related fields in standard objects...")
        try:
            custom_schema_matches = check_custom_schema(schema_keywords)
            audit_results['custom_schema_matches'] = custom_schema_matches
        except Exception as e:
            print(f"Error checking custom schema: {str(e)}")
            custom_schema_matches = {}
        
        # Check reports and dashboards
        print("\nChecking for attribution-related reports and dashboards...")
        try:
            audit_results['report_dashboard_usage'] = check_reports_dashboards(report_keywords)
        except Exception as e:
            print(f"Error checking reports and dashboards: {str(e)}")
        
        # Check Apex references using search_apex.py module
        print("\nChecking for attribution-related Apex code...")
        try:
            audit_results['apex_references'] = check_apex_references(code_keywords)
        except Exception as e:
            print(f"Error checking Apex references: {str(e)}")
        
        # Check Flow references
        print("\nChecking for attribution-related Flows...")
        try:
            audit_results['flow_references'] = check_flow_references(flow_keywords)
        except Exception as e:
            print(f"Error checking Flow references: {str(e)}")
        
        # Check campaign member statuses
        print("\nChecking campaign member statuses...")
        try:
            audit_results['campaign_member_statuses'] = check_campaign_member_statuses()
        except Exception as e:
            print(f"Error checking campaign member statuses: {str(e)}")
        
        # Check campaign type values
        print("\nChecking campaign type values...")
        try:
            audit_results['campaign_type_values'] = check_campaign_type_values()
        except Exception as e:
            print(f"Error checking campaign type values: {str(e)}")
        
        # Analyze field usage for attribution fields found
        if HAS_FIELD_USAGE_MODULE and custom_schema_matches:
            print("\nAnalyzing field usage for attribution-related fields...")
            try:
                field_usage_data = analyze_field_usage_for_objects(custom_schema_matches)
                if field_usage_data:
                    audit_results['field_usage_data'] = field_usage_data
            except Exception as e:
                print(f"Error analyzing field usage: {str(e)}")
                print("Field usage analysis is not available - search_fieldUsage.py module not loaded")
        
        # Get company name for output file
        company_name = get_company_name()
        output_filename = f"{company_name}_attribution_audit.json"
        
        # Save results to JSON file instead of printing to terminal
        with open(output_filename, 'w') as json_file:
            json.dump(audit_results, json_file, indent=2)
        
        print(f"\n===== AUDIT RESULTS SAVED =====")
        print(f"Results saved to: {output_filename}")
        
        # Call openai_sender.py to analyze the results
        try:
            print("\n===== SENDING TO OPENAI FOR ANALYSIS =====")
            import subprocess
            script_dir = os.path.dirname(os.path.abspath(__file__))
            openai_sender_path = os.path.join(script_dir, 'openai_sender.py')
            
            # Run openai_sender.py with the output file
            result = subprocess.run(
                [sys.executable, openai_sender_path, output_filename],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("Successfully sent results to OpenAI for analysis")
                print(result.stdout)
            else:
                print("Error sending results to OpenAI:")
                print(result.stderr)
        except Exception as e:
            print(f"Error calling openai_sender.py: {str(e)}")
        
    except Exception as e:
        print(f"Error performing audit: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main() 