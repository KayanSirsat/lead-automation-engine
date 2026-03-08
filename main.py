print("MAIN LOADED")
from workflows.lead_workflow import run_lead_audit_workflow
print("WORKFLOW LOADED")

def main() -> None:
    print("STARTING WORKFLOW")
    run_lead_audit_workflow()
    print("WORKFLOW FINISHED")


if __name__ == "__main__":
    main()