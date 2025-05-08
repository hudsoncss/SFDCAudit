import subprocess
import json
import pandas as pd
import datetime
import sys
import time

print("Starting AccountAudit.py script...")

# Define your SOQL query (replace with your actual query)
query = "SELECT Id, Name, CreatedDate, LastActivityDate, Industry, Type, Website FROM Account"
print(f"Querying Accounts with: {query}")

cmd = [
    "sfdx",  # Ensure the 'sfdx' CLI is in your system PATH
    "force:data:soql:query",
    "-q", query,
    "-r", "json"  # Output the results in JSON format for easier parsing
]

# Execute the command and capture output with explicit encoding
try:
    print("Executing SFDX command for Accounts...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)

    # Check if the command was successful
    if result.returncode != 0:
        print("Error executing SFDX command:")
        print(result.stderr)
        sys.exit(1)

    # Parse the JSON output from stdout
    if result.stdout:
        data = json.loads(result.stdout)
        print(f"Successfully retrieved Account data. Records: {len(data.get('result', {}).get('records', []))}")
    else:
        print("No output received from SFDX command")
        sys.exit(1)
except Exception as e:
    print(f"Error executing or parsing SFDX command: {e}")
    sys.exit(1)

# Create a DataFrame from the SOQL output records
records = data.get("result", {}).get("records", [])
if not records:
    print("No records found in the SFDX output")
    sys.exit(1)

df = pd.DataFrame(records)
# Optionally, convert column names to uppercase for consistency in later processing
df.columns = df.columns.str.upper()
print(f"Created DataFrame with {len(df)} Account records")
print(f"DataFrame columns: {list(df.columns)}")

# Create a dictionary mapping Account IDs to names upfront
account_names = {row['ID']: row['NAME'] for _, row in df.iterrows()}
print(f"Created mapping for {len(account_names)} accounts")

# Query to get won opportunities with their account and amount
won_opps_query = """SELECT Id, AccountId, Account.Name, Amount FROM Opportunity WHERE IsWon = TRUE"""
print(f"Querying Opportunities with: {won_opps_query}")

cmd_won_opps = [
    "sfdx",
    "force:data:soql:query",
    "-q", won_opps_query,
    "-r", "json"
]

# Execute the command and capture output with explicit encoding
try:
    print("Executing SFDX command for Opportunities...")
    won_opps_result = subprocess.run(cmd_won_opps, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)

    # Check if the command was successful
    if won_opps_result.returncode != 0:
        print("Error executing SFDX command for won opportunities:")
        print(won_opps_result.stderr)
        sys.exit(1)

    # Parse the JSON output from stdout
    if won_opps_result.stdout:
        won_opps_data = json.loads(won_opps_result.stdout)
        print(f"Successfully retrieved Opportunity data. Records: {len(won_opps_data.get('result', {}).get('records', []))}")
    else:
        print("No output received from SFDX command for won opportunities")
        won_opps_df = pd.DataFrame(columns=["ID", "ACCOUNTID", "ACCOUNT_NAME", "AMOUNT"])
        won_opps_records = []
except Exception as e:
    print(f"Error executing or parsing SFDX command for won opportunities: {e}")
    won_opps_df = pd.DataFrame(columns=["ID", "ACCOUNTID", "ACCOUNT_NAME", "AMOUNT"])
    won_opps_records = []

# Create a DataFrame from the SOQL output records for won opportunities
try:
    won_opps_records = won_opps_data.get("result", {}).get("records", [])
    if not won_opps_records:
        print("No won opportunities found")
        won_opps_df = pd.DataFrame(columns=["ID", "ACCOUNTID", "ACCOUNT_NAME", "AMOUNT"])
    else:
        won_opps_df = pd.DataFrame(won_opps_records)
        # Convert column names to uppercase for consistency
        won_opps_df.columns = won_opps_df.columns.str.upper()
        # Convert Amount to numeric
        won_opps_df['AMOUNT'] = pd.to_numeric(won_opps_df['AMOUNT'], errors='coerce')
        print(f"Created DataFrame with {len(won_opps_df)} Opportunity records")
        print(f"Opportunity DataFrame columns: {list(won_opps_df.columns)}")
except NameError:
    # This handles the case when won_opps_data was not defined due to exception
    print("No won opportunities data available")
    won_opps_df = pd.DataFrame(columns=["ID", "ACCOUNTID", "ACCOUNT_NAME", "AMOUNT"])
    won_opps_records = []

# --------------------------
# Data Preparation
# --------------------------
print("Starting data preparation...")

# Convert date fields with UTC conversion then remove timezone info
df['CREATEDDATE'] = pd.to_datetime(df['CREATEDDATE'], errors='coerce', utc=True).dt.tz_convert(None)
df['LASTACTIVITYDATE'] = pd.to_datetime(df['LASTACTIVITYDATE'], errors='coerce', utc=True).dt.tz_convert(None)

# Define today's date (timezone-naive)
today = pd.to_datetime(datetime.date.today())

# --------------------------
# KPI Calculations
# --------------------------
print("Calculating KPIs...")

# 1. Total Number of Accounts (i.e. total records)
total_accounts = len(df)

# 2. Account Growth Rate (using CREATEDDATE)
#    Calculated as the year-over-year growth rate.
current_year = today.year
count_current_year = len(df[df['CREATEDDATE'].dt.year == current_year])
count_previous_year = len(df[df['CREATEDDATE'].dt.year == (current_year - 1)])
growth_rate = ((count_current_year - count_previous_year) / count_previous_year * 100) if count_previous_year > 0 else None

# 3. Accounts by Industry
accounts_by_industry = df['INDUSTRY'].value_counts()

# 4. Accounts by Type
accounts_by_type = df['TYPE'].value_counts()

# 5. Average Account Age (in years)
df['ACCOUNT_AGE_DAYS'] = (today - df['CREATEDDATE']).dt.days
average_account_age_years = df['ACCOUNT_AGE_DAYS'].mean() / 365

# 6. Total number where LASTACTIVITYDATE is blank
blank_lastactivity = df['LASTACTIVITYDATE'].isna() | (df['LASTACTIVITYDATE'].astype(str).str.strip() == "")
total_blank_lastactivity = blank_lastactivity.sum()

# 7. Total number where LASTACTIVITYDATE is over 90 days ago
threshold_date = today - pd.Timedelta(days=90)
over_90_lastactivity = df['LASTACTIVITYDATE'].notna() & (df['LASTACTIVITYDATE'] < threshold_date)
total_over_90_lastactivity = over_90_lastactivity.sum()

# 8. Total number where LASTACTIVITYDATE is within the last 90 days
within_90_lastactivity = df['LASTACTIVITYDATE'].notna() & (df['LASTACTIVITYDATE'] >= threshold_date)
total_within_90_lastactivity = within_90_lastactivity.sum()

# 9. Total number where WEBSITE is blank
blank_website = df['WEBSITE'].isna() | (df['WEBSITE'].astype(str).str.strip() == "")
total_blank_website = blank_website.sum()

# 10. Total number of records (again, same as total_accounts)
total_records = total_accounts

# 11. Count of accounts with at least one won opportunity
if not won_opps_df.empty:
    # Get unique account IDs that have won opportunities
    accounts_with_won_opps = won_opps_df['ACCOUNTID'].nunique()
    
    # Calculate total opportunity amount per account
    opp_amount_by_account = won_opps_df.groupby('ACCOUNTID')['AMOUNT'].sum()
    
    # Calculate average opportunity amount per account with won opportunities
    avg_lifetime_value = opp_amount_by_account.mean()
    print(f"Found {accounts_with_won_opps} accounts with won opportunities")
else:
    accounts_with_won_opps = 0
    avg_lifetime_value = 0
    print("No won opportunities found")

# Calculate Lifetime Customer Value for top customers display
print("Calculating lifetime customer values...")
lifetime_values = {}
opp_account_names = {}

# Only process won_opps_records if it exists and has data
if won_opps_records:
    print(f"Processing {len(won_opps_records)} opportunity records for lifetime value...")
    # Print first record to check structure
    if len(won_opps_records) > 0:
        print(f"Sample opportunity record: {won_opps_records[0]}")
        
    for opp in won_opps_records:
        # In Salesforce API responses, field names may be case-sensitive
        # Try different possible key names for AccountId
        account_id = None
        account_name = "Unknown"
        
        # Try to get Account ID
        for key in ['AccountId', 'ACCOUNTID', 'accountid']:
            if key in opp:
                account_id = opp[key]
                break
                
        if not account_id:
            print(f"Warning: No Account ID found in opportunity record: {opp}")
            continue
        
        # Try to get Account Name from the opportunity record first (if available)
        if 'ACCOUNT' in opp and isinstance(opp['ACCOUNT'], dict) and 'NAME' in opp['ACCOUNT']:
            account_name = opp['ACCOUNT']['NAME']
        elif 'Account' in opp and isinstance(opp['Account'], dict) and 'Name' in opp['Account']:
            account_name = opp['Account']['Name']
        else:
            # Fall back to our account names dictionary
            account_name = account_names.get(account_id, "Unknown")
        
        # Store the account name
        opp_account_names[account_id] = account_name
            
        # Try different possible key names for Amount
        amount = 0
        for key in ['Amount', 'AMOUNT', 'amount']:
            if key in opp:
                try:
                    amount = float(opp[key] or 0)
                except (ValueError, TypeError):
                    print(f"Warning: Invalid amount value in opportunity: {opp[key]}")
                    amount = 0
                break
        
        if account_id in lifetime_values:
            lifetime_values[account_id] += amount
        else:
            lifetime_values[account_id] = amount

    print(f"Built lifetime values for {len(lifetime_values)} accounts")
else:
    print("No opportunity records to process")

# Display Top 10 Accounts by Lifetime Customer Value
top_accounts = sorted(lifetime_values.items(), key=lambda x: x[1], reverse=True)[:10]
print(f"Identified {len(top_accounts)} top accounts by lifetime value")

if top_accounts:
    print("\nTop 10 Accounts by Lifetime Value:")
    print("-----------------")
    for i, (account_id, value) in enumerate(top_accounts, 1):
        # Use the account name from opportunities if available, otherwise use "Unknown"
        account_name = opp_account_names.get(account_id, "Unknown")
        print(f"{i}. {account_name}: ${value:,.2f}")
else:
    print("\nNo customer data available")

# --------------------------
# Output the Metrics
# --------------------------
print("\n--- Account KPIs ---")
print(f"Total Accounts = {total_accounts}")

# Calculate and display percentages for each metric
website_pct = (total_blank_website / total_accounts) * 100
print(f"  No Website = {total_blank_website} ({website_pct:.2f}%)")

print("No Sales Activity")
blank_activity_pct = (total_blank_lastactivity / total_accounts) * 100
print(f"  Ever = {total_blank_lastactivity} ({blank_activity_pct:.2f}%)")

over_90_pct = (total_over_90_lastactivity / total_accounts) * 100
print(f"  >90 Days = {total_over_90_lastactivity} ({over_90_pct:.2f}%)")

within_90_pct = (total_within_90_lastactivity / total_accounts) * 100
print(f"  <90 Days = {total_within_90_lastactivity} ({within_90_pct:.2f}%)")

customer_pct = (accounts_with_won_opps / total_accounts) * 100 if total_accounts > 0 else 0
print(f"Customer Count = {accounts_with_won_opps} ({customer_pct:.2f}%)")
print(f"Average Lifetime Customer Value = ${avg_lifetime_value:,.2f}")

print("Script completed.")