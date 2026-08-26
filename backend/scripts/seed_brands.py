"""
scripts/seed_brands.py
Idempotent seed for the two brands — FieldPie (US/EN) and Evatro (TR).

Upserts by slug: running it repeatedly updates the profiles in place instead of
creating duplicates. It seeds each brand's rich profile (language, colors,
visual_identity, voice_profile), content pillars, and solution focuses.

It deliberately does NOT seed AIProviderConfig rows — those hold real,
Fernet-encrypted API keys and are configured per brand via the settings API.

Run (from backend/, with the DB reachable and migrations applied):
    python -m scripts.seed_brands
    # or
    python scripts/seed_brands.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select

from core.database import get_db_context
from models.db_models import (
    Brand,
    BrandLanguageEnum,
    BrandSolution,
    ContentPillar,
    SolutionEnum,
)


# ─────────────────────────────────────────────────────────────────────────────
# Brand specifications
# ─────────────────────────────────────────────────────────────────────────────

BRANDS: list[dict] = [
    {
        "slug": "fieldpie",
        "display_name": "FieldPie",
        "industry": "Field operations SaaS",
        "language": BrandLanguageEnum.EN,
        "primary_color": "#0EA5A4",
        "secondary_color": "#1E293B",
        "accent_color": "#0EA5A4",
        "monthly_post_target": 20,
        "voice_guide_text": (
            "Clear, reassuring, problem -> solution. Short, punchy headlines. "
            "Native US English, marketing-focused, never translated-sounding. "
            "No corporate fluff, no 'excited to announce' energy."
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
            "avoid": [
                "translated phrasing",
                "corporate fluff",
                "excited to announce energy",
                "generic AI voice",
            ],
        },
        "research_sources": {
            "rss_feeds": [
                "https://www.retaildive.com/feeds/news/",
                "https://www.socialmediatoday.com/feeds/news/",
                "https://www.modernretail.co/feed/",
            ],
            "trends_geo": "US",
            "use_apify": False,
        },
        "pillars": [
            {"name": "Problem -> Solution Proof", "percentage": 30,
             "description": "Show a field-ops pain and how FieldPie resolves it."},
            {"name": "Product in Action", "percentage": 25,
             "description": "Real product/UI inside real field workflows."},
            {"name": "Industry Insight", "percentage": 25,
             "description": "Retail execution and field-operations trends."},
            {"name": "Brand & Culture", "percentage": 20,
             "description": "Team, values, and customer stories."},
        ],
        "solutions": [
            {"solution": SolutionEnum.MERCHANDISING, "is_focus": True, "priority": 10,
             "concept_notes": "Shelf execution, planogram compliance, retail audits."},
            {"solution": SolutionEnum.FIELD_AUDIT, "is_focus": True, "priority": 20,
             "concept_notes": "On-site audits and compliance checks."},
            {"solution": SolutionEnum.FIELD_SALES, "is_focus": True, "priority": 30,
             "concept_notes": "Rep productivity, route and visit execution."},
            {"solution": SolutionEnum.HOME_SERVICE, "is_focus": True, "priority": 40,
             "concept_notes": "Dispatch, on-site jobs, service quality."},
            {"solution": SolutionEnum.AI, "is_focus": True, "priority": 50,
             "concept_notes": "AI-assisted field ops, photo recognition."},
            {"solution": SolutionEnum.GENERAL, "is_focus": False, "priority": 90,
             "concept_notes": "Brand-level, cross-solution content."},
        ],
    },
    {
        "slug": "evatro",
        "display_name": "Evatro",
        "industry": "Saha operasyonları / merchandising yazılımı",
        "language": BrandLanguageEnum.TR,
        "primary_color": "#E4002B",
        "secondary_color": "#0B1E3B",
        "accent_color": "#E4002B",
        "monthly_post_target": 12,
        "voice_guide_text": (
            "Net, iddialı, 'yeterli değil -> gereken bu' kurgusu. Doğal, yerel "
            "Türkçe; İngilizceden çeviri gibi durmayan. Kısa, çarpıcı başlıklar."
        ),
        "visual_identity": {
            "ground_color": "#FFFFFF",
            "block_color": "#0B1E3B",
            "pill": {"bg_color": "#E4002B", "text_color": "#FFFFFF", "shape": "rounded-full"},
            "logo": {"url": None, "position": "bottom-left"},
            "motifs": [
                "navy corner block top-left",
                "magnifier / büyüteç",
                "tablet and phone mockups",
                "shelf and store photography",
                "red accent lines",
            ],
            "style_keywords": ["net", "iddialı", "modern", "kanıt-odaklı"],
            "reference_images": [],
        },
        "voice_profile": {
            "tone_keywords": ["net", "iddialı", "güven veren"],
            "narrative_structure": "yeterli değil -> gereken bu",
            "example_headlines": ["Ürün Stokta, Peki Rafta mı?"],
            "avoid": ["İngilizceden çeviri gibi durma", "yapay/kurumsal dil"],
        },
        "research_sources": {
            "rss_feeds": [
                "https://webrazzi.com/feed",
                "https://www.retaildive.com/feeds/news/",
            ],
            "trends_geo": "TR",
            "use_apify": False,
        },
        "pillars": [
            {"name": "Raf Gerçekliği", "percentage": 30,
             "description": "Sahadaki raf/stok problemleri ve çözümü."},
            {"name": "Ürün Aksiyonu", "percentage": 30,
             "description": "Gerçek akışlarda ürün/uygulama görünümü."},
            {"name": "Sektör İçgörüsü", "percentage": 25,
             "description": "Merchandising ve saha denetimi trendleri."},
            {"name": "Marka & Kültür", "percentage": 15,
             "description": "Ekip, değerler ve müşteri hikayeleri."},
        ],
        "solutions": [
            {"solution": SolutionEnum.MERCHANDISING, "is_focus": True, "priority": 10,
             "concept_notes": "Raf denetimi, planogram uyumu, saha merchandising."},
            {"solution": SolutionEnum.FIELD_AUDIT, "is_focus": True, "priority": 20,
             "concept_notes": "Saha denetimi ve uygunluk kontrolü."},
            {"solution": SolutionEnum.AI, "is_focus": True, "priority": 30,
             "concept_notes": "AI destekli görsel tanıma ve raf analizi."},
            {"solution": SolutionEnum.GENERAL, "is_focus": False, "priority": 90,
             "concept_notes": "Marka düzeyi, çözümler arası içerik."},
        ],
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Upsert helpers
# ─────────────────────────────────────────────────────────────────────────────

BRAND_SCALAR_FIELDS = (
    "display_name", "industry", "language", "primary_color", "secondary_color",
    "accent_color", "monthly_post_target", "voice_guide_text", "visual_identity",
    "voice_profile", "research_sources",
)


async def _upsert_brand(db, spec: dict) -> Brand:
    result = await db.execute(select(Brand).where(Brand.slug == spec["slug"]))
    brand = result.scalar_one_or_none()

    if brand is None:
        brand = Brand(slug=spec["slug"])
        db.add(brand)

    for field in BRAND_SCALAR_FIELDS:
        setattr(brand, field, spec[field])
    brand.is_active = True

    await db.flush()  # ensure brand.id is available for children
    return brand


async def _upsert_pillars(db, brand: Brand, pillars: list[dict]) -> None:
    result = await db.execute(
        select(ContentPillar).where(ContentPillar.brand_id == brand.id)
    )
    existing = {p.name: p for p in result.scalars().all()}
    for spec in pillars:
        row = existing.get(spec["name"])
        if row is None:
            db.add(ContentPillar(
                brand_id=brand.id,
                name=spec["name"],
                description=spec.get("description"),
                percentage=spec["percentage"],
                is_active=True,
            ))
        else:
            row.description = spec.get("description")
            row.percentage = spec["percentage"]
            row.is_active = True


async def _upsert_solutions(db, brand: Brand, solutions: list[dict]) -> None:
    result = await db.execute(
        select(BrandSolution).where(BrandSolution.brand_id == brand.id)
    )
    existing = {s.solution: s for s in result.scalars().all()}
    for spec in solutions:
        row = existing.get(spec["solution"])
        if row is None:
            db.add(BrandSolution(
                brand_id=brand.id,
                solution=spec["solution"],
                is_focus=spec.get("is_focus", True),
                priority=spec.get("priority", 100),
                concept_notes=spec.get("concept_notes"),
                is_active=True,
            ))
        else:
            row.is_focus = spec.get("is_focus", True)
            row.priority = spec.get("priority", 100)
            row.concept_notes = spec.get("concept_notes")
            row.is_active = True


async def seed() -> None:
    async with get_db_context() as db:
        for spec in BRANDS:
            brand = await _upsert_brand(db, spec)
            await _upsert_pillars(db, brand, spec["pillars"])
            await _upsert_solutions(db, brand, spec["solutions"])
            print(
                f"seeded {brand.slug}: {len(spec['pillars'])} pillars, "
                f"{len(spec['solutions'])} solutions"
            )
    print("Brand seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
