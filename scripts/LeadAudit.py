import subprocess
import json
import pandas as pd
import datetime
import sys

# Define your SOQL query (replace with your actual query)
query = "Select Email, Id, LastActivityDate, Title, IsConverted FROM Lead"

cmd = [
    "sfdx",  # Ensure the 'sfdx' CLI is in your system PATH
    "force:data:soql:query",
    "-q", query,
    "-r", "json"  # Output the results in JSON format for easier parsing
]
# comment somewhere
# another one
# Execute the command and capture output
result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

# Check if the command was successful
if result.returncode != 0:
    print("Error executing SFDX command:")
    print(result.stderr)
    sys.exit(1)

# Parse the JSON output from stdout
data = json.loads(result.stdout)

# Create a DataFrame from the SOQL output records
records = data.get("result", {}).get("records", [])
if not records:
    print("No records found in the SFDX output")
    sys.exit(1)

df = pd.DataFrame(records)
# Optionally, convert column names to uppercase for consistency in later processing
df.columns = df.columns.str.upper()

# --------------------------
# Data Preparation
# --------------------------

# Convert numeric fields
# df['ANNUALREVENUE'] = pd.to_numeric(df['ANNUALREVENUE'], errors='coerce')

# Convert date fields with UTC conversion then remove timezone info
df['LASTACTIVITYDATE'] = pd.to_datetime(df['LASTACTIVITYDATE'], errors='coerce', utc=True).dt.tz_convert(None)

# Convert boolean fields
df['ISCONVERTED'] = df['ISCONVERTED'].apply(lambda x: True if str(x).strip().upper() == 'TRUE' else False)

# Define today's date (timezone-naive)
today = pd.to_datetime(datetime.date.today())

# --------------------------
# KPI Calculations
# --------------------------

# 1. Total number of records
total_records = len(df)

# 2. Total number that are missing an email.
# This checks for NaN values or empty strings (after stripping whitespace).
missing_email = df['EMAIL'].isna() | (df['EMAIL'].astype(str).str.strip() == "")
total_missing_email = missing_email.sum()

# 3. Total number that are missing a title.
missing_title = df['TITLE'].isna() | (df['TITLE'].astype(str).str.strip() == "")
total_missing_title = missing_title.sum()

# 4. Total number where LastActivityDate is blank.
# Convert LastActivityDate to datetime (errors coerced to NaT)
df['LASTACTIVITYDATE'] = pd.to_datetime(df['LASTACTIVITYDATE'], errors='coerce')
missing_last_activity = df['LASTACTIVITYDATE'].isna()
total_missing_last_activity = missing_last_activity.sum()

# 5 & 6. Compute date threshold for 90 days and count accordingly.
today = pd.to_datetime(datetime.date.today())
threshold_date = today - pd.Timedelta(days=90)

# Total number where LastActivityDate is over 90 days ago.
over_90_days = df['LASTACTIVITYDATE'].notna() & (df['LASTACTIVITYDATE'] < threshold_date)
total_over_90 = over_90_days.sum()

# Total number where LastActivityDate is within the last 90 days.
within_90_days = df['LASTACTIVITYDATE'].notna() & (df['LASTACTIVITYDATE'] >= threshold_date)
total_within_90 = within_90_days.sum()

# 7. Count converted leads
converted_leads = df[df['ISCONVERTED'] == True]
total_converted = len(converted_leads)

# Print out the metrics
print("\n--- Lead KPIs ---")
print(f"Leads = {total_records}")

# Calculate and print percentages for each metric
email_pct = (total_missing_email / total_records) * 100
print(f"  No Email = {total_missing_email} ({email_pct:.2f}%)")

title_pct = (total_missing_title / total_records) * 100
print(f"  No Title = {total_missing_title} ({title_pct:.2f}%)")

converted_pct = (total_converted / total_records) * 100
print(f"  Converted = {total_converted} ({converted_pct:.2f}%)")

print("Leads with No Sales Activity")
activity_ever_pct = (total_missing_last_activity / total_records) * 100
print(f"  No Activity Ever = {total_missing_last_activity} ({activity_ever_pct:.2f}%)")

over_90_pct = (total_over_90 / total_records) * 100
print(f"  No Activity >90 Days = {total_over_90} ({over_90_pct:.2f}%)")

within_90_pct = (total_within_90 / total_records) * 100
print(f"  No Activity <90 Days = {total_within_90} ({within_90_pct:.2f}%)")