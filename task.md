# Lead Automation Engine — Master Task List

## Phase 1 — Complete the Core Loop
- [x] Lead generation via Google Maps scraper
- [x] Dynamic scroll logic (stabilize-before-stop)
- [x] Location-aware query generation with niche synonyms
- [x] Lead normalization + scoring + deduplication
- [x] Zomato enrichment hook
- [x] Instagram finder hook
- [x] Write leads to Google Sheets (Lead Database)
- [x] Website extractor ([website_extractor.py](file:///d:/Kayan/Freelancing/automation/lead_automation/agents/website_extractor.py))
- [x] Website audit agent with LLM prompt ([website_audit_agent.py](file:///d:/Kayan/Freelancing/automation/lead_automation/agents/website_audit_agent.py))
- [x] Write audit results to Strategic Angle sheet
- [x] FastAPI backend ([api.py](file:///d:/Kayan/Freelancing/automation/lead_automation/api.py), [routes/jobs.py](file:///d:/Kayan/Freelancing/automation/lead_automation/routes/jobs.py), [routes/leads.py](file:///d:/Kayan/Freelancing/automation/lead_automation/routes/leads.py))
- [x] Background job runner with thread-based pipeline
- [x] Frontend dashboard ([index.html](file:///d:/Kayan/Freelancing/automation/lead_automation/index.html))
- [x] **[outreach_agent.py](file:///d:/Kayan/Freelancing/automation/lead_automation/agents/outreach_agent.py)** — generate personalized cold email from audit result
- [x] [run_outreach_workflow()](file:///d:/Kayan/Freelancing/automation/lead_automation/workflows/lead_workflow.py#207-285) in [lead_workflow.py](file:///d:/Kayan/Freelancing/automation/lead_automation/workflows/lead_workflow.py) — read Strategic Angle, call agent, write to `Outreach Drafts` sheet
- [x] `POST /leads/{id}/outreach` API route — trigger per-lead outreach generation
- [x] Plug outreach stage into [job_runner.py](file:///d:/Kayan/Freelancing/automation/lead_automation/job_runner.py) pipeline (Stage 4)

## Phase 2 — Contact Enrichment (FullEnrich-style)
- [x] `agents/contact_enricher.py` — 5-source waterfall enricher (website scrape -> Instagram bio -> Google search -> Hunter.io -> Prospeo)
- [x] Parse Instagram bio for phone/email signals -- handled inside `contact_enricher.py` Source 2
- [x] Write enriched contact details back to Lead Database sheet -- done via run_enrichment_workflow()
- [x] Expose `POST /leads/{id}/enrich` API route
- [x] Plug enrichment stage into `job_runner.py` pipeline (Stage 5) and dashboard

## Phase 3 — Phone Outreach & Call Scripts (New)
- [x] Owner name discovery waterfall (`agents/contact_enricher.py`)
- [x] Structured call script generator (`agents/outreach_agent.py`)
- [x] Fallback audit generation for leads without websites (`workflows/lead_workflow.py`)
- [x] `POST /leads/{lead_id}/call-script` API route with sheet persistence
- [x] Plug call script generation into `job_runner.py` pipeline (Stage 6)
- [x] Frontend Call Script UI in LeadModal and job dashboard
- [x] Connected dynamic API limit chunking to Maps Scraper
- [x] Addressed Gemini TPM/RPM token limits logically in llm_client.py
- [x] Added debug API endpoints (/sync/) for raw stage polling
- [x] Inserted Call Scripts stage into PipelineStatus STAGES array

## Phase 4 — Outreach Delivery
- [x] Email sender module (SMTP or SendGrid) — `agents/email_sender.py`
- [x] `run_outreach_delivery_workflow()` in `workflows/lead_workflow.py`
- [x] `POST /leads/{lead_id}/send-email` API route — send single lead email
- [x] `POST /leads/sync/delivery` API route — bulk send all pending drafts
- [x] Mark draft status as "Sent" in Outreach Drafts sheet after send
- [x] Update `.env.example` with email configuration variables
- [x] Follow-up sequence logic (trigger after N days if no reply) — run_followup_workflow() in lead_workflow.py + POST /leads/sync/followup route
- [ ] Reply tracking integration

## Phase 5 — Dashboard Polish
- [x] Pipeline funnel visualization (scrape → audit → outreach → contacted → replied → closed) with conversion % and proportional bar heights
- [x] Per-niche stats chart (horizontal bar chart, client-side grouping, sorted by count)
- [ ] Per-city stats chart
- [x] Lead filter UI (tier, city, niche, audit confidence score)
- [ ] Live job log display improvements

## Phase 6 — Infrastructure & Scale (Planned)
- [ ] Migrate from Google Sheets to Supabase (PostgreSQL)
- [ ] Follow-up reply tracking via Gmail API or SendGrid webhooks
- [ ] A/B testing for subject lines
- [ ] Bounce rate tracking
- [ ] Sending rate limits and daily cap controls
- [ ] Multi-user support (per-user sheet / DB isolation)
