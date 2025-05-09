import json

def get_attribution_prompt(audit_results: dict) -> str:
    """Generate the prompt for attribution analysis.
    
    Args:
        audit_results: Dictionary containing the audit results
        
    Returns:
        Formatted prompt string for OpenAI
    """
    return f"""Please analyze the following Salesforce Marketing Attribution Audit results and provide insights and recommendations:

Company: {audit_results.get('company_name', 'Unknown')}

1. Campaign Influence Status:
- Enabled: {audit_results.get('campaign_influence_enabled', False)}

2. Installed Attribution Packages:
{json.dumps(audit_results.get('installed_packages', {}), indent=2)}

3. Custom Schema Matches:
{json.dumps(audit_results.get('custom_schema_matches', {}), indent=2)}

4. Attribution Custom Objects:
{json.dumps(audit_results.get('attribution_custom_objects', []), indent=2)}

5. Report and Dashboard Usage:
{json.dumps(audit_results.get('report_dashboard_usage', {}), indent=2)}

6. Apex References:
{json.dumps(audit_results.get('apex_references', {}), indent=2)}

7. Flow References:
{json.dumps(audit_results.get('flow_references', {}), indent=2)}

8. Campaign Member Statuses:
{json.dumps(audit_results.get('campaign_member_statuses', {}), indent=2)}

9. Campaign Type Values:
{json.dumps(audit_results.get('campaign_type_values', {}), indent=2)}

Please provide:
1. A summary of the current attribution setup
2. Key findings and potential gaps
3. Recommendations for improvement
4. Best practices that could be implemented
"""

def get_system_prompt() -> str:
    """Get the system prompt for attribution analysis.
    
    Returns:
        System prompt string for OpenAI
    """
    return "You are a Salesforce Marketing Attribution expert. Analyze the provided audit results and give detailed, actionable insights." 