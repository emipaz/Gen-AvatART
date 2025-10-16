import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

from flask import current_app


def _snapshots_dir() -> str:
    """
    Carpeta base donde guardamos snapshots.
    Usamos instance_path si existe (escribe-safe), si no, la root del proyecto.
    """
    try:
        base = current_app.instance_path  # recomendado por Flask para data writable
    except RuntimeError:
        # Fuera de contexto de app (e.g., scripts), fallback al cwd
        base = os.getcwd()

    path = os.path.join(base, "snapshots", "avatars")
    os.makedirs(path, exist_ok=True)
    return path


def _avatar_snapshot_path(avatar_id: int) -> str:
    """Ruta del archivo JSON del snapshot de un avatar."""
    return os.path.join(_snapshots_dir(), f"{avatar_id}.json")


def _iso(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.utcnow()).isoformat(timespec="seconds")


def _redact_secrets(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Limpia claves sensibles en el payload (por si por error llegan).
    No toques los campos que realmente necesitás para recrear el avatar.
    """
    redacted = dict(payload or {})
    for key in list(redacted.keys()):
        k = key.lower()
        if "api_key" in k or "apikey" in k or "token" in k or "secret" in k:
            redacted[key] = "****"
    return redacted


def save_avatar_snapshot(
    *,
    avatar_id: int,
    producer_id: int,
    created_by_id: int,
    source: str,
    inputs: Dict[str, Any],
    heygen_owner_hint: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Guarda un snapshot JSON con toda la información necesaria para
    **re-crear** el avatar desde otra cuenta (p. ej., productor custodio).

    Params
    ------
    avatar_id:         ID del avatar recién creado (DB)
    producer_id:       Productor al momento de la creación (dueño de API)
    created_by_id:     Usuario que disparó la creación (producer/subproducer/API user)
    source:            'api' | 'producer_ui' | 'subproducer_ui' | otro texto corto
    inputs:            Payload original de entrada (name, description, type, language, tags, flags, etc.)
    heygen_owner_hint: Texto útil para auditoría (ej.: email de cuenta HeyGen o company_name)
    extra:             Metadatos opcionales (versiones, IP, user_agent, etc.)

    Devuelve True si se guardó correctamente.
    """
    try:
        # Sanitizar lo sensible por si viniera en inputs
        safe_inputs = _redact_secrets(inputs or {})

        snapshot = {
            "schema": "avatar_snapshot.v1",
            "avatar_id": avatar_id,
            "producer_id": producer_id,
            "created_by_id": created_by_id,
            "source": source,
            "inputs": safe_inputs,           # TODO: añadir aquí rutas/ids de medios si aplica
            "heygen_owner_hint": heygen_owner_hint,
            "extra": extra or {},
            "created_at": _iso(),
            # Futuras recreaciones podrán anexarse aquí:
            "recreate_history": [],
        }

        path = _avatar_snapshot_path(avatar_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        # Evitamos romper el flujo principal si falla el snapshot
        print(f"[snapshot] Error guardando snapshot de avatar {avatar_id}: {e}")
        return False


def load_avatar_snapshot(avatar_id: int) -> Optional[Dict[str, Any]]:
    """Lee el snapshot JSON de un avatar (o None si no existe)."""
    path = _avatar_snapshot_path(avatar_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[snapshot] Error leyendo snapshot de avatar {avatar_id}: {e}")
        return None


def append_recreate_log(avatar_id: int, *, by_user_id: int, note: str, new_owner_producer_id: Optional[int] = None) -> bool:
    """
    Agrega una entrada al historial de “recreaciones” (cuando el custodio rehace el avatar).
    Útil para auditoría.
    """
    data = load_avatar_snapshot(avatar_id)
    if not data:
        return False

    rec = {
        "at": _iso(),
        "by_user_id": by_user_id,
        "note": note,
        "new_owner_producer_id": new_owner_producer_id,
    }
    data.setdefault("recreate_history", []).append(rec)

    try:
        path = _avatar_snapshot_path(avatar_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[snapshot] Error actualizando recreate_history de avatar {avatar_id}: {e}")
        return False
