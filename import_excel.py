"""
Imports InvestmentLeads.xlsx into the SQLite database.
Run once: python3 import_excel.py
"""

import sys
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
from app import app, db
from database import InvestmentLead

EXCEL = "/Users/arvind/Downloads/Investment/InvestmentLeads.xlsx"

# ── Status mapping ─────────────────────────────────────────────────────────────
STATUS_MAP = {
    "not interested":   "Not Interested",
    "didn't respond":   "Didn't Respond",
    "didnt respond":    "Didn't Respond",
    "did not respond":  "Didn't Respond",
    "no response":      "Didn't Respond",
    "drop":             "Not Interested",
    "active":           "Engaged",
    "engaged":          "Engaged",
    "reached out":      "Reached Out",
    "tbd":              "New",
}

def map_status(raw):
    if not raw or str(raw).strip().lower() in ("nan", "none", ""):
        return "New"
    key = str(raw).strip().lower()
    # partial match
    for k, v in STATUS_MAP.items():
        if k in key:
            return v
    return "New"

def clean(val):
    if val is None:
        return ""
    s = str(val).strip().strip("\t").strip()
    return "" if s.lower() in ("nan", "none", "tbd", "n/a") else s

def infer_investor_type(name):
    n = name.lower()
    if "accelerat" in n or "100x" in n or "surge" in n or "atoms" in n:
        return "Accelerator"
    if "private investment advisor" in n or "family office" in n:
        return "Angel"
    if "angel" in n or "network" in n:
        return "Angel Network"
    if any(x in n for x in ["capital", "ventures", "partners", "fund", "vc", "invest"]):
        return "VC"
    if any(x in n for x in ["pe", "private equity", "equity"]):
        return "PE"
    return "VC"

seen = set()  # (investor_name_lower) for dedup

def add_if_new(records):
    added = 0
    for r in records:
        key = r["investor_name"].lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        lead = InvestmentLead(**r)
        db.session.add(lead)
        added += 1
    db.session.commit()
    return added


# ── Sheet: Master ──────────────────────────────────────────────────────────────
def import_master():
    df = pd.read_excel(EXCEL, sheet_name="Master", header=8)
    df = df.dropna(subset=["Fund House"])
    records = []
    for _, row in df.iterrows():
        fund   = clean(row.get("Fund House", ""))
        poc    = clean(row.get("POC", ""))
        email  = clean(row.get("Email", ""))
        status = map_status(row.get("Status", ""))
        feedback   = clean(row.get("Feedback", ""))
        referral_t = clean(row.get("Referral Type", ""))
        referral_s = clean(row.get("Referral Source", ""))

        if not fund:
            continue

        notes_parts = []
        if feedback:      notes_parts.append(f"Feedback: {feedback}")
        if referral_t:    notes_parts.append(f"Referral: {referral_t}")
        if referral_s:    notes_parts.append(f"Source: {referral_s}")

        records.append({
            "investor_name":    fund,
            "investor_type":    infer_investor_type(fund),
            "invested_company": "Bhookle",
            "investment_amount": "",
            "round_type":       "",
            "sector":           "Home Food / Food Tech",
            "deal_date":        "",
            "key_contact":      poc,
            "email":            email,
            "linkedin":         "",
            "source_url":       "",
            "status":           status,
            "notes":            " | ".join(notes_parts),
        })
    return records


# ── Sheet: Sheet1 (older snapshot — pick up extras not in Master) ─────────────
def import_sheet1():
    df = pd.read_excel(EXCEL, sheet_name="Sheet1", header=8)
    df = df.dropna(subset=["Fund House"])
    records = []
    for _, row in df.iterrows():
        fund   = clean(row.get("Fund House", ""))
        poc    = clean(row.get("POC", ""))
        email  = clean(row.get("Email", ""))
        status = map_status(row.get("Status", ""))
        feedback   = clean(row.get("Feedback", ""))
        referral_t = clean(row.get("Referral Type", ""))
        referral_s = clean(row.get("Referral Source", ""))

        if not fund:
            continue

        notes_parts = []
        if feedback:      notes_parts.append(f"Feedback: {feedback}")
        if referral_t:    notes_parts.append(f"Referral: {referral_t}")
        if referral_s:    notes_parts.append(f"Source: {referral_s}")

        records.append({
            "investor_name":    fund,
            "investor_type":    infer_investor_type(fund),
            "invested_company": "Bhookle",
            "investment_amount": "",
            "round_type":       "",
            "sector":           "Home Food / Food Tech",
            "deal_date":        "",
            "key_contact":      poc,
            "email":            email,
            "linkedin":         "",
            "source_url":       "",
            "status":           status,
            "notes":            " | ".join(notes_parts),
        })
    return records


# ── Sheet: Accelerators ────────────────────────────────────────────────────────
def import_accelerators():
    df = pd.read_excel(EXCEL, sheet_name="Accelerators", header=None)
    records = []
    for _, row in df.iterrows():
        vals = [clean(v) for v in row if clean(v)]
        if len(vals) < 2:
            continue
        # skip header-like rows
        if vals[0] in ("#", "Accelerators"):
            continue
        try:
            int(vals[0])  # first col is row number
        except ValueError:
            continue

        name   = vals[1] if len(vals) > 1 else ""
        amount = vals[2] if len(vals) > 2 else ""
        if not name:
            continue

        records.append({
            "investor_name":    name,
            "investor_type":    "Accelerator",
            "invested_company": "Bhookle",
            "investment_amount": amount[:100] if amount else "",
            "round_type":       "Accelerator Program",
            "sector":           "Home Food / Food Tech",
            "deal_date":        "",
            "key_contact":      "",
            "email":            "",
            "linkedin":         "",
            "source_url":       "",
            "status":           "New",
            "notes":            "",
        })
    return records


# ── Sheet: Dubai (Family Offices) ─────────────────────────────────────────────
def import_dubai():
    df = pd.read_excel(EXCEL, sheet_name="Dubai", header=2)
    df = df.dropna(subset=["Family Office Name"])

    # strip the first junk row (the giveaway notice)
    df = df[df["Family Office Name"].str.len() < 200]

    records = []
    for _, row in df.iterrows():
        name       = clean(row.get("Family Office Name", ""))
        contact    = clean(row.get("Contact Full Name", ""))
        email      = clean(row.get("Contact Primary Email", ""))
        linkedin_c = clean(row.get("Contact LinkedIn Profile", ""))
        linkedin_f = clean(row.get("Corporate Linkedin Address", ""))
        sectors    = clean(row.get("Investing Sectors", ""))
        thesis     = clean(row.get("Investment Thesis", ""))
        aum        = clean(row.get("AUM", ""))
        city       = clean(row.get("Family Office City", ""))
        country    = clean(row.get("Family Office Country", ""))
        job_title  = clean(row.get("Contact Job Title", ""))

        if not name:
            continue

        notes_parts = []
        if thesis[:200]:    notes_parts.append(f"Thesis: {thesis[:200]}")
        if aum:             notes_parts.append(f"AUM: {aum}")
        if city or country: notes_parts.append(f"Location: {city}, {country}".strip(", "))
        if job_title:       notes_parts.append(f"Contact role: {job_title}")

        records.append({
            "investor_name":    name,
            "investor_type":    "Family Office",
            "invested_company": "Bhookle",
            "investment_amount": "",
            "round_type":       "",
            "sector":           sectors[:200] if sectors else "Multi-sector",
            "deal_date":        "",
            "key_contact":      contact,
            "email":            email,
            "linkedin":         linkedin_c or linkedin_f,
            "source_url":       clean(row.get("Family Office Website Address", "")),
            "status":           "New",
            "notes":            " | ".join(notes_parts),
        })
    return records


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Pre-load existing names to avoid duplication with seed data
        for lead in InvestmentLead.query.all():
            seen.add(lead.investor_name.lower().strip())

        print("Importing Master sheet…")
        master_records = import_master()
        n = add_if_new(master_records)
        print(f"  → Added {n} / {len(master_records)} records")

        total = InvestmentLead.query.count()
        print(f"\nDone. Total leads in database: {total}")
