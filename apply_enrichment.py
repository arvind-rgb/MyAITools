"""
Applies enriched LinkedIn / email data to the investment_leads DB.
Run: python3 apply_enrichment.py
"""
import warnings; warnings.filterwarnings("ignore")

from app import app
from database import db, InvestmentLead

# investor_name (exact, case-insensitive) → (linkedin, email)
ENRICHMENT = {
    # ── Surge / Peak XV ───────────────────────────────────────────────────────
    "surge": (
        "https://www.linkedin.com/in/rajan-anandan-2481b814",
        ""),
    "peak xv partners": (
        "https://www.linkedin.com/in/rishenkapoor/",
        ""),

    # ── Major VCs ─────────────────────────────────────────────────────────────
    "chryscapital": (
        "https://www.linkedin.com/in/chhavi-sodhi-0015946b/",
        ""),
    "bertelsmann india investments": (
        "https://www.linkedin.com/in/akshay-chiripal",
        ""),
    "speciale invest": (
        "https://www.linkedin.com/company/specialeinvest",
        ""),
    "ankur capital": (
        "https://www.linkedin.com/in/srema",
        ""),
    "sixth sense ventures": (
        "https://www.linkedin.com/in/nikhil-vora-07713622",
        ""),
    "nexus venture partners": (
        "https://www.linkedin.com/in/sandeep-singhal-604499",
        ""),
    "blume ventures": (
        "https://www.linkedin.com/in/karthikreddyb",
        ""),
    "kae capital": (
        "https://www.linkedin.com/in/antrasaxena/",
        ""),
    "fireside ventures": (
        "https://www.linkedin.com/in/urvashi-nanda-598a17121/",
        ""),
    "3one4 capital": (
        "https://www.linkedin.com/company/3one4-capital",
        ""),
    "orios venture partners": (
        "https://www.linkedin.com/in/rehanyarkhan",
        ""),
    "rukam capital": (
        "https://www.linkedin.com/in/archanajahagirdar/",
        ""),
    "trifecta capital advisors": (
        "https://www.linkedin.com/in/khannarahul",
        ""),
    "eximius ventures": (
        "https://www.linkedin.com/in/pearl-agarwal",
        ""),
    "inflection point ventures": (
        "https://www.linkedin.com/in/arindam-deb-a37577124",
        ""),
    "better capital": (
        "https://www.linkedin.com/in/better/",
        ""),
    "india alternatives investment advisors": (
        "https://www.linkedin.com/in/harish-ravichandran-4a3b7a1a/",
        ""),
    "general catalyst (venture highway)": (
        "https://www.linkedin.com/in/siddhi-kasliwal/",
        ""),
    "lightspeed": (
        "https://www.linkedin.com/in/priyal-motwani-63099793/",
        ""),
    "rainmatter by zerodha": (
        "https://www.linkedin.com/in/jayantibhattacharya",
        ""),
    "infoedge ventures": (
        "https://www.linkedin.com/in/chinmaya-sharma/",
        ""),
    "array ventures": (
        "https://www.linkedin.com/in/shrutigandhi",
        "arraydeals@array.vc"),
    "footwork": (
        "https://www.linkedin.com/in/nikhilbt",
        ""),
    "ajvc": (
        "https://www.linkedin.com/in/aviral-bhatnagar-ajuniorvc",
        "aviral@ajuniorvc.com"),
    "anicut capital llp": (
        "https://www.linkedin.com/in/vedh-vijay/",
        ""),
    "100x.vc": (
        "https://www.linkedin.com/in/ninadkarpe",
        ""),
    "omnivore partners": (
        "https://www.linkedin.com/in/subhadeep-sanyal-4021261a",
        ""),
    "gvfl": (
        "https://www.linkedin.com/in/mihirjoshi-mj",
        ""),
    "first cheque (india quotient)": (
        "https://www.linkedin.com/in/kanika-agarrwal-9a457122/",
        ""),
    "hyderbad angel fund (haf.vc)": (
        "https://www.linkedin.com/in/rathnakar-samavedam-816085a",
        ""),
    "z47": (
        "https://www.linkedin.com/company/z47-vc",
        ""),
    "matrix partners india": (
        "https://www.linkedin.com/company/matrix-partners-india/",
        ""),
    "stellaris venture partners": (
        "https://www.linkedin.com/company/stellaris-venture-partners",
        ""),

    # ── Shark Tank sharks ─────────────────────────────────────────────────────
    "anupam mittal": (
        "https://www.linkedin.com/in/anupammittal007",
        ""),
    "vineeta singh": (
        "https://www.linkedin.com/in/vineetasingh",
        ""),
    "kunal shah": (
        "https://www.linkedin.com/in/kunalshah1",
        ""),
    "peyush bansal": (
        "https://www.linkedin.com/in/peyushbansal",
        ""),
    "aman gupta": (
        "https://www.linkedin.com/in/aman-gupta-7217a515/",
        ""),
    "namita thapar": (
        "https://www.linkedin.com/in/namita-thapar",
        ""),

    # ── Angel investors / founders turned investors ───────────────────────────
    "arjun vaidya": (
        "https://www.linkedin.com/in/arjunvaidya",
        ""),

    # ── Angel networks / other funds ─────────────────────────────────────────
    "indian angel network (ian)": (
        "https://www.linkedin.com/company/indian-angel-network",
        ""),
    "mumbai angels": (
        "https://www.linkedin.com/company/mumbai-angels-network",
        ""),
    "lvx / letsventure": (
        "https://www.linkedin.com/company/letsventure",
        ""),
    "venture catalysts++": (
        "https://www.linkedin.com/company/venturecatalysts",
        "ideas@venturecatalysts.in"),
    "the chennai angels": (
        "https://www.linkedin.com/company/the-chennai-angels",
        ""),
    "lead angels network (leadinvest)": (
        "https://www.linkedin.com/company/lead-angels-network",
        ""),
    "we founder circle": (
        "https://www.linkedin.com/company/we-founder-circle",
        ""),
    "9unicorns": (
        "https://www.linkedin.com/company/9unicorns-accelerator-fund",
        ""),
    "kalaari capital": (
        "https://www.linkedin.com/company/kalaari-capital",
        ""),
    "saama capital": (
        "https://www.linkedin.com/company/saama-capital",
        ""),
    "prime venture partners": (
        "https://www.linkedin.com/company/prime-venture-partners",
        ""),
    "ideaspring capital": (
        "https://www.linkedin.com/company/ideaspring-capital",
        ""),
    "arkam ventures": (
        "https://www.linkedin.com/company/arkam-ventures",
        ""),
    "lok capital": (
        "https://www.linkedin.com/company/lok-capital",
        ""),
    "jungle ventures": (
        "https://www.linkedin.com/company/jungle-ventures",
        ""),
    "a91 partners": (
        "https://www.linkedin.com/company/a91-partners",
        ""),
    "westbridge capital": (
        "https://www.linkedin.com/company/westbridge-capital",
        ""),
    "khosla ventures": (
        "https://www.linkedin.com/company/khosla-ventures",
        ""),
    "alpha wave ventures": (
        "https://www.linkedin.com/company/alpha-wave-global",
        ""),
    "lightrock": (
        "https://www.linkedin.com/company/lightrock",
        ""),
    "leapfrog investments": (
        "https://www.linkedin.com/company/leapfrog-investments",
        ""),
    "omidyar network": (
        "https://www.linkedin.com/company/omidyar-network",
        ""),
    "elevar equity": (
        "https://www.linkedin.com/company/elevar-equity",
        ""),
    "blacksoil": (
        "https://www.linkedin.com/company/blacksoil",
        ""),
    "tanglin venture partners": (
        "https://www.linkedin.com/company/tanglin-venture-partners",
        ""),
    "sorin investments": (
        "https://www.linkedin.com/company/sorin-investments",
        ""),
    "exfinity venture partners": (
        "https://www.linkedin.com/company/exfinity-venture-partners",
        ""),
    "huddle ventures": (
        "https://www.linkedin.com/company/huddle-accelerator",
        ""),
    "evolveX": (
        "https://www.linkedin.com/company/evolvex-accelerator",
        ""),
}


def normalise(s):
    return s.strip().lower()


def run():
    with app.app_context():
        leads = InvestmentLead.query.all()
        updated = 0
        for lead in leads:
            key = normalise(lead.investor_name)
            if key not in ENRICHMENT:
                continue
            li, em = ENRICHMENT[key]
            changed = False
            if li and not lead.linkedin:
                lead.linkedin = li
                changed = True
            if em and not lead.email:
                lead.email = em
                changed = True
            if changed:
                updated += 1

        db.session.commit()
        print(f"Updated {updated} leads with LinkedIn / email data.")

        # Summary
        has_li = InvestmentLead.query.filter(
            InvestmentLead.linkedin != "", InvestmentLead.linkedin != None
        ).count()
        has_em = InvestmentLead.query.filter(
            InvestmentLead.email != "", InvestmentLead.email != None
        ).count()
        total = InvestmentLead.query.count()
        print(f"Coverage: {has_li}/{total} have LinkedIn, {has_em}/{total} have email")


if __name__ == "__main__":
    run()
