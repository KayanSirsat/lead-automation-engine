# Lead Automation Engine

An automated pipeline for generating, enriching, and scoring business leads.

## Overview

This project builds a complete lead generation workflow that collects raw business data, processes it, and produces structured, high-quality leads ready for outreach or CRM systems.

## Pipeline

Input → Scraping → Enrichment → Scoring → AI Website Audit → Outreach Drafts → Call Scripts → Sheets Output

### 1. Scraping

* Collects business data from online sources
* Extracts key fields like name, contact details, and location

### 2. Cleaning

* Removes duplicates and invalid entries
* Standardizes formats (phone numbers, names, etc.)

### 3. Enrichment

* Adds missing data using external sources/APIs
* Improves lead quality with additional attributes

### 4. Scoring

* Assigns scores based on predefined criteria
* Helps prioritize high-value leads


### 5. AI Website Audit
* Uses Gemini 2.5 Flash to read and analyze scraped websites
* Identifies actionable weaknesses for sales pitches

### 6. Outreach Generation & Call Scripts
* Generates highly personalized cold email drafts
* Crafts dynamic 5-part cold calling scripts (opener, hook, custom objections)

### 7. Output

* Exports structured data (CSV / Google Sheets)

## Example Output

| Name     | Phone      | Rating            | Lead Score |
| -------- | ---------- | ----------------- | ---------- |
| ABC Corp | 9876543210 | 4.5 (120 reviews) | High       |

## Tech Stack

* Python
* Web Scraping
* APIs
* Data Processing

## How to Run

```bash
git clone https://github.com/KayanSirsat/lead-automation-engine
cd lead-automation-engine
pip install -r requirements.txt
python main.py
```

## Future Improvements

* Better scoring models
* Real-time pipeline execution
* Integration with CRM systems
