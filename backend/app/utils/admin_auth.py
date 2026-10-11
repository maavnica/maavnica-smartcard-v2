import base64
import binascii
import os
import secrets
import time
from threading import Lock
from urllib.parse import quote, urlsplit

from fastapi import HTTPException, Request, status


ADMIN_SESSION_MAX_AGE_SECONDS = 8 * 60 * 60
ADMIN_SESSION_COOKIE = "smartcard_admin_session"
ADMIN_SESSION_CSRF_HEADER = "X-CSRF-Token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
_MAX_ACTIVE_ADMIN_SESSIONS = 1000
_active_admin_sessions: dict[str, int] = {}
_active_admin_sessions_lock = Lock()


def _expected_admin_secret() -> str:
    return (os.getenv("ADMIN_API_KEY") or "").strip()


def _request_session(request: Request) -> dict:
    try:
        return request.session
    except (AssertionError, RuntimeError):
        return {}


def is_admin_session_valid(request: Request) -> bool:
    session = _request_session(request)
    if session.get("admin_authenticated") is not True:
        return False
    session_id = str(session.get("admin_session_id") or "")
    try:
        expires_at = int(session.get("admin_expires_at", 0))
    except (TypeError, ValueError):
        return False
    now = int(time.time())
    if not session_id or expires_at <= now or not session.get("admin_csrf"):
        return False
    with _active_admin_sessions_lock:
        registered_expiry = _active_admin_sessions.get(session_id)
        if registered_expiry is None or registered_expiry != expires_at:
            return False
        if registered_expiry <= now:
            _active_admin_sessions.pop(session_id, None)
            return False
    return True


def create_admin_session(request: Request) -> tuple[str, int]:
    csrf_token = secrets.token_urlsafe(32)
    session_id = secrets.token_urlsafe(32)
    expires_at = int(time.time()) + ADMIN_SESSION_MAX_AGE_SECONDS
    now = int(time.time())
    with _active_admin_sessions_lock:
        expired = [
            active_id
            for active_id, active_expiry in _active_admin_sessions.items()
            if active_expiry <= now
        ]
        for active_id in expired:
            _active_admin_sessions.pop(active_id, None)
        if len(_active_admin_sessions) >= _MAX_ACTIVE_ADMIN_SESSIONS:
            oldest_id = min(
                _active_admin_sessions,
                key=_active_admin_sessions.__getitem__,
            )
            _active_admin_sessions.pop(oldest_id, None)
        _active_admin_sessions[session_id] = expires_at
    request.session.clear()
    request.session.update(
        {
            "admin_authenticated": True,
            "admin_session_id": session_id,
            "admin_expires_at": expires_at,
            "admin_csrf": csrf_token,
        }
    )
    return csrf_token, expires_at


def get_admin_csrf_token(request: Request) -> str:
    if not is_admin_session_valid(request):
        return ""
    return str(_request_session(request).get("admin_csrf") or "")


def clear_admin_session(request: Request) -> None:
    session = _request_session(request)
    session_id = str(session.get("admin_session_id") or "")
    if session_id:
        with _active_admin_sessions_lock:
            _active_admin_sessions.pop(session_id, None)
    session.clear()


def validate_admin_password(password: str) -> bool:
    expected = _expected_admin_secret()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_API_KEY manquante côté serveur.",
        )
    return secrets.compare_digest(str(password or ""), expected)


def _bearer_auth_state(request: Request) -> str:
    """Retourne valid, invalid ou absent sans exposer la clé."""
    auth = request.headers.get("Authorization", "") or ""
    if not auth.lower().startswith("bearer "):
        return "absent"
    provided = auth[7:].strip()
    expected = _expected_admin_secret()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_API_KEY manquante côté serveur.",
        )
    if provided and secrets.compare_digest(provided, expected):
        return "valid"
    return "invalid"


def _basic_auth_state(request: Request) -> str:
    auth = request.headers.get("Authorization", "") or ""
    if not auth.lower().startswith("basic "):
        return "absent"
    try:
        decoded = base64.b64decode(auth[6:].strip(), validate=True).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError, binascii.Error):
        return "invalid"
    expected = _expected_admin_secret()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADMIN_API_KEY manquante côté serveur.",
        )
    if username == "admin" and secrets.compare_digest(password, expected):
        return "valid"
    return "invalid"


def validate_admin_csrf(request: Request, provided_token: str | None = None) -> None:
    session = _request_session(request)
    expected = str(session.get("admin_csrf") or "")
    provided = str(
        provided_token
        if provided_token is not None
        else request.headers.get(ADMIN_SESSION_CSRF_HEADER, "")
    )
    if not expected or not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Jeton CSRF invalide.",
        )


def require_admin_session(request: Request, *, require_csrf: bool = False) -> None:
    if not is_admin_session_valid(request):
        clear_admin_session(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session administrateur expirée ou absente.",
        )
    if require_csrf or request.method.upper() not in _SAFE_METHODS:
        validate_admin_csrf(request)


def require_admin_api_key(request: Request) -> None:
    """
    Auth admin par Bearer historique ou session web.

    Le Bearer reste accepté pour les outils existants. Une requête web utilisant
    le cookie de session doit fournir le jeton CSRF pour toute méthode mutante.
    """
    bearer_state = _bearer_auth_state(request)
    if bearer_state == "valid":
        return None
    if bearer_state == "invalid":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Clé admin invalide.",
        )

    require_admin_session(request)
    return None


def admin_bearer_matches(request: Request) -> bool:
    """
    True si la requête porte Authorization: Bearer <ADMIN_API_KEY> valide.
    Utile pour enrichir une réponse JSON (ex. clé mode propriétaire) sans rendre l’auth obligatoire.
    """
    return _bearer_auth_state(request) == "valid"


def admin_request_matches(request: Request) -> bool:
    """True pour un Bearer valide ou une session administrateur valide."""
    return admin_bearer_matches(request) or is_admin_session_valid(request)


def require_admin_http_basic(request: Request) -> str:
    """
    Auth des pages SSR par session, avec compatibilité Basic historique.

    Utilisateur Basic fixe : admin — mot de passe : valeur de ADMIN_API_KEY.
    """
    if is_admin_session_valid(request):
        return "session"

    basic_state = _basic_auth_state(request)
    if basic_state == "valid":
        return "basic"
    if basic_state == "invalid":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
            headers={"WWW-Authenticate": "Basic"},
        )

    next_path = request.url.path
    if request.url.query:
        next_path += "?" + request.url.query
    location = "/admin/login?next=" + quote(next_path, safe="")
    raise HTTPException(
        status_code=status.HTTP_303_SEE_OTHER,
        detail="Connexion administrateur requise.",
        headers={"Location": location},
    )


def validate_page_csrf(
    request: Request,
    auth_mode: str,
    provided_token: str,
) -> None:
    if auth_mode == "session":
        validate_admin_csrf(request, provided_token)
        return

    # Compatibilité Basic pour les outils existants : les clients non-navigateurs
    # sans Origin restent acceptés, mais une soumission navigateur cross-site est refusée.
    source = (request.headers.get("origin") or request.headers.get("referer") or "").strip()
    if not source:
        return
    parsed = urlsplit(source)
    expected_host = (
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or request.url.netloc
    ).split(",")[0].strip().lower()
    expected_scheme = (
        request.headers.get("x-forwarded-proto") or request.url.scheme
    ).split(",")[0].strip().lower()
    if (
        parsed.netloc.lower() != expected_host
        or parsed.scheme.lower() != expected_scheme
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origine de la requête invalide.",
        )

