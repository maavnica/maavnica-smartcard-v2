import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

# Rate limiting in-memory (simple / minimal).
# NB: ceci est suffisant pour un patch court terme, mais non partagé entre instances.

_RATE_LIMIT_WINDOW_SECONDS_DEFAULT = 60
_RATE_LIMIT_MAX_REQUESTS_DEFAULT = 5

_buckets: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()

# Pour éviter un DoS mémoire via un grand nombre d'IPs différentes.
_MAX_BUCKETS = 50000


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit_by_ip(limit: int, window_seconds: int = _RATE_LIMIT_WINDOW_SECONDS_DEFAULT):
    """
    Dépendance FastAPI.
    Limite N requêtes par fenêtre de temps par IP + path.
    """

    def _dependency(request: Request) -> None:
        nonlocal limit, window_seconds

        ip = _get_client_ip(request)
        key = f"{ip}:{request.url.path}"
        now = time.monotonic()

        with _lock:
            # Si trop de keys, on purge : stratégie conservative pour ne pas exploser la mémoire.
            if len(_buckets) > _MAX_BUCKETS:
                _buckets.clear()

            q = _buckets[key]
            while q and (now - q[0]) > window_seconds:
                q.popleft()

            if len(q) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Trop de tentatives. Réessayez plus tard.",
                )

            q.append(now)

        return None

    return _dependency

