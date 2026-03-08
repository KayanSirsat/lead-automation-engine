Project: AI-assisted Lead Automation for Website Agency

Goal:
Automate lead intelligence and outreach for cafés, business coaches, and immigration agencies.

System Structure:

Infrastructure:

sheets_client.py

llm_client.py

models.py

Agents:

website_extractor.py

website_audit_agent.py

outreach_agent.py

Workflows:

lead_workflow.py

Data Flow:

Load lead from "Lead Database" sheet.

Extract website content.

Audit website using LLM.

Generate leverage angle and personalized note.

Generate outreach subject + pitch.

Update:

Strategic angle sheet

Outreach tracking sheet

Failure Handling:

If website fetch fails → mark status "Website Error"

If JSON parsing fails → retry once

If still invalid → log error and skip

Upgrade Path:

Add async parallel execution

Add response classifier agent

Add mockup generation workflow

Migrate to graph-based orchestration later