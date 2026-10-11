from pathlib import Path
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from app.utils.admin_auth import (
    ADMIN_SESSION_MAX_AGE_SECONDS,
    clear_admin_session,
    create_admin_session,
    is_admin_session_valid,
    require_admin_session,
    validate_admin_password,
)
from app.utils.rate_limit import rate_limit_by_ip


router = APIRouter(tags=["admin-session"])
_ADMIN_STATIC_DIR = Path(__file__).resolve().parents[2] / "static" / "admin"
_NO_STORE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "Expires": "0",
}


class AdminLoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


@router.get("/admin/login", include_in_schema=False)
def admin_login_page(request: Request):
    if is_admin_session_valid(request):
        return RedirectResponse(url="/admin", status_code=status.HTTP_303_SEE_OTHER)
    file_path = _ADMIN_STATIC_DIR / "login.html"
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Page de connexion introuvable.")
    return FileResponse(
        path=str(file_path),
        media_type="text/html; charset=utf-8",
        headers=_NO_STORE_HEADERS,
    )


@router.post("/api/admin/session/login")
def admin_login(
    payload: AdminLoginRequest,
    request: Request,
    _: None = Depends(rate_limit_by_ip(5, 5 * 60)),
):
    if not validate_admin_password(payload.password):
        clear_admin_session(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mot de passe administrateur invalide.",
        )
    csrf_token, _expires_at = create_admin_session(request)
    return JSONResponse(
        {
            "authenticated": True,
            "csrf_token": csrf_token,
            "expires_in": ADMIN_SESSION_MAX_AGE_SECONDS,
        },
        headers=_NO_STORE_HEADERS,
    )


@router.get("/api/admin/session")
def admin_session_status(request: Request):
    require_admin_session(request)
    return JSONResponse(
        {
            "authenticated": True,
            "csrf_token": request.session["admin_csrf"],
            "expires_in": max(
                0,
                int(request.session["admin_expires_at"])
                - int(time.time()),
            ),
        },
        headers=_NO_STORE_HEADERS,
    )


@router.post("/api/admin/session/logout", status_code=status.HTTP_204_NO_CONTENT)
def admin_logout(request: Request):
    require_admin_session(request, require_csrf=True)
    clear_admin_session(request)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=_NO_STORE_HEADERS)
