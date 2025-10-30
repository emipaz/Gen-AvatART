"""Servicios para sincronizar avatares de HeyGen con la base local."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Iterable, Optional, Tuple

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.avatar import Avatar, AvatarStatus
from app.models.producer import Producer
from app.services.heygen_service import HeyGenService

SyncResult = Tuple[bool, str, str]


def _extract_first(data: Dict, *keys: str, default: Optional[str] = None) -> Optional[str]:
    """Obtiene el primer valor disponible en `data` para los `keys` indicados."""
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _normalize_avatar_id(item: Dict) -> Optional[str]:
    """Normaliza el identificador de un avatar retornado por HeyGen."""
    return _extract_first(
        item,
        "avatar_id",
        "avatarId",
        "id",
        "avatarID",
    )


def _collect_ids(items: Iterable[Dict]) -> set[str]:
    """Obtiene el conjunto de IDs a partir de la colección entregada por HeyGen."""
    return {avatar_id for item in items if (avatar_id := _normalize_avatar_id(item))}


def _get_owner_api_key() -> Optional[str]:
    """Obtiene la API key del dueño/plataforma desde la configuración."""
    if current_app:
        candidate = current_app.config.get("HEYGEN_OWNER_API_KEY")
        if candidate:
            return candidate
    return os.environ.get("HEYGEN_API_KEY_OWNER")


def sync_producer_heygen_avatars(producer: Producer) -> SyncResult:
    """Sincroniza los avatares propios del productor contra HeyGen.

    Descarga el catálogo del productor y le resta los avatares visibles para el dueño
    de la plataforma para evitar listar clones públicos. Los avatares exclusivos del
    productor se insertan o actualizan en la base local.

    Returns:
        tuple: (éxito, mensaje, categoria_flash)
    """
    producer_api_key = producer.get_heygen_api_key()
    if not producer_api_key:
        return False, "El productor todavía no configuró su API key de HeyGen.", "warning"

    owner_api_key = _get_owner_api_key()
    if not owner_api_key:
        return False, "No hay API key configurada para el dueño de la plataforma.", "warning"

    base_url = current_app.config.get("HEYGEN_BASE_URL", "https://api.heygen.com") if current_app else "https://api.heygen.com"

    try:
        producer_service = HeyGenService(producer_api_key, base_url)
        owner_service = HeyGenService(owner_api_key, base_url)

        producer_avatars = producer_service.list_avatars()
        owner_avatars = owner_service.list_avatars()
    except Exception as exc:  # pragma: no cover - fallback ante errores de red
        return False, f"Error al comunicarse con HeyGen: {exc}", "danger"

    if not producer_avatars:
        return True, "API key válida. No se encontraron avatares en HeyGen para sincronizar.", "info"

    owner_ids = _collect_ids(owner_avatars)

    new_count = 0
    updated_count = 0
    now_iso = datetime.utcnow().isoformat()

    try:
        for item in producer_avatars:
            avatar_id = _normalize_avatar_id(item)
            if not avatar_id or avatar_id in owner_ids:
                continue

            avatar = Avatar.query.filter_by(producer_id=producer.id, avatar_ref=avatar_id).first()

            preview_url = _extract_first(item, "preview_url", "previewVideoUrl", "preview_video_url")
            thumb_url = _extract_first(item, "preview_image_url", "thumbnail_url", "cover_image_url")
            language = _extract_first(item, "language", "default_language", default="es")
            avatar_type = _extract_first(item, "avatar_type", "category", "gender", default="video")
            name = _extract_first(item, "name", "display_name", default=f"Avatar {avatar_id}")
            description = _extract_first(item, "description", "bio")
            tags = item.get("tags") or item.get("labels") or []

            if not avatar:
                avatar = Avatar(
                    producer_id=producer.id,
                    created_by_id=producer.user_id,
                    name=name,
                    description=description,
                    avatar_type=avatar_type,
                    language=language,
                    avatar_ref=avatar_id,
                    preview_video_url=preview_url,
                    thumbnail_url=thumb_url,
                    status=AvatarStatus.ACTIVE,
                    enabled_by_admin=True,
                    enabled_by_producer=True,
                    enabled_by_subproducer=True,
                    meta_data={
                        "synced_from": "heygen",
                        "heygen_payload": item,
                        "synced_at": now_iso,
                    },
                )
                db.session.add(avatar)
                if tags:
                    avatar.set_tags(tags if isinstance(tags, (list, tuple)) else str(tags))
                new_count += 1
            else:
                avatar.name = name or avatar.name
                avatar.description = description or avatar.description
                avatar.avatar_type = avatar_type or avatar.avatar_type
                avatar.language = language or avatar.language
                avatar.preview_video_url = preview_url or avatar.preview_video_url
                avatar.thumbnail_url = thumb_url or avatar.thumbnail_url
                avatar.status = AvatarStatus.ACTIVE
                avatar.enabled_by_admin = True
                avatar.enabled_by_producer = True
                avatar.enabled_by_subproducer = True

                meta_data = avatar.meta_data or {}
                meta_data.update({
                    "synced_from": "heygen",
                    "synced_at": now_iso,
                    "heygen_payload": item,
                })
                avatar.meta_data = meta_data
                if tags:
                    avatar.set_tags(tags if isinstance(tags, (list, tuple)) else str(tags))
                updated_count += 1

        if new_count or updated_count:
            db.session.commit()

    except SQLAlchemyError as db_error:
        db.session.rollback()
        return False, f"Error guardando avatares sincronizados: {db_error}", "danger"

    if new_count or updated_count:
        parts = []
        if new_count:
            parts.append(f"{new_count} nuevos")
        if updated_count:
            parts.append(f"{updated_count} actualizados")
        detail = ", ".join(parts)
        return True, f"Sincronización de HeyGen completada ({detail}).", "success"

    return True, "API key validada. No había avatares nuevos para sincronizar.", "info"
