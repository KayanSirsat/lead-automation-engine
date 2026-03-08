Workflow 1: Lead Intelligence Engine

Trigger:
Lead exists without "Primary Website Weakness".

Steps:

Website Extractor Agent

Website Audit Agent

Update Strategic Angle sheet

Workflow 2: Outreach Execution Engine

Trigger:
Confidence score >= 6 AND not yet contacted.

Steps:

Outreach Agent

Update Outreach Tracking sheet

Set Date first contacted

Set Subject line used

Set Pitch version

Future Workflow: Mockup Generator

Trigger:
Lead replies positively.

Steps:

Branding Analyzer Agent

Homepage Structure Planner

Copy Generator

HTML Skeleton Generator

All workflows must:

Accept lead_id

Operate deterministically

Update only relevant sheets