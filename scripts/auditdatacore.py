import time
import sys
from datetime import datetime

def run_script(script_name):
    print(f"\n{'='*50}")
    print(f"Running {script_name}...")
    print(f"{'='*50}\n")
    
    start_time = time.time()
    try:
        # Import the module dynamically
        module = __import__(script_name)
        # Run the script
        print(f"\nCompleted {script_name} in {time.time() - start_time:.2f} seconds")
        return True
    except Exception as e:
        print(f"Error running {script_name}: {str(e)}")
        return False

def main():
    print(f"\nStarting Audit Data Core at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("This script will run all audit scripts in sequence.\n")
    
    # List of scripts to run in order
    scripts = [
        'AccountAudit',
        'ContactAudit',
        'LeadAudit',
        'OpportunityAudit',
        'EventAudit'
    ]
    
    # Track success/failure
    results = []
    
    # Run each script
    for script in scripts:
        success = run_script(script)
        results.append((script, success))
    
    # Print summary
    print(f"\n{'='*50}")
    print("Audit Summary:")
    print(f"{'='*50}")
    
    for script, success in results:
        status = "✓ Success" if success else "✗ Failed"
        print(f"{script}: {status}")
    
    print(f"\nCompleted all audits at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 