import os

from fastapi import HTTPException, Request, status


def require_admin_api_key(request: Request) -> None:
    """
    Auth admin minimale par API key.

    Méthode attendue (cohérente) :
      Authorization: Bearer <ADMIN_API_KEY>
    """
    expected = (os.getenv("ADMIN_API_KEY") or "").strip()
    if not expected:
        # Fail-safe : si la clé n'est pas configurée, on refuse pour éviter une sécurité illusoire.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_API_KEY manquante côté serveur.",
        )

    auth = request.headers.get("Authorization", "") or ""
    if auth.lower().startswith("bearer "):
        provided = auth[7:].strip()
    else:
        provided = ""

    if not provided:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé admin manquante (Authorization: Bearer ...).",
        )

    if provided != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clé admin invalide.",
        )

    # Rien à retourner : le simple fait de passer la dépendance auth suffit.
    return None

