"""
api/routes/settings.py
AI provider configuration endpoints.
API keys are never returned in plaintext — only masked versions.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ai_provider import FALLBACK_MODELS, AIProvider, AIProviderError, list_models
from core.config import get_encryption_manager
from core.database import get_db
from models.db_models import AIProviderConfig, Brand, PhaseEnum, ProviderEnum

router = APIRouter()


class ProviderConfigCreate(BaseModel):
    phase: PhaseEnum
    provider: ProviderEnum
    model: str = Field(..., min_length=1, max_length=128)
    api_key: str = Field(..., min_length=8)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=256, le=200_000)


class ProviderConfigResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    phase: PhaseEnum
    provider: ProviderEnum
    model: str
    api_key_masked: str
    temperature: float
    max_tokens: int
    is_active: bool

    class Config:
        from_attributes = True


class ProviderTestResult(BaseModel):
    success: bool
    provider: str
    model: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class ModelListRequest(BaseModel):
    provider: ProviderEnum
    api_key: str = Field(..., min_length=8)


class ModelListResponse(BaseModel):
    models: list[str]
    source: str   # "live" (from the key) or "fallback" (curated)


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return f"{key[:3]}...{key[-4:]}"


@router.get("/settings/providers/{brand_id}", response_model=list[ProviderConfigResponse])
async def list_provider_configs(brand_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIProviderConfig).where(AIProviderConfig.brand_id == brand_id))
    configs = result.scalars().all()
    enc = get_encryption_manager()

    return [
        ProviderConfigResponse(
            id=c.id,
            brand_id=c.brand_id,
            phase=c.phase,
            provider=c.provider,
            model=c.model,
            api_key_masked=_mask_key(enc.decrypt(c.api_key_enc)),
            temperature=c.temperature,
            max_tokens=c.max_tokens,
            is_active=c.is_active,
        )
        for c in configs
    ]


@router.post("/settings/providers/{brand_id}", response_model=ProviderConfigResponse, status_code=201)
async def upsert_provider_config(
    brand_id: uuid.UUID,
    payload: ProviderConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    brand = await db.execute(select(Brand).where(Brand.id == brand_id))
    if not brand.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Brand not found.")

    enc = get_encryption_manager()
    encrypted_key = enc.encrypt(payload.api_key)

    result = await db.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.brand_id == brand_id,
            AIProviderConfig.phase == payload.phase,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.provider = payload.provider
        existing.model = payload.model
        existing.api_key_enc = encrypted_key
        existing.temperature = payload.temperature
        existing.max_tokens = payload.max_tokens
        existing.is_active = True
        config = existing
    else:
        config = AIProviderConfig(
            brand_id=brand_id,
            phase=payload.phase,
            provider=payload.provider,
            model=payload.model,
            api_key_enc=encrypted_key,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
        )
        db.add(config)

    await db.flush()
    await db.refresh(config)

    return ProviderConfigResponse(
        id=config.id,
        brand_id=config.brand_id,
        phase=config.phase,
        provider=config.provider,
        model=config.model,
        api_key_masked=_mask_key(payload.api_key),
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        is_active=config.is_active,
    )


@router.post("/settings/providers/{brand_id}/test", response_model=ProviderTestResult)
async def test_provider_config(
    brand_id: uuid.UUID,
    phase: PhaseEnum,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIProviderConfig).where(
            AIProviderConfig.brand_id == brand_id,
            AIProviderConfig.phase == phase,
        )
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Provider config not found.")

    enc = get_encryption_manager()
    api_key = enc.decrypt(config.api_key_enc)

    provider = AIProvider(
        provider_name=config.provider.value,
        model=config.model,
        api_key=api_key,
        max_retries=1,
        timeout=15,
    )

    try:
        response = await provider.complete(
            user_message="Reply with exactly: OK",
            system_prompt="You are a test harness. Reply only with what is requested.",
            temperature=0.0,
            max_tokens=10,
        )
        return ProviderTestResult(
            success=True,
            provider=config.provider.value,
            model=config.model,
            latency_ms=round(response.latency_ms, 1),
        )
    except AIProviderError as exc:
        return ProviderTestResult(
            success=False,
            provider=config.provider.value,
            model=config.model,
            error=str(exc),
        )


@router.post("/settings/models", response_model=ModelListResponse)
async def list_available_models(payload: ModelListRequest):
    """List the models a given provider + API key can use. Falls back to a
    curated list if the live lookup fails (bad key, SDK/network issue). The key
    is used only for this lookup and is never stored here."""
    try:
        models = await list_models(payload.provider.value, payload.api_key)
        if models:
            return ModelListResponse(models=models, source="live")
    except Exception:  # noqa: BLE001 — any failure -> curated fallback
        pass
    return ModelListResponse(
        models=FALLBACK_MODELS.get(payload.provider.value, []),
        source="fallback",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Platform settings (Brave / Apify keys) — managed from the in-app Settings page
# ─────────────────────────────────────────────────────────────────────────────

class AppSettingItem(BaseModel):
    key: str
    label: str
    description: str
    secret: bool
    is_set: bool
    masked: Optional[str] = None
    value: Optional[str] = None            # plaintext, only for non-secret settings
    choices: Optional[list[str]] = None


class AppSettingUpdate(BaseModel):
    value: str = ""   # empty string clears the setting


@router.get("/settings/app", response_model=list[AppSettingItem])
async def list_app_settings():
    from core.settings_store import KNOWN_SETTINGS, get_app_setting

    items: list[AppSettingItem] = []
    for key, meta in KNOWN_SETTINGS.items():
        value = await get_app_setting(key)
        items.append(
            AppSettingItem(
                key=key,
                label=meta["label"],
                description=meta["description"],
                secret=meta["secret"],
                is_set=bool(value),
                masked=_mask_key(value) if (value and meta["secret"]) else None,
                value=value if (value and not meta["secret"]) else None,
                choices=meta.get("choices"),
            )
        )
    return items


@router.put("/settings/app/{key}")
async def update_app_setting(key: str, payload: AppSettingUpdate):
    from core.settings_store import KNOWN_SETTINGS, delete_app_setting, set_app_setting

    if key not in KNOWN_SETTINGS:
        raise HTTPException(status_code=404, detail=f"Unknown setting '{key}'.")
    value = payload.value.strip()
    if value:
        await set_app_setting(key, value)
        return {"message": "Saved.", "key": key, "is_set": True}
    await delete_app_setting(key)
    return {"message": "Cleared.", "key": key, "is_set": False}

