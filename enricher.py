"""
Enriches investment leads with missing email / LinkedIn by:
  1. Searching DuckDuckGo for each contact
  2. Passing results to Claude to extract structured contact info
  3. Writing back to the SQLite DB

Run: python3 enricher.py [--limit N] [--dry-run]
"""

import sys
import re
import time
import argparse
import warnings
warnings.filterwarnings("ignore")

import requests
from bs4 import BeautifulSoup
import anthropic

from app import app
from database import db, InvestmentLead

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+/?")


def ddg_search(query: str, max_results: int = 6) -> list[dict]:
    """Scrape DuckDuckGo HTML results — no API key needed."""
    url = "https://html.duckduckgo.com/html/"
    try:
        resp = requests.post(
            url,
            data={"q": query, "b": "", "kl": "us-en"},
            headers=HEADERS,
            timeout=12,
        )
        soup = BeautifulSoup(resp.text, "lxml")
        results = []
        for r in soup.select(".result")[:max_results]:
            title_el = r.select_one(".result__title")
            snippet_el = r.select_one(".result__snippet")
            url_el = r.select_one(".result__url")
            results.append({
                "title":   title_el.get_text(strip=True) if title_el else "",
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                "url":     url_el.get_text(strip=True) if url_el else "",
            })
        return results
    except Exception as e:
        print(f"    [ddg] Error: {e}")
        return []


def fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """Fetch a page and return visible text, truncated."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:max_chars]
    except Exception:
        return ""


def extract_with_claude(client: anthropic.Anthropic, lead: InvestmentLead, search_snippets: list[dict]) -> dict:
    """Ask Claude to extract email + LinkedIn from search results."""
    snippets_text = "\n".join(
        f"[{i+1}] Title: {r['title']}\n     URL: {r['url']}\n     Snippet: {r['snippet']}"
        for i, r in enumerate(search_snippets)
    )

    # Build the first contact name (take first from comma-separated list)
    first_contact = lead.key_contact.split(",")[0].strip() if lead.key_contact else ""

    prompt = f"""You are a B2B contact research assistant. Extract contact information from these search results.

Target:
- Firm: {lead.investor_name}
- Contact person: {first_contact or "any senior person at the firm"}
- Context: Indian venture capital / investment firm

Search results:
{snippets_text}

Extract:
1. linkedin_url — The LinkedIn profile URL of {first_contact or "the most senior contact at this firm"}. Must be in format https://www.linkedin.com/in/... — if you find a company page instead, return that under company_linkedin. Return "" if not found.
2. email — A valid professional email address for {first_contact or "anyone at this firm"}. Return "" if not found.
3. company_linkedin — The firm's LinkedIn company page URL (linkedin.com/company/...). Return "" if not found.
4. confidence — "high", "medium", or "low"

Rules:
- Only return URLs you actually see in the search results above. Do NOT hallucinate or guess URLs.
- Prefer results from linkedin.com directly.
- Return JSON only, no explanation.

Example:
{{"linkedin_url": "https://www.linkedin.com/in/john-doe/", "email": "john@firm.com", "company_linkedin": "https://www.linkedin.com/company/firm/", "confidence": "high"}}"""

    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        import json
        return json.loads(raw.strip())
    except Exception as e:
        print(f"    [claude] Extraction error: {e}")
        return {}


def validate_linkedin(url: str) -> str:
    """Normalise and basic-validate a LinkedIn URL."""
    if not url:
        return ""
    url = url.strip().rstrip("/")
    if "linkedin.com/in/" in url or "linkedin.com/company/" in url:
        if not url.startswith("http"):
            url = "https://" + url
        return url
    return ""


def validate_email(email: str) -> str:
    if not email:
        return ""
    email = email.strip().lower()
    if EMAIL_RE.fullmatch(email):
        return email
    # try extracting from string
    found = EMAIL_RE.search(email)
    return found.group() if found else ""


# ── Main enrichment loop ───────────────────────────────────────────────────────

def enrich(limit: int = None, dry_run: bool = False):
    import os
    api_key = os.getenv("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key) if api_key else None
    if not client:
        print("Note: ANTHROPIC_API_KEY not set — running regex-only mode (no Claude fallback)\n")

    with app.app_context():
        query = InvestmentLead.query.filter(
            db.or_(
                InvestmentLead.email == "",
                InvestmentLead.email == None,
                InvestmentLead.linkedin == "",
                InvestmentLead.linkedin == None,
            )
        ).order_by(InvestmentLead.id)

        if limit:
            query = query.limit(limit)

        leads = query.all()
        print(f"Enriching {len(leads)} leads…\n")

        updated = 0
        for i, lead in enumerate(leads, 1):
            first_contact = lead.key_contact.split(",")[0].strip() if lead.key_contact else ""
            print(f"[{i}/{len(leads)}] {lead.investor_name} | {first_contact}")

            new_email   = lead.email or ""
            new_linkedin = lead.linkedin or ""

            # ── Search 1: LinkedIn profile of the contact ──────────────────
            if first_contact and (not new_linkedin):
                q = f'{first_contact} {lead.investor_name} India linkedin'
                results = ddg_search(q)
                # Quick regex scan on URLs first
                for r in results:
                    m = LINKEDIN_RE.search(r["url"])
                    if m:
                        new_linkedin = m.group()
                        print(f"    ✓ LinkedIn (regex): {new_linkedin}")
                        break

            # ── Search 2: Email of the contact ─────────────────────────────
            if not new_email:
                q = f'{first_contact} {lead.investor_name} email contact India investor'
                results2 = ddg_search(q)
                # Quick regex scan
                for r in results2:
                    m = EMAIL_RE.search(r["snippet"] + " " + r["url"])
                    if m and "@" in m.group() and "example" not in m.group():
                        new_email = m.group()
                        print(f"    ✓ Email (regex): {new_email}")
                        break

            # ── Search 3: Claude extraction if still missing ───────────────
            if client and (not new_linkedin or not new_email):
                q3 = f'{lead.investor_name} {first_contact} VC India contact linkedin email'
                combined = ddg_search(q3, max_results=8)
                if combined:
                    extracted = extract_with_claude(client, lead, combined)
                    conf = extracted.get("confidence", "low")

                    if not new_linkedin:
                        li = validate_linkedin(extracted.get("linkedin_url", ""))
                        if not li:
                            li = validate_linkedin(extracted.get("company_linkedin", ""))
                        if li and conf in ("high", "medium"):
                            new_linkedin = li
                            print(f"    ✓ LinkedIn (claude/{conf}): {new_linkedin}")

                    if not new_email:
                        em = validate_email(extracted.get("email", ""))
                        if em and conf in ("high", "medium"):
                            new_email = em
                            print(f"    ✓ Email (claude/{conf}): {new_email}")

            if not new_linkedin and not new_email:
                print(f"    — Nothing found")

            # ── Write back ─────────────────────────────────────────────────
            changed = (new_email != (lead.email or "")) or (new_linkedin != (lead.linkedin or ""))
            if changed and not dry_run:
                lead.email   = new_email   or lead.email
                lead.linkedin = new_linkedin or lead.linkedin
                db.session.commit()
                updated += 1

            # Respect rate limits
            time.sleep(1.2)

        print(f"\nDone. Updated {updated} / {len(leads)} leads.")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max leads to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    args = parser.parse_args()

    enrich(limit=args.limit, dry_run=args.dry_run)
