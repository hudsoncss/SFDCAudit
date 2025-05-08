import subprocess
import json
import pandas as pd
import sys
from datetime import datetime

# Function to execute SFDX queries and return dataframe
def query_salesforce(query):
    cmd = [
        "sfdx",
        "force:data:soql:query",
        "-q", query,
        "-r", "json"
    ]
    
    try:
        # Force UTF-8 encoding to handle special characters
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)
        
        if result.returncode != 0:
            print(f"Error executing SFDX command: {result.stderr}")
            return pd.DataFrame()
        
        # Check if stdout is available and not empty
        if not result.stdout or result.stdout.strip() == "":
            print("Empty response from SFDX command")
            return pd.DataFrame()
            
        data = json.loads(result.stdout)
        records = data.get("result", {}).get("records", [])
        
        if not records:
            return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df.columns = df.columns.str.upper()
        return df
    
    except Exception as e:
        print(f"Error executing or parsing SFDX command: {e}")
        return pd.DataFrame()

# Step 1: Query Events with basic fields
event_query = "SELECT Id, Subject, ActivityDate, WhatId, WhoId, CreatedDate FROM Event"
events_df = query_salesforce(event_query)

if events_df.empty:
    print("No event records found")
    sys.exit(1)

# Convert timestamps
events_df['CREATEDDATE'] = pd.to_datetime(events_df['CREATEDDATE'], errors='coerce', utc=True).dt.tz_convert(None)
if 'ACTIVITYDATE' in events_df.columns:
    events_df['ACTIVITYDATE'] = pd.to_datetime(events_df['ACTIVITYDATE'], errors='coerce')

# Step 2: Query Accounts
account_query = "SELECT Id FROM Account"
accounts_df = query_salesforce(account_query)

if accounts_df.empty:
    print("No accounts found")
    sys.exit(1)

# Step 3: Query Opportunities with their Account IDs and Created Dates
opportunity_query = "SELECT Id, AccountId, CreatedDate FROM Opportunity ORDER BY CreatedDate ASC"
opportunities_df = query_salesforce(opportunity_query)

if opportunities_df.empty:
    print("No opportunities found")
    sys.exit(1)

# Convert timestamps
opportunities_df['CREATEDDATE'] = pd.to_datetime(opportunities_df['CREATEDDATE'], errors='coerce', utc=True).dt.tz_convert(None)

# Print total events
total_events = len(events_df)


# Filter events related to accounts
account_ids = set(accounts_df['ID'].tolist())
account_events_df = events_df[events_df['WHATID'].isin(account_ids)]

# Calculate average events before opportunity
if 'ACCOUNTID' in opportunities_df.columns:
    first_opp_by_account = opportunities_df.sort_values('CREATEDDATE').drop_duplicates('ACCOUNTID', keep='first')
    first_opp_dates = dict(zip(first_opp_by_account['ACCOUNTID'], first_opp_by_account['CREATEDDATE']))
    
    # Initialize counters
    accounts_with_opps_and_events = 0
    total_events_before_opp = 0
    
    # For each account with opportunities, count events before first opportunity
    for account_id, first_opp_date in first_opp_dates.items():
        # Get events for this account
        account_specific_events = account_events_df[account_events_df['WHATID'] == account_id]
        
        # Skip if no events for this account
        if len(account_specific_events) == 0:
            continue
        
        # Count events before first opportunity
        events_before_opp = account_specific_events[account_specific_events['CREATEDDATE'] < first_opp_date]
        if len(events_before_opp) > 0:
            accounts_with_opps_and_events += 1
            total_events_before_opp += len(events_before_opp)
    
    # Calculate average events before opportunity creation
    avg_events_before_opp = total_events_before_opp / accounts_with_opps_and_events if accounts_with_opps_and_events > 0 else 0
    
    # Print results
    print("\n--- Event KPIs ---")
    print(f"  Total Events = {total_events}")
    print(f"  Avg. Meetings to 1st Opp: {avg_events_before_opp:.2f}")
else:
    print("  No AccountId field found in Opportunities data")