#!/usr/bin/env python3

import json
import subprocess
import sys
import argparse

# Try to import pandas - we'll use it for efficient data processing if available
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    print("Warning: pandas not found. Will use fallback method for field analysis.")
    print("For better performance, install pandas: pip install pandas")

# Default configuration - change these or use command-line arguments
DEFAULT_OBJECT = "Account"
DEFAULT_FIELDS = ["Name", "Industry", "AnnualRevenue"]
DEFAULT_BATCH_SIZE = 5000

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

def get_total_record_count(object_name):
    """Get total record count for an object"""
    try:
        query = f"SELECT count() FROM {object_name}"
        cmd = f'sfdx force:data:soql:query -q "{query}" --json'
        result = run_sfdx_command(cmd)
        
        if result and 'result' in result:
            return result['result']['totalSize']
        else:
            print(f"Error querying total record count for {object_name}")
            return 0
    except Exception as e:
        print(f"Error querying total record count: {e}")
        print(f"Continuing with total_record_count = 0")
        return 0

def validate_fields_on_object(object_name, field_names):
    """Check if fields exist on the object and get their types
    
    Args:
        object_name: The name of the Salesforce object
        field_names: List of field names to check
        
    Returns:
        Dictionary mapping valid field names to their types
    """
    # Get object metadata
    field_cmd = f'sfdx force:schema:sobject:describe -s {object_name} --json'
    field_result = run_sfdx_command(field_cmd)
    
    if not field_result or 'result' not in field_result:
        print(f"Error: Could not retrieve metadata for {object_name}")
        return {}
    
    # Check each field
    valid_fields = {}
    for field_name in field_names:
        field_exists = False
        field_type = None
        
        for field in field_result['result']['fields']:
            if field['name'].lower() == field_name.lower():
                field_exists = True
                field_type = field['type'].lower()
                valid_fields[field['name']] = field_type  # Use actual field name with correct case
                break
        
        if not field_exists:
            print(f"Warning: Field '{field_name}' does not exist on {object_name}")
    
    return valid_fields

def get_field_usage_batch(object_name, field_names, total_record_count=None, batch_size=DEFAULT_BATCH_SIZE, use_full_dataset=False):
    """Check usage percentage for multiple fields at once using dataframes
    
    Args:
        object_name: Name of the Salesforce object to check
        field_names: List of field names to check usage for, or comma-separated string
        total_record_count: Total record count (if already known)
        batch_size: Maximum number of records to query in a batch
        use_full_dataset: If True, analyze the full dataset even if large (may take longer)
        
    Returns:
        List of dictionaries with usage statistics
    """
    # Convert string input to list if needed
    if isinstance(field_names, str):
        field_names = [field.strip() for field in field_names.split(',')]
        print(f"Converted string input to list of {len(field_names)} fields: {field_names}")
    
    if not HAS_PANDAS:
        print("Warning: pandas not available, falling back to individual field analysis")
        return [get_field_usage(object_name, field, total_record_count) for field in field_names]
    
    # Get total record count if not provided
    if total_record_count is None:
        total_record_count = get_total_record_count(object_name)
        print(f"Total {object_name} records: {total_record_count}")
    
    # If there are no records, return 0% for all fields
    if total_record_count == 0:
        return [
            {
                "object": object_name,
                "field": field_name,
                "total_records": 0,
                "non_null_records": 0,
                "usage_pct": 0.0
            }
            for field_name in field_names
        ]
    
    # Validate fields and get their types
    valid_fields = validate_fields_on_object(object_name, field_names)
    if not valid_fields:
        print(f"No valid fields found for {object_name}")
        return []
    
    # Determine if we need to use sampling or full dataset
    # For very large datasets, force sampling to avoid API limitations
    very_large_dataset = total_record_count > 50000
    if very_large_dataset and use_full_dataset:
        print(f"Warning: Dataset is very large ({total_record_count} records). Using sampling instead of full analysis.")
        use_full_dataset = False
    
    use_sampling = (not use_full_dataset) and (total_record_count > batch_size)
    
    # Build query with valid fields
    field_list = ", ".join(valid_fields.keys())
    
    # For larger datasets and when full analysis is needed, try different pagination approaches
    if not use_sampling and total_record_count > batch_size:
        print(f"Analyzing full dataset of {total_record_count} records using pagination...")
        
        # Try both cursor-based and small batches to handle API limitations
        try:
            return process_with_cursor_pagination(object_name, valid_fields, total_record_count, batch_size)
        except Exception as e:
            print(f"Cursor-based pagination failed: {str(e)}")
            print("Falling back to smaller batch sizes...")
            try:
                return process_with_small_batches(object_name, valid_fields, total_record_count)
            except Exception as e2:
                print(f"Small batch processing failed: {str(e2)}")
                print("Falling back to sampling method...")
                use_sampling = True
    
    # For sampling or smaller datasets that fit in one query
    sample_size = min(batch_size, total_record_count)
    if use_sampling:
        print(f"Using sampling with {sample_size} records (out of {total_record_count} total)")
    
    # Build query
    query = f"SELECT Id, {field_list} FROM {object_name}"
    
    # Add limit for the sample
    if use_sampling or sample_size < total_record_count:
        query += f" LIMIT {sample_size}"
    
    # Execute query
    cmd = f'sfdx force:data:soql:query -q "{query}" --json'
    print(f"Executing query: {query}")
    result = run_sfdx_command(cmd)
    
    if not result or 'result' not in result or 'records' not in result['result']:
        print(f"Error querying data for {object_name}")
        return []
    
    # Convert to dataframe
    records = result['result']['records']
    df = pd.DataFrame(records)
    
    # Remove attributes column
    if 'attributes' in df.columns:
        df = df.drop(columns=['attributes'])
    
    # Calculate usage for each field
    results = []
    for field_name, field_type in valid_fields.items():
        if field_name not in df.columns:
            print(f"Warning: Field {field_name} not found in query results")
            continue
        
        # Special handling for compound fields (address, location, etc.)
        if field_type in ['address', 'location']:
            # For compound fields, check if any part is non-null
            if field_type == 'address':
                # Try to access nested dictionary values if they exist
                non_null_count = 0
                for _, row in df.iterrows():
                    field_value = row.get(field_name)
                    if isinstance(field_value, dict) and any(v for v in field_value.values() if v is not None):
                        non_null_count += 1
            else:
                # For other compound fields, just check if the field itself is not null
                non_null_count = df[field_name].notna().sum()
        else:
            # For regular fields, use pandas vectorized operations
            non_null_count = df[field_name].notna().sum()
        
        # Calculate percentage
        usage_pct = (non_null_count / len(df)) * 100
        
        # If using a sample, extrapolate to full dataset
        if use_sampling:
            estimated_non_null = int((usage_pct / 100) * total_record_count)
            results.append({
                "object": object_name,
                "field": field_name,
                "total_records": total_record_count,
                "non_null_records": estimated_non_null,
                "usage_pct": round(usage_pct, 2),
                "is_estimated": True,
                "sample_size": sample_size
            })
        else:
            results.append({
                "object": object_name,
                "field": field_name,
                "total_records": total_record_count,
                "non_null_records": int(non_null_count),
                "usage_pct": round(usage_pct, 2),
                "is_estimated": False
            })
    
    return results

def process_with_cursor_pagination(object_name, valid_fields, total_record_count, batch_size=2000):
    """Process full dataset using cursor-based pagination
    
    Args:
        object_name: Name of the Salesforce object
        valid_fields: Dictionary mapping field names to field types
        total_record_count: Total record count
        batch_size: Maximum number of records to query in a batch
        
    Returns:
        List of dictionaries with field usage statistics
    """
    # Initialize result counters for each field
    field_counts = {field: 0 for field in valid_fields.keys()}
    processed_records = 0
    
    # Build field list for query
    field_list = ", ".join(valid_fields.keys())
    
    # Use Id as the ordering field for cursor-based pagination
    query = f"SELECT Id, {field_list} FROM {object_name} ORDER BY Id"
    
    # Set a smaller batch size to avoid query timeouts
    actual_batch_size = min(batch_size, 2000)
    query += f" LIMIT {actual_batch_size}"
    
    # Execute initial query
    cmd = f'sfdx force:data:soql:query -q "{query}" --json'
    print(f"Starting cursor-based pagination with batch size {actual_batch_size}")
    result = run_sfdx_command(cmd)
    
    if not result or 'result' not in result or 'records' not in result['result']:
        print(f"Error in initial query for {object_name}")
        raise Exception("Initial pagination query failed")
    
    batch_num = 1
    while True:
        # Process current batch
        records = result['result']['records']
        if not records:
            break
            
        df = pd.DataFrame(records)
        
        # Remove attributes column
        if 'attributes' in df.columns:
            df = df.drop(columns=['attributes'])
        
        # Update counts for each field
        for field_name, field_type in valid_fields.items():
            if field_name not in df.columns:
                continue
            
            # Special handling for compound fields (address, location, etc.)
            if field_type in ['address', 'location']:
                # For compound fields, check if any part is non-null
                if field_type == 'address':
                    # Try to access nested dictionary values if they exist
                    for _, row in df.iterrows():
                        field_value = row.get(field_name)
                        if isinstance(field_value, dict) and any(v for v in field_value.values() if v is not None):
                            field_counts[field_name] += 1
                else:
                    # For other compound fields, just check if the field itself is not null
                    field_counts[field_name] += df[field_name].notna().sum()
            else:
                # For regular fields, use pandas vectorized operations
                field_counts[field_name] += df[field_name].notna().sum()
        
        # Update progress
        processed_records += len(records)
        print(f"Processed batch {batch_num} with {len(records)} records ({processed_records} total, {(processed_records/total_record_count)*100:.1f}%)")
        
        # Check if we've processed all records
        if processed_records >= total_record_count or len(records) < actual_batch_size:
            break
        
        # Get the last ID from the current batch for cursor-based pagination
        last_id = records[-1]['Id']
        
        # Build next query with cursor (WHERE Id > last_id)
        next_query = f"SELECT Id, {field_list} FROM {object_name} WHERE Id > '{last_id}' ORDER BY Id LIMIT {actual_batch_size}"
        cmd = f'sfdx force:data:soql:query -q "{next_query}" --json'
        
        # Execute next query
        result = run_sfdx_command(cmd)
        if not result or 'result' not in result or 'records' not in result['result']:
            print(f"Error in pagination query for {object_name} after ID {last_id}")
            break
        
        batch_num += 1
    
    # Calculate results based on processed data
    results = []
    for field_name, field_type in valid_fields.items():
        non_null_count = field_counts[field_name]
        usage_pct = (non_null_count / processed_records) * 100 if processed_records > 0 else 0
        
        results.append({
            "object": object_name,
            "field": field_name,
            "total_records": total_record_count,
            "non_null_records": int(non_null_count),
            "usage_pct": round(usage_pct, 2),
            "is_estimated": processed_records < total_record_count,
            "records_analyzed": processed_records
        })
    
    return results

def process_with_small_batches(object_name, valid_fields, total_record_count, batch_size=500):
    """Process full dataset using very small batches to avoid SOQL limitations
    
    Args:
        object_name: Name of the Salesforce object
        valid_fields: Dictionary mapping field names to field types
        total_record_count: Total record count
        batch_size: Small batch size to use (default: 500)
        
    Returns:
        List of dictionaries with field usage statistics
    """
    # Initialize result counters for each field
    field_counts = {field: 0 for field in valid_fields.keys()}
    processed_records = 0
    
    # Build field list for query
    field_list = ", ".join(valid_fields.keys())
    
    # Determine how many batches we need
    num_batches = (total_record_count + batch_size - 1) // batch_size
    print(f"Processing with very small batches: {num_batches} batches of {batch_size} records each")
    
    # Process each batch with a new query
    for batch_num in range(1, num_batches + 1):
        offset = (batch_num - 1) * batch_size
        
        # Build query for this small batch
        query = f"SELECT Id, {field_list} FROM {object_name} LIMIT {batch_size} OFFSET {offset}"
        
        # Execute query
        cmd = f'sfdx force:data:soql:query -q "{query}" --json'
        print(f"Processing small batch {batch_num}/{num_batches} (records {offset+1}-{min(offset+batch_size, total_record_count)})")
        
        result = run_sfdx_command(cmd)
        if not result or 'result' not in result or 'records' not in result['result']:
            print(f"Error in small batch query for {object_name} at offset {offset}")
            # Continue with next batch instead of breaking completely
            continue
        
        # Process batch
        records = result['result']['records']
        if not records:
            # No more records
            break
            
        df = pd.DataFrame(records)
        
        # Remove attributes column
        if 'attributes' in df.columns:
            df = df.drop(columns=['attributes'])
        
        # Update counts for each field
        for field_name, field_type in valid_fields.items():
            if field_name not in df.columns:
                continue
            
            # Special handling for compound fields (address, location, etc.)
            if field_type in ['address', 'location']:
                # For compound fields, check if any part is non-null
                if field_type == 'address':
                    # Try to access nested dictionary values if they exist
                    for _, row in df.iterrows():
                        field_value = row.get(field_name)
                        if isinstance(field_value, dict) and any(v for v in field_value.values() if v is not None):
                            field_counts[field_name] += 1
                else:
                    # For other compound fields, just check if the field itself is not null
                    field_counts[field_name] += df[field_name].notna().sum()
            else:
                # For regular fields, use pandas vectorized operations
                field_counts[field_name] += df[field_name].notna().sum()
        
        # Update progress
        processed_records += len(records)
        print(f"Processed {processed_records} of {total_record_count} records ({(processed_records/total_record_count)*100:.1f}%)")
        
        # To avoid overloading the system, add a small delay between batches
        import time
        time.sleep(0.5)
    
    # Calculate results based on all processed batches
    results = []
    for field_name, field_type in valid_fields.items():
        non_null_count = field_counts[field_name]
        usage_pct = (non_null_count / processed_records) * 100 if processed_records > 0 else 0
        
        results.append({
            "object": object_name,
            "field": field_name,
            "total_records": total_record_count,
            "non_null_records": int(non_null_count),
            "usage_pct": round(usage_pct, 2),
            "is_estimated": processed_records < total_record_count,
            "records_analyzed": processed_records
        })
    
    return results

def get_field_usage(object_name, field_name, total_record_count=None, sample_size=5000):
    """Check usage percentage for a specific field in a Salesforce object
    
    Args:
        object_name: Name of the Salesforce object to check
        field_name: Name of the field to check usage for (should be a single field name, not a list or comma-separated string)
        total_record_count: Total record count (if already known)
        sample_size: Maximum number of records to query for sampling (default: 5000)
        
    Returns:
        Dictionary with usage statistics or None if error
    """
    # Ensure we have a single field name, not a comma-separated string
    if ',' in field_name:
        print(f"Warning: field_name '{field_name}' contains commas. This function expects a single field name.")
        field_name = field_name.split(',')[0].strip()
        print(f"Using only the first field: '{field_name}'")
    
    # Get total record count if not provided
    if total_record_count is None:
        total_record_count = get_total_record_count(object_name)
        print(f"Total {object_name} records: {total_record_count}")
    
    # If there are no records, return 0%
    if total_record_count == 0:
        return {
            "object": object_name,
            "field": field_name,
            "total_records": 0,
            "non_null_records": 0,
            "usage_pct": 0.0
        }
    
    # Check if field exists by getting field metadata
    field_cmd = f'sfdx force:schema:sobject:describe -s {object_name} --json'
    field_result = run_sfdx_command(field_cmd)
    
    if not field_result or 'result' not in field_result:
        print(f"Error: Could not retrieve metadata for {object_name}")
        return None
    
    # Check if field exists in object
    field_exists = False
    field_type = None
    for field in field_result['result']['fields']:
        if field['name'].lower() == field_name.lower():
            field_exists = True
            field_type = field['type'].lower()
            break
    
    if not field_exists:
        print(f"Error: Field '{field_name}' does not exist on {object_name}")
        return None
    
    # Some field types can't be queried with != null
    nonqueryable_field_types = ['address', 'location', 'richtext', 'base64', 'encrypted']
    
    # If field is of a nonqueryable type or has special characters, use alternative method
    use_alternative = False
    if field_type in nonqueryable_field_types:
        print(f"Field '{field_name}' is of type '{field_type}' which can't be queried with simple SOQL.")
        use_alternative = True
    
    # Also use alternative method if field name contains special characters
    if any(c in field_name for c in ['$', '%', '^', '&', '*', '+', '=', '`', '~', '"', "'", '(', ')', '[', ']', '{', '}', '<', '>', '?', '\\', '|']):
        print(f"Field '{field_name}' contains special characters that may cause SOQL issues.")
        use_alternative = True
    
    # Use alternative sampling method if needed
    if use_alternative:
        print("Using alternative method to calculate usage (sampling records)...")
        
        # Get a sample of records (limit to the specified sample_size)
        sample_size = min(sample_size, total_record_count)
        query = f"SELECT {field_name} FROM {object_name} LIMIT {sample_size}"
        cmd = f'sfdx force:data:soql:query -q "{query}" --json'
        result = run_sfdx_command(cmd)
        
        if not result or 'result' not in result:
            print(f"Error querying {field_name} data from {object_name}")
            return None
        
        # Count non-null values in the sample
        non_null_count = 0
        for record in result['result']['records']:
            field_value = record.get(field_name)
            if field_value is not None:
                # For compound fields like Address, check if any component is non-null
                if isinstance(field_value, dict):
                    if any(v for v in field_value.values() if v is not None):
                        non_null_count += 1
                else:
                    non_null_count += 1
        
        # Calculate estimated usage percentage from sample
        sample_pct = (non_null_count / sample_size) * 100
        
        # Extrapolate to full dataset
        estimated_non_null = int((sample_pct / 100) * total_record_count)
        
        return {
            "object": object_name,
            "field": field_name, 
            "total_records": total_record_count,
            "non_null_records": estimated_non_null,
            "usage_pct": round(sample_pct, 2),
            "is_estimated": True,
            "sample_size": sample_size
        }
    
    # For normal fields, use SOQL COUNT query
    try:
        # Try using COUNT() query first (more efficient)
        query = f"SELECT COUNT() FROM {object_name} WHERE {field_name} != null"
        cmd = f'sfdx force:data:soql:query -q "{query}" --json'
        result = run_sfdx_command(cmd)
        
        if result and 'result' in result:
            non_null_count = result['result']['totalSize']
            usage_pct = (non_null_count / total_record_count) * 100
            
            return {
                "object": object_name,
                "field": field_name,
                "total_records": total_record_count,
                "non_null_records": non_null_count,
                "usage_pct": round(usage_pct, 2),
                "is_estimated": False
            }
        else:
            # Fall back to alternative method if COUNT query fails
            print(f"COUNT query failed for field '{field_name}', using alternative sampling method...")
            
            # Use same alternative sampling method as above
            sample_size = min(sample_size, total_record_count)
            query = f"SELECT {field_name} FROM {object_name} LIMIT {sample_size}"
            cmd = f'sfdx force:data:soql:query -q "{query}" --json'
            result = run_sfdx_command(cmd)
            
            if not result or 'result' not in result:
                print(f"Error querying {field_name} data from {object_name}")
                return None
            
            # Count non-null values in the sample
            non_null_count = 0
            for record in result['result']['records']:
                field_value = record.get(field_name)
                if field_value is not None:
                    # For compound fields like Address, check if any component is non-null
                    if isinstance(field_value, dict):
                        if any(v for v in field_value.values() if v is not None):
                            non_null_count += 1
                    else:
                        non_null_count += 1
            
            # Calculate estimated usage percentage from sample
            sample_pct = (non_null_count / sample_size) * 100
            
            # Extrapolate to full dataset
            estimated_non_null = int((sample_pct / 100) * total_record_count)
            
            return {
                "object": object_name,
                "field": field_name, 
                "total_records": total_record_count,
                "non_null_records": estimated_non_null,
                "usage_pct": round(sample_pct, 2),
                "is_estimated": True,
                "sample_size": sample_size
            }
    except Exception as e:
        print(f"Error calculating field usage: {e}")
        return None

def analyze_fields(object_name, field_names, batch_size=DEFAULT_BATCH_SIZE, use_full_dataset=False):
    """Analyze usage for multiple fields in a Salesforce object
    
    Args:
        object_name: Name of the Salesforce object to analyze
        field_names: List of field names to analyze, or comma-separated string
        batch_size: Maximum number of records to query in a batch
        use_full_dataset: If True, analyze the full dataset even if large
        
    Returns:
        List of dictionaries with field usage data
    """
    # Convert string input to list if needed
    if isinstance(field_names, str):
        field_names = [field.strip() for field in field_names.split(',')]
        print(f"Converted string input to list of {len(field_names)} fields: {field_names}")
    
    # Check if SFDX is installed and authenticated
    check_sfdx_installed()
    
    # Get total record count once (for efficiency)
    total_record_count = get_total_record_count(object_name)
    print(f"Total {object_name} records: {total_record_count}")
    
    # If pandas is available, use the batch method
    if HAS_PANDAS and len(field_names) > 1:
        print(f"Using batch processing for {len(field_names)} fields")
        return get_field_usage_batch(object_name, field_names, total_record_count, batch_size, use_full_dataset)
    
    # Otherwise, process each field individually
    results = []
    for field_name in field_names:
        print(f"Analyzing field: {field_name}")
        result = get_field_usage(object_name, field_name, total_record_count)
        if result:
            results.append(result)
    
    return results

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description='Analyze Salesforce field usage for specific fields')
    parser.add_argument('--object', '-o', type=str, default=DEFAULT_OBJECT,
                        help=f'Salesforce object API name to analyze (default: {DEFAULT_OBJECT})')
    parser.add_argument('--fields', '-f', type=str, nargs='+', default=DEFAULT_FIELDS,
                        help=f'Field API names to analyze (default: {", ".join(DEFAULT_FIELDS)})')
    parser.add_argument('--batch-size', '-b', type=int, default=DEFAULT_BATCH_SIZE,
                        help=f'Maximum number of records to query in a batch (default: {DEFAULT_BATCH_SIZE})')
    parser.add_argument('--no-batch', action='store_true',
                        help='Disable batch processing even if pandas is available')
    parser.add_argument('--full-dataset', action='store_true',
                        help='Analyze the full dataset even if large (may take longer)')
    return parser.parse_args()

def main():
    try:
        # Parse command-line arguments
        args = parse_args()
        
        object_name = args.object
        field_names = args.fields
        batch_size = args.batch_size
        use_full_dataset = args.full_dataset
        
        # If --no-batch is specified, temporarily disable pandas
        if args.no_batch:
            global HAS_PANDAS
            original_pandas_state = HAS_PANDAS
            HAS_PANDAS = False
        
        print(f"Analyzing usage for fields in {object_name}: {', '.join(field_names)}")
        print(f"Using {'complete dataset' if use_full_dataset else f'batches of {batch_size} records'}")
        
        # Analyze field usage
        results = analyze_fields(object_name, field_names, batch_size, use_full_dataset)
        
        # Restore original pandas state if it was changed
        if args.no_batch:
            HAS_PANDAS = original_pandas_state
        
        # Display results
        print("\nField Usage Results:")
        print("-" * 80)
        print(f"{'Field':<30} {'Usage %':<10} {'Non-null Records':<20} {'Total Records':<15}")
        print("-" * 80)
        
        for result in results:
            field_name = result['field']
            usage_pct = result['usage_pct']
            non_null = result['non_null_records']
            total = result['total_records']
            estimated = "(estimated)" if result.get('is_estimated', False) else ""
            
            print(f"{field_name:<30} {usage_pct:<10.2f} {non_null:<20,d} {total:<15,d} {estimated}")
        
        print("-" * 80)
        
        # Sort by usage percentage
        sorted_results = sorted(results, key=lambda x: x['usage_pct'], reverse=True)
        
        # Show sorted by usage
        print("\nFields Sorted by Usage Percentage (Highest to Lowest):")
        print("-" * 80)
        print(f"{'Field':<30} {'Usage %':<10}")
        print("-" * 80)
        
        for result in sorted_results:
            field_name = result['field']
            usage_pct = result['usage_pct']
            print(f"{field_name:<30} {usage_pct:<10.2f}")
        
        print("-" * 80)
        
    except KeyboardInterrupt:
        print("\nProcess interrupted by user. Exiting.")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 