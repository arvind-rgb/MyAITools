import os
import csv
import io
import uuid
import base64
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders as email_encoders
from flask import Flask, render_template, request, jsonify, Response, redirect, session
from dotenv import load_dotenv
from database import db, InvestmentLead, EmailTemplate, Delivery
from scraper import get_seed_data, scrape_live, fetch_recent_investments, enrich_contact, generate_email_draft

load_dotenv(override=True)

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///investment_leads.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "bhookle-dev-secret")

db.init_app(app)

# ── Gmail API helpers ────────────────────────────────────────────────────────
GMAIL_SCOPES   = ["https://www.googleapis.com/auth/gmail.send"]
GMAIL_TOKEN    = os.path.join(os.path.dirname(__file__), "gmail_token.json")
GMAIL_CREDS    = os.path.join(os.path.dirname(__file__), "credentials.json")
GMAIL_REDIRECT = "http://localhost:5050/api/gmail/callback"

ATTACHMENTS_DIR = os.path.join(os.path.dirname(__file__), "static", "attachments")
os.makedirs(ATTACHMENTS_DIR, exist_ok=True)


def _gmail_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    if not os.path.exists(GMAIL_TOKEN):
        raise RuntimeError("gmail_not_connected")
    creds = Credentials.from_authorized_user_file(GMAIL_TOKEN, GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(GMAIL_TOKEN, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _build_mime(to, subject, body, attachment_path=None):
    msg = MIMEMultipart()
    msg["to"]      = to
    msg["subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        email_encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f'attachment; filename="{os.path.basename(attachment_path)}"',
        )
        msg.attach(part)
    return {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}


def _send_via_gmail(to, subject, body, attachment_path=None):
    svc = _gmail_service()
    svc.users().messages().send(
        userId="me", body=_build_mime(to, subject, body, attachment_path)
    ).execute()


def _mark_sent(lead):
    today = date.today().strftime("%d %b %Y")
    note  = f"Email sent on {today}"
    lead.notes  = (lead.notes.rstrip() + f"\n{note}") if lead.notes else note
    lead.status = "Reached Out"


def seed_db():
    if InvestmentLead.query.count() == 0:
        for d in get_seed_data():
            lead = InvestmentLead(**{k: v for k, v in d.items() if hasattr(InvestmentLead, k)})
            db.session.add(lead)
        db.session.commit()
        print(f"[app] Seeded {InvestmentLead.query.count()} leads")


@app.route("/")
def index():
    status_filter = request.args.get("status", "")
    search = request.args.get("search", "")
    investor_type_filter = request.args.get("investor_type", "")

    query = InvestmentLead.query
    if status_filter:
        query = query.filter(InvestmentLead.status == status_filter)
    if investor_type_filter:
        query = query.filter(InvestmentLead.investor_type == investor_type_filter)
    if search:
        like = f"%{search}%"
        query = query.filter(db.or_(
            InvestmentLead.investor_name.ilike(like),
            InvestmentLead.invested_company.ilike(like),
            InvestmentLead.key_contact.ilike(like),
            InvestmentLead.sector.ilike(like),
        ))

    leads = query.order_by(InvestmentLead.id.desc()).all()
    total = InvestmentLead.query.count()

    status_counts = {s: InvestmentLead.query.filter_by(status=s).count()
                     for s in ["New", "Reached Out", "Engaged", "Didn't Respond", "Not Interested"]}

    investor_types = [r[0] for r in db.session.query(InvestmentLead.investor_type).distinct().all() if r[0]]

    return render_template(
        "index.html",
        leads=leads, total=total,
        status_counts=status_counts,
        investor_types=sorted(investor_types),
        current_status=status_filter,
        current_type=investor_type_filter,
        search=search,
    )


@app.route("/api/lead/<int:lead_id>/status", methods=["PATCH"])
def update_status(lead_id):
    lead = InvestmentLead.query.get_or_404(lead_id)
    data = request.get_json()
    allowed = ["New", "Reached Out", "Engaged", "Didn't Respond", "Not Interested"]
    if data.get("status") not in allowed:
        return jsonify({"error": "Invalid status"}), 400
    lead.status = data["status"]
    db.session.commit()
    return jsonify({"ok": True, "status": lead.status})


@app.route("/api/lead/<int:lead_id>/contacts", methods=["PATCH"])
def update_contacts(lead_id):
    lead = InvestmentLead.query.get_or_404(lead_id)
    data = request.get_json()
    if 'names' in data:
        lead.key_contact = ','.join(n for n in data['names'] if n)
    if 'emails' in data:
        lead.email = ','.join(e for e in data['emails'] if e)
    if 'linkedins' in data:
        lead.linkedin = ','.join(l for l in data['linkedins'] if l)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/lead/<int:lead_id>/followup", methods=["PATCH"])
def update_followup(lead_id):
    lead = InvestmentLead.query.get_or_404(lead_id)
    data = request.get_json()
    lead.follow_up_date = data.get("follow_up_date", "")
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/lead/<int:lead_id>/notes", methods=["PATCH"])
def update_notes(lead_id):
    lead = InvestmentLead.query.get_or_404(lead_id)
    data = request.get_json()
    lead.notes = data.get("notes", "")
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/lead/<int:lead_id>/enrich", methods=["POST"])
def enrich_lead(lead_id):
    lead = InvestmentLead.query.get_or_404(lead_id)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 400
    contacts = enrich_contact(lead.investor_name, lead.investor_type, api_key)
    if contacts:
        names     = [c.get("name", "").strip()     for c in contacts if c.get("name")]
        emails    = [c.get("email", "").strip()    for c in contacts]
        linkedins = [c.get("linkedin", "").strip() for c in contacts]
        titles    = [c.get("title", "").strip()    for c in contacts]
        # Append to existing or set new
        def merge(existing, new_vals):
            existing_list = [v.strip() for v in existing.split(",") if v.strip()] if existing else []
            for v in new_vals:
                if v and v not in existing_list:
                    existing_list.append(v)
            return ",".join(existing_list)
        lead.key_contact = merge(lead.key_contact, names)
        lead.email       = merge(lead.email,       emails)
        lead.linkedin    = merge(lead.linkedin,    linkedins)
        db.session.commit()
    return jsonify({"ok": True, "contacts": contacts})


_enrich_status = {"running": False, "done": 0, "total": 0, "enriched": 0}

@app.route("/api/enrich/batch", methods=["POST"])
def enrich_batch():
    """Kick off background enrichment; return immediately."""
    global _enrich_status
    if _enrich_status["running"]:
        return jsonify({"ok": False, "message": "Already running…"}), 409
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 400

    # collect IDs upfront (don't pass ORM objects to thread)
    with app.app_context():
        leads = InvestmentLead.query.filter(
            db.or_(
                InvestmentLead.email == None, InvestmentLead.email == "",
                InvestmentLead.linkedin == None, InvestmentLead.linkedin == ""
            )
        ).limit(30).all()
        lead_ids = [(l.id, l.investor_name, l.investor_type) for l in leads]

    _enrich_status = {"running": True, "done": 0, "total": len(lead_ids), "enriched": 0}

    import threading
    def run():
        global _enrich_status
        def merge(existing, new_vals):
            ex = [v.strip() for v in existing.split(",") if v.strip()] if existing else []
            for v in new_vals:
                if v and v not in ex:
                    ex.append(v)
            return ",".join(ex)
        with app.app_context():
            for lead_id, name, itype in lead_ids:
                try:
                    contacts = enrich_contact(name, itype, api_key)
                    if contacts:
                        lead = InvestmentLead.query.get(lead_id)
                        if lead:
                            lead.key_contact = merge(lead.key_contact, [c.get("name","").strip() for c in contacts if c.get("name")])
                            lead.email       = merge(lead.email,       [c.get("email","").strip() for c in contacts])
                            lead.linkedin    = merge(lead.linkedin,    [c.get("linkedin","").strip() for c in contacts])
                            db.session.commit()
                            _enrich_status["enriched"] += 1
                except Exception as e:
                    print(f"[enrich] {name}: {e}")
                _enrich_status["done"] += 1
        _enrich_status["running"] = False

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True, "total": len(lead_ids), "message": f"Started enriching {len(lead_ids)} leads…"})


@app.route("/api/enrich/status")
def enrich_status():
    return jsonify(_enrich_status)


@app.route("/api/lead/<int:lead_id>/recent", methods=["POST"])
def enrich_recent(lead_id):
    """Fetch recent investments for a single lead via Claude."""
    lead = InvestmentLead.query.get_or_404(lead_id)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 400
    result = fetch_recent_investments(lead.investor_name, api_key)
    if result and result != "Data unavailable":
        lead.recent_investments = result
        db.session.commit()
    return jsonify({"ok": True, "recent_investments": result})


@app.route("/api/lead", methods=["POST"])
def add_lead():
    data = request.get_json()
    if not data.get("investor_name"):
        return jsonify({"error": "investor_name is required"}), 400
    lead = InvestmentLead(
        investor_name=data.get("investor_name", ""),
        investor_type=data.get("investor_type", ""),
        invested_company=data.get("invested_company", "—"),
        investment_amount=data.get("investment_amount", ""),
        round_type=data.get("round_type", ""),
        sector=data.get("sector", ""),
        deal_date=data.get("deal_date", ""),
        key_contact=data.get("key_contact", ""),
        email=data.get("email", ""),
        linkedin=data.get("linkedin", ""),
        source_url=data.get("source_url", ""),
        status="New",
    )
    db.session.add(lead)
    db.session.commit()
    return jsonify({"ok": True, "id": lead.id}), 201


@app.route("/api/lead/<int:lead_id>", methods=["DELETE"])
def delete_lead(lead_id):
    lead = InvestmentLead.query.get_or_404(lead_id)
    db.session.delete(lead)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/refresh", methods=["POST"])
def refresh_leads():
    new_deals = scrape_live()
    added = 0
    for d in new_deals:
        exists = InvestmentLead.query.filter_by(
            investor_name=d.get("investor_name", ""),
            invested_company=d.get("invested_company", ""),
        ).first()
        if not exists:
            lead = InvestmentLead(**{k: v for k, v in d.items() if hasattr(InvestmentLead, k)})
            db.session.add(lead)
            added += 1
    db.session.commit()
    return jsonify({"ok": True, "added": added, "message": f"🍱 Added {added} fresh leads!"})


@app.route("/api/export")
def export_csv():
    leads = InvestmentLead.query.order_by(InvestmentLead.id.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Investor Name", "Type", "Invested Company", "Amount", "Round",
        "Sector", "Deal Date", "Key Contact", "Email", "LinkedIn",
        "Recent Investments", "Status", "Notes", "Source"
    ])
    for l in leads:
        writer.writerow([
            l.investor_name, l.investor_type, l.invested_company,
            l.investment_amount, l.round_type, l.sector, l.deal_date,
            l.key_contact, l.email, l.linkedin,
            l.recent_investments or "", l.status, l.notes or "", l.source_url or ""
        ])
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=bhookle_investment_leads.csv"},
    )


# ── Gmail OAuth2 setup ───────────────────────────────────────────────────────

@app.route("/api/gmail/status")
def gmail_status():
    connected = os.path.exists(GMAIL_TOKEN)
    has_creds = os.path.exists(GMAIL_CREDS)
    return jsonify({"connected": connected, "has_credentials_json": has_creds})


@app.route("/api/gmail/auth")
def gmail_auth():
    from google_auth_oauthlib.flow import Flow
    if not os.path.exists(GMAIL_CREDS):
        return jsonify({"error": "credentials.json not found"}), 400
    flow = Flow.from_client_secrets_file(GMAIL_CREDS, scopes=GMAIL_SCOPES, redirect_uri=GMAIL_REDIRECT)
    auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/api/gmail/callback")
def gmail_callback():
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_secrets_file(
        GMAIL_CREDS, scopes=GMAIL_SCOPES,
        redirect_uri=GMAIL_REDIRECT, state=session.get("oauth_state"),
    )
    flow.fetch_token(authorization_response=request.url)
    with open(GMAIL_TOKEN, "w") as f:
        f.write(flow.credentials.to_json())
    return redirect("/?gmail=connected")


@app.route("/api/gmail/disconnect", methods=["POST"])
def gmail_disconnect():
    if os.path.exists(GMAIL_TOKEN):
        os.remove(GMAIL_TOKEN)
    return jsonify({"ok": True})


# ── Email Templates CRUD ─────────────────────────────────────────────────────

@app.route("/api/templates", methods=["GET"])
def list_templates():
    templates = EmailTemplate.query.order_by(EmailTemplate.id.asc()).all()
    return jsonify([
        {"id": t.id, "name": t.name, "subject": t.subject or "", "body": t.body,
         "attachment_name": t.attachment_name or ""}
        for t in templates
    ])


@app.route("/api/templates", methods=["POST"])
def create_template():
    data = request.get_json()
    if not data.get("name") or not data.get("body"):
        return jsonify({"error": "name and body are required"}), 400
    t = EmailTemplate(
        name=data["name"],
        subject=data.get("subject", ""),
        body=data["body"],
    )
    db.session.add(t)
    db.session.commit()
    return jsonify({"ok": True, "id": t.id}), 201


@app.route("/api/templates/<int:tid>", methods=["PUT"])
def update_template(tid):
    t = EmailTemplate.query.get_or_404(tid)
    data = request.get_json()
    t.name    = data.get("name",    t.name)
    t.subject = data.get("subject", t.subject)
    t.body    = data.get("body",    t.body)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/templates/<int:tid>", methods=["DELETE"])
def delete_template(tid):
    t = EmailTemplate.query.get_or_404(tid)
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})


# ── AI Email Draft Generation ────────────────────────────────────────────────

@app.route("/api/lead/<int:lead_id>/draft-email", methods=["POST"])
def draft_email(lead_id):
    lead = InvestmentLead.query.get_or_404(lead_id)
    data = request.get_json()
    template_id = data.get("template_id")
    if not template_id:
        return jsonify({"error": "template_id is required"}), 400
    template = EmailTemplate.query.get_or_404(template_id)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 400

    result = generate_email_draft(
        lead.investor_name,
        lead.investor_type or "",
        lead.invested_company or "",
        lead.sector or "",
        template.subject or "",
        template.body,
        api_key,
    )
    if not result:
        return jsonify({"error": "AI failed to generate a draft — try again"}), 500

    return jsonify({
        "ok": True,
        "subject": result.get("subject") or template.subject or "",
        "body":    result.get("body", ""),
    })


# ── Single lead send ─────────────────────────────────────────────────────────

@app.route("/api/lead/<int:lead_id>/send-email", methods=["POST"])
def send_email_route(lead_id):
    lead = InvestmentLead.query.get_or_404(lead_id)
    data        = request.get_json()
    to_email    = (data.get("to_email") or "").strip()
    subject     = (data.get("subject")  or "").strip()
    body        = (data.get("body")     or "").strip()
    template_id = data.get("template_id")

    if not to_email: return jsonify({"error": "Recipient email required"}), 400

    attachment_path = None
    if template_id:
        t = EmailTemplate.query.get(template_id)
        if t and t.attachment_path:
            attachment_path = t.attachment_path

    try:
        _send_via_gmail(to_email, subject, body, attachment_path)
    except RuntimeError as e:
        if "gmail_not_connected" in str(e):
            return jsonify({"error": "gmail_not_connected"}), 401
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    _mark_sent(lead)
    db.session.commit()
    return jsonify({"ok": True})


# ── Bulk send ─────────────────────────────────────────────────────────────────

@app.route("/api/bulk-send", methods=["POST"])
def bulk_send():
    data        = request.get_json()
    lead_ids    = data.get("lead_ids", [])
    template_id = data.get("template_id")
    api_key     = os.getenv("ANTHROPIC_API_KEY")

    if not lead_ids or not template_id:
        return jsonify({"error": "lead_ids and template_id are required"}), 400

    template = EmailTemplate.query.get_or_404(template_id)
    leads    = InvestmentLead.query.filter(InvestmentLead.id.in_(lead_ids)).all()

    results = []
    for lead in leads:
        email = (lead.email or "").split(",")[0].strip()
        if not email:
            results.append({"id": lead.id, "name": lead.investor_name, "status": "skipped", "reason": "no email"})
            continue
        try:
            draft = generate_email_draft(
                lead.investor_name, lead.investor_type or "",
                lead.invested_company or "", lead.sector or "",
                template.subject or "", template.body, api_key,
            ) if api_key else None
            subject = (draft or {}).get("subject") or template.subject or ""
            body    = (draft or {}).get("body")    or template.body
            _send_via_gmail(email, subject, body, template.attachment_path)
            _mark_sent(lead)
            results.append({"id": lead.id, "name": lead.investor_name, "status": "sent", "email": email})
        except RuntimeError as e:
            if "gmail_not_connected" in str(e):
                db.session.commit()
                return jsonify({"error": "gmail_not_connected", "results": results}), 401
            results.append({"id": lead.id, "name": lead.investor_name, "status": "error", "reason": str(e)})
        except Exception as e:
            results.append({"id": lead.id, "name": lead.investor_name, "status": "error", "reason": str(e)})

    db.session.commit()
    sent = sum(1 for r in results if r["status"] == "sent")
    return jsonify({"ok": True, "sent": sent, "total": len(leads), "results": results})


# ── Attachment upload for templates ──────────────────────────────────────────

@app.route("/api/templates/<int:tid>/attachment", methods=["POST"])
def upload_attachment(tid):
    t = EmailTemplate.query.get_or_404(tid)
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400
    ext      = os.path.splitext(f.filename)[1]
    filename = uuid.uuid4().hex + ext
    path     = os.path.join(ATTACHMENTS_DIR, filename)
    # Remove old file
    if t.attachment_path and os.path.exists(t.attachment_path):
        os.remove(t.attachment_path)
    f.save(path)
    t.attachment_path = path
    t.attachment_name = f.filename
    db.session.commit()
    return jsonify({"ok": True, "attachment_name": f.filename})


@app.route("/api/templates/<int:tid>/attachment", methods=["DELETE"])
def remove_attachment(tid):
    t = EmailTemplate.query.get_or_404(tid)
    if t.attachment_path and os.path.exists(t.attachment_path):
        os.remove(t.attachment_path)
    t.attachment_path = None
    t.attachment_name = None
    db.session.commit()
    return jsonify({"ok": True})


# ── Porter Delivery Routes ───────────────────────────────────────────────────

import asyncio as _asyncio
from porter_browser import PorterBrowser as _PorterBrowser, SESSION_DIR as _PORTER_SESSION_DIR


@app.route("/api/deliveries", methods=["GET"])
def list_deliveries():
    deliveries = Delivery.query.order_by(Delivery.id.desc()).all()
    return jsonify([d.to_dict() for d in deliveries])


@app.route("/api/deliveries", methods=["POST"])
def create_delivery():
    data = request.get_json()
    for field in ["pickup_address", "drop_address", "contact_name", "contact_phone"]:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400
    delivery = Delivery(
        pickup_address=data["pickup_address"],
        drop_address=data["drop_address"],
        contact_name=data["contact_name"],
        contact_phone=data["contact_phone"],
        pickup_time=data.get("pickup_time", "now"),
        status=data.get("status", "pending"),
        porter_order_id=data.get("porter_order_id", ""),
        estimated_cost=data.get("estimated_cost", ""),
        notes=data.get("notes", ""),
    )
    db.session.add(delivery)
    db.session.commit()
    return jsonify({"ok": True, "id": delivery.id, "delivery": delivery.to_dict()}), 201


@app.route("/api/deliveries/<int:delivery_id>", methods=["PATCH"])
def update_delivery(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    data = request.get_json()
    for field in ["status", "porter_order_id", "estimated_cost", "notes", "pickup_time"]:
        if field in data:
            setattr(delivery, field, data[field])
    db.session.commit()
    return jsonify({"ok": True, "delivery": delivery.to_dict()})


@app.route("/api/deliveries/<int:delivery_id>/status", methods=["GET"])
def get_delivery_status(delivery_id):
    delivery = Delivery.query.get_or_404(delivery_id)
    return jsonify({
        "id":              delivery.id,
        "status":          delivery.status,
        "porter_order_id": delivery.porter_order_id,
        "estimated_cost":  delivery.estimated_cost,
        "updated_at":      delivery.updated_at.isoformat() if delivery.updated_at else None,
    })


@app.route("/api/porter/session-status")
def porter_session_status():
    cookies_file = os.path.join(_PORTER_SESSION_DIR, "Default", "Cookies")
    network_file = os.path.join(_PORTER_SESSION_DIR, "Default", "Network", "Cookies")
    exists = os.path.exists(cookies_file) or os.path.exists(network_file)
    return jsonify({"session_file_exists": exists})


@app.route("/api/porter/setup-session", methods=["POST"])
def porter_setup_session():
    async def _run():
        async with _PorterBrowser(headless=False) as pb:
            return await pb.setup_session_interactive()
    result = _asyncio.run(_run())
    return jsonify(result)


@app.route("/api/porter/quote", methods=["POST"])
def porter_quote():
    data = request.get_json()
    if not data.get("pickup_address") or not data.get("drop_address"):
        return jsonify({"error": "pickup_address and drop_address required"}), 400
    async def _run():
        async with _PorterBrowser() as pb:
            return await pb.get_quote(data["pickup_address"], data["drop_address"])
    result = _asyncio.run(_run())
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/api/porter/book", methods=["POST"])
def porter_book():
    data = request.get_json()
    for field in ["pickup_address", "drop_address", "contact_name", "contact_phone"]:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400
    async def _run():
        async with _PorterBrowser() as pb:
            return await pb.book_delivery(
                pickup=data["pickup_address"],
                drop=data["drop_address"],
                contact_name=data["contact_name"],
                contact_phone=data["contact_phone"],
                pickup_time=data.get("pickup_time", "now"),
            )
    result = _asyncio.run(_run())
    if result.get("ok"):
        delivery = Delivery(
            pickup_address=data["pickup_address"],
            drop_address=data["drop_address"],
            contact_name=data["contact_name"],
            contact_phone=data["contact_phone"],
            pickup_time=data.get("pickup_time", "now"),
            status="booked",
            porter_order_id=result.get("porter_order_id", ""),
            estimated_cost=result.get("estimated_cost", ""),
            notes=data.get("notes", ""),
        )
        db.session.add(delivery)
        db.session.commit()
        result["delivery_id"] = delivery.id
    return jsonify(result), (201 if result.get("ok") else 400)


@app.route("/api/porter/track/<order_id>")
def porter_track(order_id):
    async def _run():
        async with _PorterBrowser() as pb:
            return await pb.track_order(order_id)
    result = _asyncio.run(_run())
    return jsonify(result), (200 if result.get("ok") else 400)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_db()
    app.run(debug=True, port=5050)
