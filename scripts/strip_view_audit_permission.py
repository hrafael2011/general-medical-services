#!/usr/bin/env python
"""Quita el permiso `view_audit` de las listas de permisos de los usuarios.

La auditoría pasó a ser exclusiva del rol administrador (ver el spec
2026-10-09-mi-perfil-y-politica-contrasena.md), así que `view_audit` ya no existe
en el enum de permisos. Si la cadena se queda en `users.permissions`, guardar a
cualquiera de esos usuarios desde la pantalla de Usuarios falla con
"Permisos inválidos: view_audit".

Es idempotente: correrlo dos veces no hace nada la segunda vez. Acepta
`--dry-run` para ver qué cambiaría sin escribir.

Uso:
    python scripts/strip_view_audit_permission.py --dry-run
    python scripts/strip_view_audit_permission.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from backend.app.infrastructure.db.models.user import UserModel  # noqa: E402
from backend.app.infrastructure.db.session import SessionLocal  # noqa: E402

REMOVED_PERMISSION = "view_audit"


def strip(*, dry_run: bool) -> int:
    session = SessionLocal()
    try:
        users = list(session.scalars(select(UserModel)))
        affected = 0
        for user in users:
            permissions = list(user.permissions or [])
            if REMOVED_PERMISSION not in permissions:
                continue
            user.permissions = [p for p in permissions if p != REMOVED_PERMISSION]
            affected += 1
            after = len(user.permissions)
            print(f"  {user.name} ({user.email}): {len(permissions)} -> {after} permisos")

        if dry_run:
            session.rollback()
            print(f"\n[DRY RUN] {affected} usuario(s) cambiarían. Nada se guardó.")
        else:
            session.commit()
            print(f"\n{affected} usuario(s) actualizados.")
        return affected
    finally:
        session.close()


if __name__ == "__main__":
    strip(dry_run="--dry-run" in sys.argv)
