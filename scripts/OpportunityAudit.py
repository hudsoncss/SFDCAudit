import subprocess
import json
import pandas as pd
import datetime
import sys

# Define your SOQL query (replace with your actual query)
query = "Select Amount, CloseDate, CreatedDate, ForecastCategoryName, Id, IsClosed, IsWon, LastActivityDate, NextStep, Probability, StageName FROM Opportunity"

cmd = [
    "sfdx",  # Ensure the 'sfdx' CLI is in your system PATH
    "force:data:soql:query",
    "-q", query,
    "-r", "json"  # Output the results in JSON format for easier parsing
]

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
df['AMOUNT'] = pd.to_numeric(df['AMOUNT'], errors='coerce')
df['PROBABILITY'] = pd.to_numeric(df['PROBABILITY'], errors='coerce')

# Convert date fields with UTC conversion then remove timezone info
df['CREATEDDATE'] = pd.to_datetime(df['CREATEDDATE'], errors='coerce', utc=True).dt.tz_convert(None)
df['CLOSEDATE'] = pd.to_datetime(df['CLOSEDATE'], errors='coerce', utc=True).dt.tz_convert(None)
df['LASTACTIVITYDATE'] = pd.to_datetime(df['LASTACTIVITYDATE'], errors='coerce', utc=True).dt.tz_convert(None)

# Convert boolean fields (assuming the CSV has "TRUE"/"FALSE" strings)
df['ISCLOSED'] = df['ISCLOSED'].apply(lambda x: True if str(x).strip().upper() == 'TRUE' else False)
df['ISWON'] = df['ISWON'].apply(lambda x: True if str(x).strip().upper() == 'TRUE' else False)

# Define today's date (timezone-naive)
today = pd.to_datetime(datetime.date.today())

# --------------------------
# KPI Calculations
# --------------------------

# 1. Total Number of Opportunities
total_opportunities = len(df)

# 2. Total number where LASTACTIVITYDATE is blank
blank_lastactivity = df['LASTACTIVITYDATE'].isna() | (df['LASTACTIVITYDATE'].astype(str).str.strip() == "")
total_blank_lastactivity = blank_lastactivity.sum()

# 3. Total number where LASTACTIVITYDATE is over 90 days ago
threshold_date = today - pd.Timedelta(days=90)
over_90_lastactivity = df['LASTACTIVITYDATE'].notna() & (df['LASTACTIVITYDATE'] < threshold_date)
total_over_90_lastactivity = over_90_lastactivity.sum()

# 4. Total number where LASTACTIVITYDATE is within the last 90 days
within_90_lastactivity = df['LASTACTIVITYDATE'].notna() & (df['LASTACTIVITYDATE'] >= threshold_date)
total_within_90_lastactivity = within_90_lastactivity.sum()

# 5. Total number where NEXTSTEP is blank
blank_nextstep = df['NEXTSTEP'].isna() | (df['NEXTSTEP'].astype(str).str.strip() == "")
total_blank_nextstep = blank_nextstep.sum()

# 4. Pipeline Value: Sum of AMOUNT for open opportunities (ISCLOSED == False)
df_open = df[df['ISCLOSED'] == False]
pipeline_value = df_open['AMOUNT'].sum()

# 5. Weighted Pipeline Value: Sum(AMOUNT * (PROBABILITY/100)) for open opportunities
weighted_pipeline_value = (df_open['AMOUNT'] * (df_open['PROBABILITY'] / 100)).sum()

# 6. Win Rate: Percentage of closed opportunities (ISCLOSED == True) that are won (ISWON == True)
df_closed = df[df['ISCLOSED'] == True]
won_opportunities = df_closed[df_closed['ISWON'] == True]
win_rate = (len(won_opportunities) / len(df_closed)) * 100 if len(df_closed) > 0 else 0

# 7. Average Deal Size: Average AMOUNT for won opportunities (ISWON == True)
df_won = df[df['ISWON'] == True]
average_deal_size = df_won['AMOUNT'].mean() if len(df_won) > 0 else 0

# 8. Sales Cycle Duration: Average number of days between CREATEDDATE and CLOSEDATE for won opportunities
if len(df_won) > 0:
    sales_cycle = (df_won['CLOSEDATE'] - df_won['CREATEDDATE']).dt.days
    average_sales_cycle = sales_cycle.mean()
else:
    average_sales_cycle = None

# 9. Opportunities Past Close Date: Open opportunities (ISCLOSED == False) with CLOSEDATE in the past
past_close_opps = df_open[(df_open['CLOSEDATE'].notna()) & (df_open['CLOSEDATE'] < today)]
total_past_close_opps = len(past_close_opps)

# 10. Stage Distribution: Count of opportunities by STAGENAME
stage_distribution = df['STAGENAME'].value_counts()

# 11. Forecast Accuracy: Percentage of closed opportunities where FORECASTCATEGORYNAME is 'CLOSED'
accurate_forecasts = df_closed[df_closed['FORECASTCATEGORYNAME'].str.upper() == 'CLOSED']
forecast_accuracy = (len(accurate_forecasts) / len(df_closed)) * 100 if len(df_closed) > 0 else 0

# 12. Total number of open opportunities
total_open_opportunities = len(df_open)

# 13. Total number of Won opportunities
total_won_opportunities = len(df_won)

# 14. Total number of lost opportunities: Closed opportunities (ISCLOSED == True) where ISWON is False
lost_opportunities = df_closed[~df_closed['ISWON']]
total_lost_opportunities = len(lost_opportunities)

# Print the metrics
print("\n--- Opportunity KPIs ---")
print("Total Opportunities = ", total_opportunities)
print("Opportunity Status")
print(f"  Open = {total_open_opportunities} ({total_open_opportunities/total_opportunities*100:.1f}%)")
print(f"  Past Close Date = {total_past_close_opps} ({total_past_close_opps/total_opportunities*100:.1f}%)")
print(f"  Won = {total_won_opportunities} ({total_won_opportunities/total_opportunities*100:.1f}%)")
print(f"  Lost = {total_lost_opportunities} ({total_lost_opportunities/total_opportunities*100:.1f}%)")
print(f"  Win Rate = {win_rate:,.2f}%")
print("Sales Activity")
print(f"  No Activity = {total_blank_lastactivity} ({total_blank_lastactivity/total_opportunities*100:.1f}%)")
print(f"  >90 Days = {total_over_90_lastactivity} ({total_over_90_lastactivity/total_opportunities*100:.1f}%)")
print(f"  <90 Days = {total_within_90_lastactivity} ({total_within_90_lastactivity/total_opportunities*100:.1f}%)")
print(f"  No Next Step = {total_blank_nextstep} ({total_blank_nextstep/total_opportunities*100:.1f}%)")
print("Stats")
print(f"  Avg. Deal Size (Won) = ${average_deal_size:,.2f}")
print(f"  Avg. Sales Cycle (days to Won): {average_sales_cycle:,.2f}")
print(f"  Total Pipeline Value: ${pipeline_value:,.2f}")
print(f"  Weighted Pipeline Value: ${weighted_pipeline_value:,.2f}")

# print("\nStage Distribution:")
# print(stage_distribution)
# print("Forecast Accuracy (%):", forecast_accuracy)