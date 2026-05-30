# Bhookle Investment Lead Tracker - Architecture & Implementation Guide

## Project Overview

Bhookle is a Flask-based investment lead management system that tracks potential investors (angels, VCs, PE firms, family offices) and facilitates outreach through AI-powered email personalization and bulk sending via Gmail API.

**Key Capabilities:**
- Track investment leads with investor profile, investment history, and outreach status
- Manage email templates with attachments
- Generate AI-customized email variations per lead using Claude
- Send emails via Gmail OAuth2 (no password required)
- Bulk send to multiple leads with per-lead personalization
- Auto-update lead notes and status after sending

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Backend Framework** | Flask 2.x + Flask-SQLAlchemy |
| **Database** | SQLite (Flask-SQLAlchemy ORM) |
| **Frontend** | Vanilla JavaScript + HTML5 + CSS3 |
| **Email Delivery** | Gmail API (OAuth2) |
| **AI Personalization** | Anthropic Claude API (Sonnet model) |
| **Authentication** | Google OAuth2 (Gmail scope) |
| **File Handling** | UUID-based attachment storage in static/attachments/ |

---

## Project Structure

```
BhookleDev/
├── app.py                      # Main Flask application & route handlers
├── database.py                 # SQLAlchemy models (InvestmentLead, EmailTemplate)
├── scraper.py                  # Web scraping & AI utilities (generate_email_draft)
├── templates/
│   └── index.html              # Single-page frontend (modals, tables, bulk UI)
├── static/
│   ├── styles.css              # All styles (responsive design, modals, bulk bar)
│   └── attachments/            # Uploaded email attachments (UUID-named files)
├── .env                        # Environment variables (ANTHROPIC_API_KEY)
├── gmail_token.json            # OAuth2 token (created after Gmail auth flow)
├── credentials.json            # Google Cloud OAuth credentials (user-provided)
├── database.db                 # SQLite database
└── CLAUDE.md                   # This file

```

---

## Database Schema

### `InvestmentLead` Model
Stores investor profiles and outreach tracking.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Unique identifier |
| `investor_name` | String(200) | Name of investor (required) |
| `investor_type` | String(100) | Angel / PE / VC / Family Office |
| `invested_company` | String(200) | Company they invested in (required) |
| `investment_amount` | String(100) | Amount invested (e.g., "$5M", "₹2Cr") |
| `round_type` | String(100) | Seed / Series A / Series B / etc. |
| `sector` | String(200) | Cloud Kitchen / Agritech / SaaS / etc. |
| `deal_date` | String(50) | Date of investment (YYYY-MM-DD format) |
| `key_contact` | String(200) | Primary contact person name |
| `email` | String(200) | Contact email (required for sending) |
| `linkedin` | String(500) | LinkedIn profile URL |
| `source_url` | String(1000) | Original source of lead (article, crunchbase, etc.) |
| `status` | String(50) | New / Reached Out / Engaged / Didn't Respond / Not Interested |
| `recent_investments` | Text | Comma-separated list (e.g., "Startup A ($2M), Startup B (₹5Cr)") |
| `follow_up_date` | String(20) | Date for follow-up reminder |
| `notes` | Text | Internal notes; auto-appended with "Email sent on YYYY-MM-DD HH:MM" |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Last modification timestamp |

### `EmailTemplate` Model
Reusable email templates for personalization.

| Column | Type | Description |
|--------|------|-------------|
| `id` | Integer (PK) | Unique identifier |
| `name` | String(200) | Template name (e.g., "Initial Outreach") |
| `subject` | String(500) | Email subject line (can include placeholders) |
| `body` | Text | Email body text (can include placeholders) |
| `attachment_path` | String(500) | File system path to attachment (UUID-named) |
| `attachment_name` | String(200) | Original filename for display to user |
| `created_at` | DateTime | Record creation timestamp |
| `updated_at` | DateTime | Last modification timestamp |

---

## API Endpoints

### Lead Management

#### `GET /`
Returns HTML index page with lead table, modals, and bulk UI.

#### `GET /api/leads`
Fetches all investment leads.

**Response:**
```json
{
  "leads": [
    {
      "id": 1,
      "investor_name": "Rahul Sharma",
      "investor_type": "Angel",
      "invested_company": "Swiggy",
      "email": "rahul@example.com",
      "status": "New",
      "notes": "...",
      "created_at": "2025-01-15T10:30:00"
    },
    ...
  ]
}
```

#### `GET /api/leads?search=<query>`
Searches leads by name, company, or email (case-insensitive substring match).

#### `POST /api/leads`
Creates new investment lead.

**Request:**
```json
{
  "investor_name": "Priya Patel",
  "investor_type": "VC",
  "invested_company": "Zerodha",
  "email": "priya@vc.com",
  "linkedin": "https://linkedin.com/in/priya",
  "sector": "Fintech",
  "deal_date": "2024-06-15",
  "source_url": "https://techcrunch.com/...",
  "investment_amount": "$3M",
  "round_type": "Series A",
  "key_contact": "Priya Patel"
}
```

#### `PUT /api/lead/<id>`
Updates a lead (any field).

**Request:**
```json
{
  "status": "Engaged",
  "notes": "Interested in follow-up call next week"
}
```

#### `DELETE /api/lead/<id>`
Deletes a lead.

#### `POST /api/lead/<id>/enrich`
Fetches additional investor data via web scraping + Claude.

**Response:**
```json
{
  "ok": true,
  "recent_investments": "Startup A ($2M), Startup B (₹5Cr)",
  "notes": "Active in fintech; led 3 rounds in 2024"
}
```

---

### Email Templates

#### `GET /api/templates`
Fetches all email templates with attachment metadata.

**Response:**
```json
{
  "templates": [
    {
      "id": 1,
      "name": "Initial Outreach",
      "subject": "Bhookle - Cloud Kitchen Intelligence Platform",
      "body": "Hi {investor_name},\n\nI came across your investment in {invested_company}...",
      "attachment_name": "Bhookle_Pitch_Deck.pdf",
      "created_at": "2025-01-10T14:22:00"
    },
    ...
  ]
}
```

#### `POST /api/templates`
Creates new email template.

**Request:**
```json
{
  "name": "Follow-up",
  "subject": "Following up - Bhookle",
  "body": "Hi {investor_name},\n\nI wanted to follow up on my previous email..."
}
```

#### `PUT /api/templates/<id>`
Updates template name, subject, or body.

**Request:**
```json
{
  "name": "Updated Name",
  "subject": "Updated subject",
  "body": "Updated body text"
}
```

#### `DELETE /api/templates/<id>`
Deletes template.

#### `POST /api/templates/<id>/attachment`
Uploads file attachment to template.

**Request:** Multipart form-data with `file` field
- File stored with UUID name in `static/attachments/`
- Original filename saved in DB as `attachment_name`
- Previous attachment automatically deleted

#### `DELETE /api/templates/<id>/attachment`
Removes attachment from template.

---

### Email Draft & Send

#### `POST /api/lead/<id>/draft-email`
Generates AI-personalized email draft using Claude.

**Request:**
```json
{
  "template_id": 1
}
```

**Response:**
```json
{
  "ok": true,
  "subject": "Bhookle - Cloud Kitchen Intelligence Platform",
  "body": "Hi Rahul,\n\nI came across your investment in Swiggy..."
}
```

**Personalization Strategy:**
- Extracts template subject/body
- Inserts lead context: investor_name, investor_type, invested_company, sector
- Claude Sonnet generates variation **preserving founder's exact tone, voice, sentence length, and energy**
- References portfolio companies when possible
- Avoids clichés unless present in original template

#### `POST /api/lead/<id>/send-email`
Sends email via Gmail API and updates lead status.

**Request:**
```json
{
  "to_email": "rahul@example.com",
  "subject": "Bhookle - Cloud Kitchen Intelligence Platform",
  "body": "Hi Rahul,\n\nI came across...",
  "template_id": 1
}
```

**Response:**
```json
{
  "ok": true,
  "message_id": "gmail_message_id_...",
  "status_updated": "Reached Out",
  "notes_updated": "Email sent on 2025-01-21 14:30"
}
```

**Side Effects:**
- Sends email via authenticated Gmail API
- Updates lead `status` to "Reached Out"
- Appends to lead `notes`: "Email sent on YYYY-MM-DD HH:MM"
- Updates `updated_at` timestamp

---

### Bulk Send

#### `POST /api/bulk-send`
Sends personalized emails to multiple leads in one request.

**Request:**
```json
{
  "lead_ids": [1, 3, 5],
  "template_id": 2
}
```

**Response:**
```json
{
  "ok": true,
  "sent": 3,
  "total": 3,
  "results": [
    {
      "lead_id": 1,
      "investor_name": "Rahul Sharma",
      "email": "rahul@example.com",
      "success": true,
      "message_id": "...",
      "notes_updated": "Email sent on 2025-01-21 14:35"
    },
    {
      "lead_id": 3,
      "investor_name": "Priya Patel",
      "email": "priya@vc.com",
      "success": true,
      "message_id": "...",
      "notes_updated": "Email sent on 2025-01-21 14:36"
    },
    ...
  ]
}
```

**Behavior:**
- Validates template exists
- Validates Gmail is connected
- For each lead:
  1. Calls `generate_email_draft()` (Claude personalization)
  2. Calls `_send_via_gmail()` (sends email)
  3. Calls `_mark_sent()` (updates lead status/notes)
  4. Records result
- Returns aggregated results
- Processing is synchronous (~1-2 seconds per lead)
- Progress visible in real-time via progress modal

---

### Gmail Authentication

#### `GET /api/gmail/status`
Checks if Gmail is connected.

**Response:**
```json
{
  "connected": true,
  "has_credentials_json": true
}
```

#### `GET /api/gmail/auth`
Initiates Gmail OAuth2 flow.

**Flow:**
1. Generates OAuth state token (stored in session)
2. Redirects to Google login page with GMAIL_REDIRECT callback URL
3. User authorizes "Bhookle" to access Gmail
4. Google redirects to `/api/gmail/callback`

#### `GET /api/gmail/callback?code=<auth_code>&state=<state>`
Handles OAuth callback after user authorization.

**Flow:**
1. Verifies state token matches session
2. Exchanges auth_code for refresh_token + access_token
3. Saves credentials to `gmail_token.json`
4. Redirects to home page

#### `POST /api/gmail/disconnect`
Removes Gmail connection.

**Side Effects:**
- Deletes `gmail_token.json`
- User must re-authenticate to send emails

---

## Frontend Architecture

### Single-Page Layout (`templates/index.html`)

The frontend is a single HTML file with embedded CSS and JavaScript implementing modals, inline table updates, and bulk actions.

#### Key UI Elements

1. **Lead Table**
   - Columns: Checkbox, Name, Investor Type, Company, Sector, Status, Email, Recent Investments, Actions
   - Row-level actions: View/Edit, Send Email, Delete
   - Status/Notes are inline-editable (no refresh required)
   - Responsive design with horizontal scroll on mobile

2. **Gmail Connection Pill** (top-right header)
   - Green "✓ Gmail Connected" if authorized
   - Red "✗ Gmail Not Connected" if not
   - Clickable: connect/disconnect flow
   - Shows setup instructions if credentials.json missing

3. **Bulk Selection Bar** (fixed at bottom)
   - Appears when ≥1 lead is checked
   - Shows: "3 leads selected"
   - Template selector dropdown
   - "🚀 Send AI Emails" button (triggers bulk send)
   - Clear selection button

4. **Email Draft Modal**
   - Pre-fills investor info (name, type, company, sector)
   - Template selector with "Generate AI Draft" button
   - Subject + Body fields for manual editing
   - "📤 Send Email" button
   - Real-time validation (shows "Gmail not connected" error)

5. **Email Templates Modal**
   - List of saved templates with preview
   - Create new template with inline form
   - Edit/delete buttons per template
   - File upload for attachment
   - Attachment deletion UI

6. **Bulk Send Progress Modal**
   - Spinner during processing
   - Results list upon completion
   - Shows per-lead success/failure with lead name and email
   - Auto-updates row status/notes in background

#### Modal Management

| Modal | Trigger | Purpose |
|-------|---------|---------|
| Add Lead | "➕ Add Lead" button | Create new investment lead |
| Lead Details | Row actions | View/edit lead details inline |
| Email Draft | Row "✉️" button | Draft & send email to single lead |
| Email Templates | "📧 Email Templates" button | Manage templates & attachments |
| Bulk Send Progress | "🚀 Send AI Emails" button | Monitor bulk send progress |

#### Global State Variables

```javascript
// Lead data
_leads = []                    // All loaded leads
_filteredLeads = []            // Search results

// Gmail OAuth state
_gmailConnected = false        // Is Gmail authorized?

// Template state
_templates = []                // All saved templates
_draftLeadId = null            // Current lead being drafted
_draftTemplateId = null        // Current template being used
```

---

## Key Features & Implementation

### 1. AI Email Personalization

**Function:** `generate_email_draft()` in `scraper.py`

**Input:**
- Investor profile: name, type, company, sector
- Template: subject, body

**Process:**
1. Constructs Claude prompt emphasizing:
   - Preserve exact founder voice and tone
   - Reference their portfolio company
   - Keep length similar to template
   - Avoid clichés unless in original
2. Calls Claude Sonnet with temperature=0.7 (balanced creativity + consistency)
3. Extracts subject + body from response
4. Returns personalized draft

**Example:**
```
Template: "Hi {investor_name}, I came across your investment in {invested_company}..."
Claude Output: "Hi Rahul, I came across your investment in Swiggy and noticed..."
```

### 2. Gmail OAuth2 Integration

**No Passwords Required** — Uses Google's OAuth2 with refresh tokens

**Setup (one-time):**
1. Create Google Cloud project
2. Enable Gmail API
3. Create OAuth 2.0 Client ID (Web Application)
4. Download credentials.json
5. Place in project root: `/Users/arvind/Documents/BhookleDev/credentials.json`

**Flow:**
1. User clicks Gmail pill (if not connected)
2. Redirects to Google login
3. User grants permission
4. Credentials saved to `gmail_token.json` (never shared)
5. All future sends use refresh token (automatic renewal)

**Helper Functions:**
- `_gmail_service()` — Creates authenticated Gmail API service
- `_build_mime()` — Builds MIME message with optional attachment
- `_send_via_gmail()` — Sends via Gmail API
- `_mark_sent()` — Updates lead status + notes after send

### 3. Bulk Sending with Per-Lead Personalization

**Endpoint:** `POST /api/bulk-send`

**Flow:**
1. User selects leads (checkboxes) + template
2. Clicks "🚀 Send AI Emails"
3. Progress modal opens
4. For each lead:
   - Claude personalizes template
   - Gmail API sends email
   - Lead status → "Reached Out"
   - Lead notes appended with "Email sent on ..."
5. Results displayed in modal
6. Table rows updated in real-time

**Performance:**
- ~1-2 seconds per lead (Claude + Gmail)
- 10 leads ≈ 15-20 seconds
- Synchronous processing (no timeout issues with Flask)

### 4. Attachment Management

**Upload Flow:**
1. User selects file in template modal
2. File uploaded to `static/attachments/`
3. UUID-based filename stored in DB
4. Original filename displayed to user

**Send Flow:**
1. When email sent, attachment fetched from disk
2. Base64-encoded into MIME
3. Sent as email attachment via Gmail API
4. Filename preserved (original name shown in email)

**Security:**
- UUID naming prevents path traversal
- Static directory isolation
- No execution of uploaded files

### 5. Inline Row Updates

**Status & Notes Fields:**
- Rendered as select/textarea in table rows
- Changes saved immediately via `PUT /api/lead/<id>`
- No page refresh required
- Auto-updated after bulk sends

---

## Environment Variables

**File:** `.env` (must be in project root)

```
ANTHROPIC_API_KEY=sk-ant-...        # Claude API key from console.anthropic.com
```

**Optional (auto-generated):**
- `gmail_token.json` — OAuth2 credentials (created after Gmail auth flow)
- `credentials.json` — Google Cloud credentials (must be placed manually by user)

---

## Setting Up Gmail OAuth (First-Time)

### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: "Bhookle" (or your preference)
3. Enable Gmail API: Search "Gmail API" → Click "Enable"

### Step 2: Create OAuth Client
1. Go to APIs & Services → Credentials
2. Click "Create Credentials" → OAuth 2.0 Client ID
3. Application type: Web application
4. Add authorized redirect URI: `http://127.0.0.1:5050/api/gmail/callback`
5. Download JSON file

### Step 3: Configure Bhookle
1. Copy downloaded JSON to project root: `credentials.json`
2. Restart Flask server
3. Click Gmail pill in app → "Connect Gmail"
4. Authorize access to Gmail

### Verify:
- Gmail pill shows "✓ Gmail Connected" (green)
- Templates appear in email draft modal
- Can send test email

---

## Running the Application

### Prerequisites
```bash
pip install flask flask-sqlalchemy anthropic google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client beautifulsoup4 requests
```

### Start Server
```bash
python app.py
```

Server runs at `http://127.0.0.1:5050`

### Database Initialization
- SQLite database auto-created on first run
- Tables auto-initialized from `database.py` models

---

## Troubleshooting

### "Gmail Not Connected" when trying to send
**Cause:** `credentials.json` missing or OAuth not completed
**Fix:** 
1. Verify `credentials.json` exists in project root
2. Click Gmail pill → "Connect Gmail"
3. Complete Google authorization flow

### Email send fails silently
**Cause:** Gmail API quota exceeded or network error
**Check:** Browser console for error messages
**Fix:** 
- Wait 1 minute, retry
- Check Google Cloud Console for API errors

### "Invalid email" error when creating lead
**Cause:** Email field is empty
**Fix:** Provide valid email address in lead form

### Claude draft generation takes >10 seconds
**Cause:** Claude API latency (rare)
**Fix:** Retry; if persistent, check ANTHROPIC_API_KEY in .env

### Attachment not uploaded
**Cause:** File size > browser limits or permissions issue
**Fix:** 
- Use files < 25MB
- Check browser console for errors
- Try different file format

---

## Future Enhancements

1. **LinkedIn Outreach** — Draft & send LinkedIn messages alongside emails
2. **Email Analytics** — Track open rates, click tracking via Gmail API
3. **Scheduled Sends** — Send emails at optimal times per investor timezone
4. **Template Variables** — Support dynamic fields beyond {investor_name}
5. **Multi-User Support** — User authentication + role-based access
6. **CRM Integration** — Sync with Pipedrive, HubSpot, etc.
7. **Enrichment API** — Real-time investor data from external sources
8. **Dashboard** — Stats on outreach rates, response rates, engagement timeline

---

## Code Contributors & Documentation

- **Backend:** Flask routes, Gmail OAuth, email sending logic
- **Database:** SQLAlchemy models (InvestmentLead, EmailTemplate)
- **AI:** Claude Sonnet integration for email personalization
- **Frontend:** Vanilla JS with modals, bulk UI, inline editing
- **Documentation:** This file (CLAUDE.md)

---

## Support & Questions

For detailed implementation questions, refer to:
- **API Routes:** `app.py` (organized by feature: leads, templates, gmail, email)
- **Database Models:** `database.py` (InvestmentLead, EmailTemplate)
- **AI Prompts:** `scraper.py` (generate_email_draft function)
- **Frontend Logic:** `templates/index.html` (JS functions for modals, bulk UI)

---

**Last Updated:** 2025-01-21  
**Version:** 1.0  
**Status:** Production-ready with Gmail OAuth, bulk email, AI personalization
