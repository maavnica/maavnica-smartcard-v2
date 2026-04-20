import os
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials


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


def admin_bearer_matches(request: Request) -> bool:
    """
    True si la requête porte Authorization: Bearer <ADMIN_API_KEY> valide.
    Utile pour enrichir une réponse JSON (ex. clé mode propriétaire) sans rendre l’auth obligatoire.
    """
    expected = (os.getenv("ADMIN_API_KEY") or "").strip()
    if not expected:
        return False
    auth = request.headers.get("Authorization", "") or ""
    if not auth.lower().startswith("bearer "):
        return False
    provided = auth[7:].strip()
    return secrets.compare_digest(provided, expected)


_http_basic = HTTPBasic()


def require_admin_http_basic(
    credentials: HTTPBasicCredentials = Depends(_http_basic),
) -> None:
    """
    Auth pour pages SSR (navigateur) : Basic auth.
    Utilisateur fixe : admin — mot de passe : valeur de ADMIN_API_KEY.
    """
    expected = (os.getenv("ADMIN_API_KEY") or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_API_KEY manquante côté serveur.",
        )
    if credentials.username != "admin":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers={"WWW-Authenticate": "Basic"},
        )
    if not secrets.compare_digest(credentials.password, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return None

