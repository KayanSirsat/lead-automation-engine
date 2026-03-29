# CHANGELOG

All changes to this project are logged here by date.
Maintained by AI. Updated at end of each working session.

---

## [2026-02-23]

### Changed
- `index.html` — Edited hero section content: text replacements and line removal to clean up copy
- `index.html` — Inserted a new centered, small-font, low-opacity white text line below the hero statistics grid

---

## [2026-03-02]

### Added
- `models.py` — Created `LeadState` dataclass with full field set (lead info, outreach details, deal stages), including `from_dict()` and `to_dict()` serialization methods

---

## [2026-03-05]

### Changed
- `agents/website_audit_agent.py` — Refined the LLM audit prompt (`_AUDIT_PROMPT_TEMPLATE`) to focus on identifying a single, actionable conversion weakness; added confidence scoring guidance (1–10), structured output format enforcement, and clearer leverage angle + personalized note instructions

---

## [2026-03-07]

### Changed
- `index.html` — Removed heavy parallax and multi-transform scroll animations from the website mockup section; replaced with lightweight fade + small upward movement transitions for smoother scrolling performance

---

## [2026-03-08]

### Changed
- `lead_generation/engine.py` — Replaced static query list with `_generate_queries()`: dynamically generates 10–20 location-aware queries by combining niche synonyms with each area + city
- `lead_generation/google_maps_scraper.py` — Replaced fixed scroll loop with dynamic scroll logic: scrolls until listing count stabilizes across two consecutive checks or a safety cap is reached

---

## [2026-03-27]

### Added
- `CHANGELOG.md` — This file. Created to track all daily changes going forward
- `routes/jobs.py` — `POST /jobs`, `GET /jobs`, `GET /jobs/{id}` endpoints for pipeline job lifecycle management
- `routes/leads.py` — `GET /leads`, `GET /leads/{id}`, `GET /leads/{id}/audit`, `GET /leads/stats` endpoints
- `api.py` — FastAPI app with CORS middleware, lifespan logging, job and lead routers
- `job_runner.py` — Background thread-based pipeline runner: stages scraping → sheet write → website audit; job status polling
- `workflows/lead_workflow.py` — `write_leads_to_sheet()` with dedup, tier/revenue scoring, HYPERLINK formula cells; `run_lead_audit_workflow()` reads leads and writes audit results to Strategic Angle sheet
- `agents/website_extractor.py` — Scrapes title, meta description, headings, CTAs, navigation links, contact signals from any URL
- `.agents/agency_context.md` — Agency positioning context (niches: cafés, business coaches, immigration agencies; value props per niche; tone guidelines)

### Added
- `agents/outreach_agent.py` — LLM-powered cold email generator; niche-aware prompt (cafe, restaurant, business coach, immigration); reads audit weakness + leverage angle + personalized note; produces `subject_line` + `email_body`; two-attempt retry with JSON validation
- `workflows/lead_workflow.py` — `run_outreach_workflow()`: reads Strategic Angle sheet, skips already-drafted leads, calls `generate_outreach()`, writes results to `Outreach Drafts` sheet (columns: Lead ID, Company Name, Niche, Subject Line, Email Body, Generated At, Status)
- `routes/leads.py` — `POST /leads/{lead_id}/outreach`: fetches lead + audit, generates draft, persists to sheet, returns draft JSON
- `job_runner.py` — Stage 4 "Generating outreach drafts" added to pipeline; `leads_outreached` counter added to `JobStatus`

---

## [2026-03-28]

### Fixed
- `routes/leads.py` — Removed dead duplicate `@router.get("/stats")` handler (`_stats_alias`) that always returned `None`. Confirmed correct route ordering so FastAPI resolves static paths before parametric ones: `GET /stats` → `GET /` → `GET /{lead_id}` → `GET /{lead_id}/audit` → `POST /{lead_id}/outreach`

### Changed
- `index.html` — Added 4th pipeline stage `"Generating outreach drafts"` (✉️) to the `STAGES` array in `PipelineStatus`
- `index.html` — Added `Outreached` counter (sourced from `detail.leads_outreached`) to the job detail panel alongside Found / Written / Audited
- `index.html` — Added `Outreached` counter (sourced from `job.leads_outreached`) to `JobRow` card counts
- `index.html` — Added **Outreach Draft** section to `LeadModal`: `✉️ Generate Draft` button calls `POST /leads/{id}/outreach`, displays `subject_line` and `email_body`, and supports regeneration
- `lead_generation/engine.py` — Added 8 new niche entries to `_NICHE_SYNONYMS`: immigration consultant, architect, interior designer, CA firm, law firm, dentist, real estate, wedding photographer
- `index.html` — Expanded `NICHES` dropdown in `FindLeads` to 12 entries; updated pipeline info text to include query expansion and outreach draft stages

---

## [2026-03-28] (continued)

### Added
- gents/contact_enricher.py -- Waterfall email enrichment module; 5-source waterfall (website scrape, Instagram bio, Google search, Hunter.io, Prospeo); each source in try/except; email skip list; result written into lead[chr(34)+chr(34)+chr(34)+chr(101)+chr(109)+chr(97)+chr(105)+chr(108)+chr(34)+chr(34)+chr(34)] in-place; load_dotenv() at top.

## [2026-03-29]

### Added
- `workflows/lead_workflow.py` -- Added `run_enrichment_workflow() -> int`:
  - Reads all rows from Lead Database sheet
  - Skips leads that already have a Personal Email value
  - Calls `enrich_contact()` (5-source waterfall) for each unenriched lead
  - On success, writes the email to column N (Personal Email) via targeted single-cell Sheets API update
  - Returns count of leads successfully enriched
- `workflows/lead_workflow.py` -- Added import for `enrich_contact` from `agents.contact_enricher`
- `workflows/lead_workflow.py` -- Added imports of `_get_sheets`, `_sheet_id` from `sheets_client` for targeted cell writes

### Added
- `routes/leads.py` -- Added `POST /leads/{lead_id}/enrich` endpoint:
  - Fetches lead from Lead Database sheet
  - If Personal Email exists, returns it immediately
  - Calls `enrich_contact(lead)` to start the waterfall enrichment process
  - Returns the newly found email or a 404 error if none is found

### Added
- `job_runner.py` -- Added `leads_enriched` to `JobStatus` and wired up Phase 5: `Enriching contact details` using the new `run_enrichment_workflow()` function.
- `index.html` -- Added `Enriching contact details` stage to the PipelineStatus dashboard widget, including updated counters for `JobRow` and job detail panes.
- `index.html` -- Added `🔍 Find Email` button to the `LeadModal` to fetch enhanced contact enrichment for a lead manually from the `/leads/{id}/enrich` route.
