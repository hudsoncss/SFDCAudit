#!/usr/bin/env python3

import json
import subprocess
import os
import sys
import argparse
import csv
import re
from sf_field_usage_single import analyze_fields, check_sfdx_installed, run_sfdx_command

# Define objects and their fields to analyze
# This structure allows you to easily add or modify objects and fields to audit
AUDIT_CONFIG = {
    "Lead": [
        "FirstName",
        "LastName",
        "Title", 
        "Phone",
        "MobilePhone",
        "Email",
        "Website",
        "Company",
        "State",
        "Country",
        "IsConverted",
        "LeadSource",
        "Status",
        "Industry",
        "Rating",
        "AnnualRevenue",
        "NumberOfEmployees",
        "ConvertedOpportunityId",
        "LastActivityDate"
    ],
    "Contact": [
        "FirstName",
        "LastName",
        "AccountId",
        "Title",
        "Email",
        "Phone",
        "MobilePhone",
        "MailingState",
        "MailingCountry",
        "LeadSource"
    ],
    "Account": [
        "Type",
        "ParentId",
        "Phone",
        "Website",
        "NumberOfEmployees",
        "AnnualRevenue",
        "Sic",
        "Industry",
        "BillingCity",
        "BillingCountry"
    ],
    "Opportunity": [
        "Type",
        "Amount",
        "NextStep",
        "ForecastCategory",
        "CampaignId",
        "IsWon",
        "IsClosed"
    ]
}

def get_company_name():
    """Get the company name from Salesforce org information"""
    try:
        # Get org details using SFDX
        cmd = "sfdx force:org:display --json"
        result = run_sfdx_command(cmd)
        
        if result and 'result' in result:
            # Try to extract company name from org display
            org_name = result['result'].get('name')
            username = result['result'].get('username')
            
            if org_name and not org_name.startswith('00D'):  # Avoid org IDs
                # Clean the org name for use in filenames
                return clean_filename(org_name)
            elif username:
                # Extract domain from username as fallback
                domain = username.split('@')[1].split('.')[0]
                return clean_filename(domain)
        
        # If we still don't have company name, try an alternative approach
        print("Trying to get company name from organization info...")
        query = "SELECT Name FROM Organization LIMIT 1"
        cmd = f'sfdx force:data:soql:query -q "{query}" --json'
        result = run_sfdx_command(cmd)
        
        if result and 'result' in result and 'records' in result['result'] and len(result['result']['records']) > 0:
            company_name = result['result']['records'][0].get('Name')
            if company_name:
                return clean_filename(company_name)
        
        # Default name if we couldn't get the company name
        print("Could not determine company name, using default.")
        return "salesforce_org"
    
    except Exception as e:
        print(f"Error getting company name: {e}")
        return "salesforce_org"

def clean_filename(name):
    """Clean a string to be used in a filename"""
    # Replace spaces with underscores and remove special characters
    cleaned = re.sub(r'[^\w\s-]', '', name)
    cleaned = re.sub(r'[\s-]+', '_', cleaned)
    return cleaned.lower()

def parse_args():
    """Parse command-line arguments"""
    # Get company name for default filenames
    company_name = get_company_name()
    json_default = f"{company_name}_data_audit.json"
    csv_default = f"{company_name}_data_audit.csv"
    
    parser = argparse.ArgumentParser(description='Run field usage audit across multiple Salesforce objects')
    parser.add_argument('--objects', '-o', type=str, nargs='+',
                        help='Specific objects to analyze (default: all configured objects)')
    parser.add_argument('--batch-size', '-b', type=int, default=5000,
                        help='Maximum number of records to query in a batch (default: 5000)')
    parser.add_argument('--output', type=str, default=json_default,
                        help=f'Output file path for JSON results (default: {json_default})')
    parser.add_argument('--csv-output', type=str, default=csv_default,
                        help=f'Output file path for CSV results (default: {csv_default})')
    return parser.parse_args()

def run_audit(objects_to_audit=None, batch_size=5000, use_full_dataset=True):
    """Run audit for specified objects or all objects in AUDIT_CONFIG
    
    Args:
        objects_to_audit: List of object names to audit (None = all in AUDIT_CONFIG)
        batch_size: Maximum number of records to query in a batch
        use_full_dataset: If True, analyze the full dataset even if large
        
    Returns:
        Dictionary with audit results
    """
    # Check if SFDX is installed and authenticated
    check_sfdx_installed()
    
    # Use all objects if none specified
    if not objects_to_audit:
        objects_to_audit = list(AUDIT_CONFIG.keys())
    
    # Filter to include only objects that exist in our config
    objects_to_audit = [obj for obj in objects_to_audit if obj in AUDIT_CONFIG]
    
    if not objects_to_audit:
        print("No valid objects specified for audit!")
        return {}
    
    # Initialize results
    audit_results = {}
    
    # Process each object
    for object_name in objects_to_audit:
        print(f"\n{'='*80}")
        print(f"Analyzing fields for {object_name}")
        print(f"{'='*80}")
        
        # Get fields for this object
        fields = AUDIT_CONFIG[object_name]
        
        if not fields:
            print(f"No fields configured for {object_name}, skipping")
            continue
        
        # Use sf_field_usage_single to analyze fields
        results = analyze_fields(
            object_name, 
            fields, 
            batch_size=batch_size, 
            use_full_dataset=use_full_dataset
        )
        
        # Add to audit results
        audit_results[object_name] = results
    
    return audit_results

def print_summary(audit_results):
    """Print a summary of the audit results"""
    print("\n\n")
    print("="*100)
    print("FIELD USAGE AUDIT SUMMARY")
    print("="*100)
    
    for object_name, results in audit_results.items():
        print(f"\n{object_name}:")
        print("-" * 80)
        print(f"{'Field':<40} {'Usage %':<10} {'Non-null Records':<20} {'Total Records':<15}")
        print("-" * 80)
        
        # Sort results by usage percentage (highest first)
        sorted_results = sorted(results, key=lambda x: x['usage_pct'], reverse=True)
        
        for result in sorted_results:
            field_name = result['field']
            usage_pct = result['usage_pct']
            non_null = result['non_null_records']
            total = result['total_records']
            estimated = "(estimated)" if result.get('is_estimated', False) else ""
            
            print(f"{field_name:<40} {usage_pct:<10.2f} {non_null:<20,d} {total:<15,d} {estimated}")
    
    print("\n")

def save_to_csv(audit_results, csv_file_path):
    """Save audit results to a CSV file
    
    Args:
        audit_results: Dictionary with audit results
        csv_file_path: Path to save the CSV file
    """
    try:
        with open(csv_file_path, 'w', newline='') as csvfile:
            fieldnames = ['Object', 'Field', 'Usage %', 'Non-null Records', 'Total Records', 'Is Estimated']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            
            for object_name, results in audit_results.items():
                # Sort results by usage percentage (highest first)
                sorted_results = sorted(results, key=lambda x: x['usage_pct'], reverse=True)
                
                for result in sorted_results:
                    writer.writerow({
                        'Object': object_name,
                        'Field': result['field'],
                        'Usage %': f"{result['usage_pct']:.2f}",
                        'Non-null Records': result['non_null_records'],
                        'Total Records': result['total_records'],
                        'Is Estimated': 'Yes' if result.get('is_estimated', False) else 'No'
                    })
        
        print(f"CSV results saved to {csv_file_path}")
    except Exception as e:
        print(f"Error saving CSV results: {e}")

def main():
    """Main entry point for the script"""
    try:
        # Parse command-line arguments
        args = parse_args()
        
        print("Starting Salesforce Field Usage Audit")
        print(f"Batch size: {args.batch_size}")
        print("Using full dataset analysis for all objects")
        
        # Run audit
        results = run_audit(
            objects_to_audit=args.objects,
            batch_size=args.batch_size,
            use_full_dataset=True
        )
        
        # Save results to JSON file
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nAudit results saved to {args.output}")
        
        # Save results to CSV file
        save_to_csv(results, args.csv_output)
        
        # Print summary
        print_summary(results)
        
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