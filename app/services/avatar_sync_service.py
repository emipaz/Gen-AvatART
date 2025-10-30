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
from app.models.user import User
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
    env_key = os.environ.get("HEYGEN_API_KEY_OWNER")
    if env_key:
        return env_key

    try:
        owner = User.query.filter_by(is_owner=True).first()
        if owner and getattr(owner, "producer_profile", None):
            return owner.producer_profile.get_heygen_api_key()
    except Exception:  # pragma: no cover - fallback silencioso
        return None

    return None


def sync_producer_heygen_avatars(producer: Producer) -> SyncResult:
    """Sincroniza los avatares propios del productor contra HeyGen.

    Descarga el catálogo del productor y le resta los avatares visibles para el dueño
    de la plataforma para evitar listar clones públicos. Los avatares exclusivos del
    productor se insertan o actualizan en la base local.

    Returns:
        tuple: (éxito, mensaje, categoria_flash)
    """
    import logging
    logger = logging.getLogger("avatar_sync")

    producer_api_key = producer.get_heygen_api_key()
    logger.info(f"[SYNC] Productor: {producer.id} - API Key: {'SET' if producer_api_key else 'NOT SET'}")
    if not producer_api_key:
        logger.warning("[SYNC] El productor no tiene API key de HeyGen configurada.")
        return False, "El productor todavía no configuró su API key de HeyGen.", "warning"

    owner_api_key = _get_owner_api_key()
    logger.info(f"[SYNC] Owner API Key: {'SET' if owner_api_key else 'NOT SET'}")
    if not owner_api_key:
        logger.warning("[SYNC] No hay API key configurada para el dueño de la plataforma.")
        return False, "No hay API key configurada para el dueño de la plataforma.", "warning"

    base_url = current_app.config.get("HEYGEN_BASE_URL", "https://api.heygen.com") if current_app else "https://api.heygen.com"
    logger.info(f"[SYNC] Base URL: {base_url}")

    try:
        producer_service = HeyGenService(producer_api_key, base_url)
        owner_service = HeyGenService(owner_api_key, base_url)

        producer_avatars = producer_service.list_avatars()
        owner_avatars = owner_service.list_avatars()
        logger.info(f"[SYNC] Avatares del productor recibidos: {len(producer_avatars) if producer_avatars else 0}")
        logger.info(f"[SYNC] Avatares del owner recibidos: {len(owner_avatars) if owner_avatars else 0}")
    except Exception as exc:  # pragma: no cover - fallback ante errores de red
        logger.error(f"[SYNC] Error al comunicarse con HeyGen: {exc}")
        return False, f"Error al comunicarse con HeyGen: {exc}", "danger"

    if not producer_avatars:
        logger.info("[SYNC] No se encontraron avatares en HeyGen para sincronizar.")
        return True, "API key válida. No se encontraron avatares en HeyGen para sincronizar.", "info"

    owner_ids = _collect_ids(owner_avatars)
    logger.info(f"[SYNC] IDs de avatares del owner: {owner_ids}")

    new_count = 0
    updated_count = 0
    now_iso = datetime.utcnow().isoformat()

    try:
        for item in producer_avatars:
            avatar_id = _normalize_avatar_id(item)
            logger.debug(f"[SYNC] Procesando avatar_id: {avatar_id}")
            if not avatar_id:
                logger.warning(f"[SYNC] Avatar sin ID válido: {item}")
                continue
            if avatar_id in owner_ids:
                logger.info(f"[SYNC] Avatar {avatar_id} es público/owner, se omite.")
                continue

            avatar = Avatar.query.filter_by(producer_id=producer.id, avatar_ref=avatar_id).first()
            logger.debug(f"[SYNC] Avatar en base local: {'ENCONTRADO' if avatar else 'NO ENCONTRADO'}")

            preview_url = _extract_first(item, "preview_url", "previewVideoUrl", "preview_video_url")
            thumb_url = _extract_first(item, "preview_image_url", "thumbnail_url", "cover_image_url")
            language = _extract_first(item, "language", "default_language", default="es")
            avatar_type = _extract_first(item, "avatar_type", "category", "gender", default="video")
            name = _extract_first(item, "name", "display_name", default=f"Avatar {avatar_id}")
            description = _extract_first(item, "description", "bio")
            tags = item.get("tags") or item.get("labels") or []

            if not avatar:
                logger.info(f"[SYNC] Creando nuevo avatar {avatar_id} para productor {producer.id}")
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
                logger.info(f"[SYNC] Actualizando avatar existente {avatar_id} para productor {producer.id}")
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
            logger.info(f"[SYNC] Commit a la base de datos. Nuevos: {new_count}, Actualizados: {updated_count}")
            db.session.commit()

    except SQLAlchemyError as db_error:
        logger.error(f"[SYNC] Error guardando avatares sincronizados: {db_error}")
        db.session.rollback()
        return False, f"Error guardando avatares sincronizados: {db_error}", "danger"

    if new_count or updated_count:
        parts = []
        if new_count:
            parts.append(f"{new_count} nuevos")
        if updated_count:
            parts.append(f"{updated_count} actualizados")
        detail = ", ".join(parts)
        logger.info(f"[SYNC] Sincronización de HeyGen completada ({detail})")
        return True, f"Sincronización de HeyGen completada ({detail}).", "success"

    logger.info("[SYNC] API key validada. No había avatares nuevos para sincronizar.")
    return True, "API key validada. No había avatares nuevos para sincronizar.", "info"
