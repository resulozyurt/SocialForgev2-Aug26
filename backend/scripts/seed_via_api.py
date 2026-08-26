"""
scripts/seed_via_api.py
One-time brand seed via the LIVE HTTP API (no direct database access needed).

Creates FieldPie + Evatro with their full profiles and solution focuses by
calling the deployed backend. Idempotent: if a brand already exists it is
updated instead of duplicated. Uses only the Python standard library.

Run (from backend/):
    python scripts/seed_via_api.py
It will ask for the admin username and password (the same ADMIN_USERNAME /
ADMIN_PASSWORD you set on the backend service in Railway).

Note: content pillars are not seeded here (the API has no pillar endpoint yet);
brands, full profiles, and solution focuses are.
"""

from __future__ import annotations

import getpass
import json
import sys
import urllib.error
import urllib.request
from base64 import b64encode

# The deployed backend's public address (no trailing slash).
BASE_URL = "https://socialforgev2-aug26-production.up.railway.app"


BRANDS = [
    {
        "slug": "fieldpie",
        "display_name": "FieldPie",
        "industry": "Field operations SaaS",
        "language": "en",
        "primary_color": "#0EA5A4",
        "secondary_color": "#1E293B",
        "accent_color": "#0EA5A4",
        "monthly_post_target": 20,
        "voice_guide_text": (
            "Clear, reassuring, problem -> solution. Short, punchy headlines. "
            "Native US English, marketing-focused, never translated-sounding."
        ),
        "visual_identity": {
            "ground_color": "#FFFFFF",
            "block_color": "#1E293B",
            "pill": {"bg_color": "#0EA5A4", "text_color": "#FFFFFF", "shape": "rounded-full"},
            "logo": {"url": None, "position": "top-left"},
            "motifs": [
                "half-circle 'pie' graphic bottom-left",
                "3D render mixed with real photography",
                "generous white space",
                "clean modern SaaS layout",
            ],
            "style_keywords": ["clean", "modern", "SaaS", "trustworthy", "spacious"],
            "reference_images": [],
        },
        "voice_profile": {
            "tone_keywords": ["clear", "reassuring", "confident", "practical"],
            "narrative_structure": "problem -> solution",
            "example_headlines": ["Photos Don't Fix Shelves. Actions Do."],
            "avoid": ["translated phrasing", "corporate fluff", "generic AI voice"],
        },
        "solutions": [
            {"solution": "merchandising", "is_focus": True, "priority": 10,
             "concept_notes": "Shelf execution, planogram compliance, retail audits."},
            {"solution": "field_audit", "is_focus": True, "priority": 20,
             "concept_notes": "On-site audits and compliance checks."},
            {"solution": "field_sales", "is_focus": True, "priority": 30,
             "concept_notes": "Rep productivity, route and visit execution."},
            {"solution": "home_service", "is_focus": True, "priority": 40,
             "concept_notes": "Dispatch, on-site jobs, service quality."},
            {"solution": "ai", "is_focus": True, "priority": 50,
             "concept_notes": "AI-assisted field ops, photo recognition."},
            {"solution": "general", "is_focus": False, "priority": 90,
             "concept_notes": "Brand-level, cross-solution content."},
        ],
    },
    {
        "slug": "evatro",
        "display_name": "Evatro",
        "industry": "Saha operasyonlari / merchandising yazilimi",
        "language": "tr",
        "primary_color": "#E4002B",
        "secondary_color": "#0B1E3B",
        "accent_color": "#E4002B",
        "monthly_post_target": 12,
        "voice_guide_text": (
            "Net, iddiali, 'yeterli degil -> gereken bu' kurgusu. Dogal, yerel "
            "Turkce; Ingilizceden ceviri gibi durmayan. Kisa, carpici basliklar."
        ),
        "visual_identity": {
            "ground_color": "#FFFFFF",
            "block_color": "#0B1E3B",
            "pill": {"bg_color": "#E4002B", "text_color": "#FFFFFF", "shape": "rounded-full"},
            "logo": {"url": None, "position": "bottom-left"},
            "motifs": [
                "navy corner block top-left",
                "magnifier",
                "tablet and phone mockups",
                "shelf and store photography",
                "red accent lines",
            ],
            "style_keywords": ["net", "iddiali", "modern", "kanit-odakli"],
            "reference_images": [],
        },
        "voice_profile": {
            "tone_keywords": ["net", "iddiali", "guven veren"],
            "narrative_structure": "yeterli degil -> gereken bu",
            "example_headlines": ["Urun Stokta, Peki Rafta mi?"],
            "avoid": ["Ingilizceden ceviri gibi durma", "yapay/kurumsal dil"],
        },
        "solutions": [
            {"solution": "merchandising", "is_focus": True, "priority": 10,
             "concept_notes": "Raf denetimi, planogram uyumu, saha merchandising."},
            {"solution": "field_audit", "is_focus": True, "priority": 20,
             "concept_notes": "Saha denetimi ve uygunluk kontrolu."},
            {"solution": "ai", "is_focus": True, "priority": 30,
             "concept_notes": "AI destekli gorsel tanima ve raf analizi."},
            {"solution": "general", "is_focus": False, "priority": 90,
             "concept_notes": "Marka duzeyi, cozumler arasi icerik."},
        ],
    },
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
        with urllib.request.urlopen(req, timeout=30) as resp:
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
        print(f"\nBaglanti hatasi: {exc}. BASE_URL dogru mu?  ({BASE_URL})")
        sys.exit(1)


def main() -> None:
    print(f"Backend: {BASE_URL}\n")
    user = input("Admin username: ").strip()
    pw = getpass.getpass("Admin password: ")

    status, _ = _request("GET", "/api/v1/brands", user, pw)
    if status == 401:
        print("\nGiris basarisiz (401). Kullanici adi/sifre backend'dekiyle ayni degil.")
        sys.exit(1)
    if status != 200:
        print(f"\nBeklenmeyen yanit: {status}. Devam edilemiyor.")
        sys.exit(1)

    for spec in BRANDS:
        spec = dict(spec)  # copy so we can pop
        solutions = spec.pop("solutions")
        slug = spec["slug"]

        status, data = _request("POST", "/api/v1/brands", user, pw, spec)
        if status == 201:
            brand_id = data["id"]
            print(f"created  {slug}")
        elif status == 409:
            _, brands = _request("GET", "/api/v1/brands", user, pw)
            brand_id = next((b["id"] for b in brands if b["slug"] == slug), None)
            if not brand_id:
                print(f"SKIP {slug}: exists but could not be found in list.")
                continue
            profile = {k: v for k, v in spec.items() if k != "slug"}
            _request("PATCH", f"/api/v1/brands/{brand_id}", user, pw, profile)
            print(f"updated  {slug}")
        else:
            print(f"ERROR {slug}: {status} {data}")
            continue

        s_status, s_data = _request(
            "PUT", f"/api/v1/brands/{brand_id}/solutions", user, pw, solutions
        )
        if s_status == 200:
            print(f"         -> {len(s_data)} solutions set")
        else:
            print(f"         -> solutions ERROR {s_status}: {s_data}")

    print("\nDone. Refresh the frontend — FieldPie and Evatro should appear.")


if __name__ == "__main__":
    main()
