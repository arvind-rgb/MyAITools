from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class InvestmentLead(db.Model):
    __tablename__ = "investment_leads"

    id = db.Column(db.Integer, primary_key=True)
    investor_name = db.Column(db.String(200), nullable=False)
    investor_type = db.Column(db.String(100))         # Angel / PE / VC / Family Office
    invested_company = db.Column(db.String(200), nullable=False)
    investment_amount = db.Column(db.String(100))
    round_type = db.Column(db.String(100))            # Seed / Series A / etc.
    sector = db.Column(db.String(200))                # Cloud kitchen / Agritech / etc.
    deal_date = db.Column(db.String(50))
    key_contact = db.Column(db.String(200))
    email = db.Column(db.String(200))
    linkedin = db.Column(db.String(500))
    source_url = db.Column(db.String(1000))
    status = db.Column(
        db.String(50),
        default="New",
    )  # New / Reached Out / Engaged / Didn't Respond / Not Interested
    recent_investments = db.Column(db.Text)   # crawled: "Startup A ($2M), Startup B (₹5Cr)"
    follow_up_date = db.Column(db.String(20))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "investor_name": self.investor_name,
            "investor_type": self.investor_type,
            "invested_company": self.invested_company,
            "investment_amount": self.investment_amount,
            "round_type": self.round_type,
            "sector": self.sector,
            "deal_date": self.deal_date,
            "key_contact": self.key_contact,
            "email": self.email,
            "linkedin": self.linkedin,
            "source_url": self.source_url,
            "status": self.status,
            "recent_investments": self.recent_investments,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EmailTemplate(db.Model):
    __tablename__ = "email_templates"

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(200), nullable=False)
    subject         = db.Column(db.String(500), default="")
    body            = db.Column(db.Text, nullable=False)
    attachment_path = db.Column(db.String(500))   # path to file on disk
    attachment_name = db.Column(db.String(200))   # original filename shown to user
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Delivery(db.Model):
    __tablename__ = "deliveries"

    id              = db.Column(db.Integer, primary_key=True)
    pickup_address  = db.Column(db.String(500), nullable=False)
    drop_address    = db.Column(db.String(500), nullable=False)
    contact_name    = db.Column(db.String(200), nullable=False)
    contact_phone   = db.Column(db.String(20), nullable=False)
    pickup_time     = db.Column(db.String(50))   # ISO8601 datetime or "now"
    status          = db.Column(db.String(50), default="pending")
    # pending / booked / in_transit / delivered / failed / cancelled
    porter_order_id = db.Column(db.String(100))
    estimated_cost  = db.Column(db.String(50))
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id":               self.id,
            "pickup_address":   self.pickup_address,
            "drop_address":     self.drop_address,
            "contact_name":     self.contact_name,
            "contact_phone":    self.contact_phone,
            "pickup_time":      self.pickup_time,
            "status":           self.status,
            "porter_order_id":  self.porter_order_id,
            "estimated_cost":   self.estimated_cost,
            "notes":            self.notes,
            "created_at":       self.created_at.isoformat() if self.created_at else None,
            "updated_at":       self.updated_at.isoformat() if self.updated_at else None,
        }
