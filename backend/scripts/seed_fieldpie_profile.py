"""
scripts/seed_fieldpie_profile.py
One-time, comprehensive FieldPie brand-profile seed via the LIVE HTTP API.

Fills the FieldPie brand end-to-end for the best pipeline results — identity,
voice, visual identity, solution focuses (with importance), competitors, and
per-solution research keywords — using values researched from fieldpie.com and
public sources (positioning, solutions, target audience, real competitors).

Idempotent: it PATCHes the existing FieldPie brand (found by slug), upserts its
solutions, and only adds competitors that are not already present (matched by
name). It never deletes anything. Standard library only.

Run (from backend/):
    python scripts/seed_fieldpie_profile.py
It asks for the admin username + password (the same ADMIN_USERNAME /
ADMIN_PASSWORD set on the backend service). Override the backend URL with:
    BACKEND_URL=https://your-backend python scripts/seed_fieldpie_profile.py
"""

from __future__ import annotations

import getpass
import json
import os
import sys
import urllib.error
import urllib.request
from base64 import b64encode

BASE_URL = os.environ.get(
    "BACKEND_URL", "https://socialforgev2-aug26-production.up.railway.app"
).rstrip("/")

SLUG = "fieldpie"

# ── Researched profile (fieldpie.com + public sources) ───────────────────────
PROFILE = {
    "display_name": "FieldPie",
    "industry": "AI-powered field operations software",
    "language": "en",
    "primary_color": "#0EA5A4",
    "secondary_color": "#1E293B",
    "accent_color": "#0EA5A4",
    "monthly_post_target": 30,
    "voice_guide_text": (
        "Native US English, marketing-sharp, never translated-sounding. Structure: "
        "problem -> solution -> proof. FieldPie is an all-in-one, AI-powered field "
        "operations platform (scheduling, routing, reporting, image recognition) used "
        "in 27 countries by brands like Coca-Cola, Danone and Mercedes-Benz, completing "
        "10M+ jobs a year. Voice is clear, confident and practical; lead with the real "
        "field problem, land the fix, and back it with a concrete outcome (e.g. 32% more "
        "productivity, 64% less paper). Short, punchy headlines. No corporate fluff, no "
        "hype without proof."
    ),
    "visual_identity": {
        "ground_color": "#FFFFFF",
        "block_color": "#1E293B",
        "pill": {"bg_color": "#0EA5A4", "text_color": "#FFFFFF", "shape": "rounded-full"},
        "logo": {"url": None, "position": "top-left"},
        "motifs": [
            "half-circle 'pie' graphic bottom-left",
            "3D render mixed with real store / field photography",
            "image-recognition bounding boxes on shelves",
            "generous white space",
            "clean modern SaaS layout",
        ],
        "style_keywords": [
            "clean", "modern", "SaaS", "trustworthy", "spacious",
            "data-driven", "AI-forward",
        ],
        "reference_images": [],
    },
    "voice_profile": {
        "tone_keywords": ["clear", "confident", "practical", "results-driven", "no-nonsense"],
        "narrative_structure": "problem -> solution -> proof",
        "example_headlines": [
            "Photos Don't Fix Shelves. Actions Do.",
            "See Every Shelf. Fix Every Gap.",
            "Perfect Retail Execution, Powered by AI.",
        ],
        "avoid": [
            "translated phrasing", "corporate fluff", "generic AI voice",
            "hype without proof",
        ],
    },
    "research_sources": {
        "rss_feeds": [
            "https://www.retaildive.com/feeds/news/",
            "https://www.modernretail.co/feed/",
        ],
        "trends_geo": "US",
        "use_apify": False,
        "use_trends": False,
        "search_keywords": [
            "field operations software trends",
            "retail execution trends",
            "CPG field team management",
            "field service AI trends",
        ],
        "solution_keywords": {
            "merchandising": [
                "retail merchandising execution",
                "planogram compliance software",
                "in-store execution CPG",
                "shelf audit software",
            ],
            "field_audit": [
                "retail audit software",
                "store compliance audit",
                "out-of-stock detection retail",
                "planogram audit",
            ],
            "field_sales": [
                "field sales execution CPG",
                "retail sales rep productivity",
                "DSD van sales software",
                "territory management field sales",
            ],
            "home_service": [
                "field service management software",
                "home service scheduling software",
                "HVAC dispatch software",
                "route optimization field service",
            ],
            "ai": [
                "AI image recognition retail shelf",
                "computer vision merchandising",
                "AI route optimization field",
                "AI field operations",
            ],
        },
    },
}

SOLUTIONS = [
    {"solution": "merchandising", "is_focus": True, "priority": 10, "importance": 5,
     "concept_notes": "Perfect shelf execution: planogram compliance, display accuracy, "
                      "promotions and product availability for CPG brands and retail "
                      "execution agencies. Core solution."},
    {"solution": "field_audit", "is_focus": True, "priority": 20, "importance": 4,
     "concept_notes": "Retail and store audits: compliance checks, planogram adherence, "
                      "out-of-stock tracking, evidence capture across multi-location fleets."},
    {"solution": "ai", "is_focus": True, "priority": 30, "importance": 4,
     "concept_notes": "Cross-cutting: image recognition (misplaced products, empty shelves, "
                      "compliance), AI route optimization, automated verification and reporting."},
    {"solution": "field_sales", "is_focus": True, "priority": 40, "importance": 3,
     "concept_notes": "Field sales execution: rep productivity, route and visit execution, "
                      "faster deals for distributed CPG / B2B sales teams."},
    {"solution": "home_service", "is_focus": True, "priority": 50, "importance": 3,
     "concept_notes": "Home / field service: scheduling, dispatch, on-site jobs, invoicing "
                      "and service quality for HVAC, plumbing, electrical, pest control, landscaping."},
    {"solution": "general", "is_focus": False, "priority": 90, "importance": 3,
     "concept_notes": "Brand-level, cross-solution content (positioning, proof, AI-for-field-ops)."},
]

# Real competitors (public), mapped to the solution area they compete in.
# Social handles are left empty on purpose (not fabricated) — add them later if wanted.
COMPETITORS = [
    {"name": "YOOBIC", "solution": "merchandising", "is_aspirational": True,
     "notes": "Retail execution / task management. Strong retail-execution brand to benchmark."},
    {"name": "Repsly", "solution": "merchandising", "is_aspirational": False,
     "notes": "Retail execution + field team activity for CPG merchandising."},
    {"name": "Wiser Solutions", "solution": "merchandising", "is_aspirational": False,
     "notes": "Retail intelligence + in-store execution / price & shelf monitoring."},
    {"name": "GoSpotCheck by FORM", "solution": "field_audit", "is_aspirational": False,
     "notes": "Mobile forms + retail audits / task execution for field teams."},
    {"name": "SimplyDepo", "solution": "field_sales", "is_aspirational": False,
     "notes": "Retail execution + B2B ordering for field sales / DSD."},
    {"name": "SalesRabbit", "solution": "field_sales", "is_aspirational": False,
     "notes": "Field sales enablement + route planning for door-to-door / outside sales."},
    {"name": "ServiceTitan", "solution": "home_service", "is_aspirational": True,
     "notes": "Category leader for home-service trades (HVAC/plumbing) — aspirational benchmark."},
    {"name": "Connecteam", "solution": "general", "is_aspirational": False,
     "notes": "Field team management / communication across service industries."},
]


def _request(method: str, path: str, user: str, pw: str, body=None):
    url = BASE_URL + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    token = b64encode(f"{user}:{pw}".encode("utf-8")).decode("ascii")
    req.add_header("Authorization", "Basic " + token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            text = resp.read().decode("utf-8")
            return resp.status, (json.loads(text) if text else None)
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8")
        try:
            payload = json.loads(text)
        except Exception:
            payload = text
        return exc.code, payload
    except urllib.error.URLError as exc:
        print(f"\nConnection error: {exc}. Is BACKEND_URL correct?  ({BASE_URL})")
        sys.exit(1)


def main() -> None:
    print(f"Backend: {BASE_URL}\n")
    user = input("Admin username: ").strip()
    pw = getpass.getpass("Admin password: ")

    status, brands = _request("GET", "/api/v1/brands", user, pw)
    if status == 401:
        print("\nLogin failed (401). Username/password do not match the backend.")
        sys.exit(1)
    if status != 200 or not isinstance(brands, list):
        print(f"\nUnexpected response listing brands: {status} {brands}")
        sys.exit(1)

    brand_id = next((b["id"] for b in brands if b.get("slug") == SLUG), None)
    if not brand_id:
        print(f"FieldPie (slug '{SLUG}') not found. Seed the brand first "
              f"(scripts/seed_via_api.py), then re-run this.")
        sys.exit(1)
    print(f"Found FieldPie: {brand_id}")

    # 1) Identity / voice / visual / research sources
    st, _ = _request("PATCH", f"/api/v1/brands/{brand_id}", user, pw, PROFILE)
    print(f"profile PATCH -> {st}")

    # 2) Solution focuses (with importance)
    st, sdata = _request("PUT", f"/api/v1/brands/{brand_id}/solutions", user, pw, SOLUTIONS)
    print(f"solutions PUT -> {st}"
          + (f" ({len(sdata)} set)" if st == 200 and isinstance(sdata, list) else f" {sdata}"))

    # 3) Competitors (add only the ones not already present, matched by name)
    st, existing = _request("GET", f"/api/v1/brands/{brand_id}/competitors", user, pw)
    have = {c.get("name", "").strip().lower() for c in existing} if isinstance(existing, list) else set()
    added = 0
    for comp in COMPETITORS:
        if comp["name"].strip().lower() in have:
            print(f"  competitor exists: {comp['name']}")
            continue
        cst, _ = _request("POST", f"/api/v1/brands/{brand_id}/competitors", user, pw, comp)
        if cst == 201:
            added += 1
            print(f"  + {comp['name']} ({comp['solution']})")
        else:
            print(f"  competitor ERROR {comp['name']}: {cst}")
    print(f"competitors -> {added} added")

    print("\nDone. Open FieldPie in the app and review Identity / Voice / Solutions / "
          "Competitors / Sources, then run the pipeline.")


if __name__ == "__main__":
    main()
