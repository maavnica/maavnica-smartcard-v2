from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# =============================================================
#  SMARTCARD — BASE
# =============================================================

class CardBase(BaseModel):
    """
    Champs communs pour la SmartCard.
    IMPORTANT : les clés doivent correspondre exactement à celles envoyées par le front.
    """
    company_name: str
    slug: str

    # 🔹 NOUVEAUX CHAMPS — PROFIL & INFOS MÉTIER
    #   artisan, digital, bien_etre, medical, immo, resto, generic…
    profile: str = "artisan"
    email_pro: Optional[str] = None
    site_web: Optional[str] = None

    # 🔹 Contact & actions
    google_review_link: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    payment_link: Optional[str] = None

    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None

    # 🔹 Visuel
    avatar_url: Optional[str] = None
    theme: str = "apple"                  # apple, material, black-gold, artisan…
    theme_color: Optional[str] = "#2563EB"  # couleur dominante (hex)


# =============================================================
#  SMARTCARD — CRÉATION / MISE À JOUR
# =============================================================

class CardCreate(CardBase):
    """Schéma pour création d’une carte. Le user_id est forcé côté backend."""
    pass


class CardUpdate(BaseModel):
    """
    Mise à jour partielle — tous les champs sont optionnels.
    Utilisé en PUT/PATCH /api/cards/{id}
    """
    company_name: Optional[str] = None
    slug: Optional[str] = None

    # 🔹 Nouveaux champs
    profile: Optional[str] = None
    email_pro: Optional[str] = None
    site_web: Optional[str] = None

    google_review_link: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    payment_link: Optional[str] = None

    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None

    avatar_url: Optional[str] = None
    theme: Optional[str] = None
    theme_color: Optional[str] = None


# =============================================================
#  SMARTCARD — RÉPONSE API (PUBLIC + ADMIN)
# =============================================================

class CardPublic(BaseModel):
    """Schéma complet renvoyé au front (admin & carte publique)."""

    id: int
    company_name: str
    slug: str

    # 🔹 Nouveaux champs
    profile: str
    email_pro: Optional[str]
    site_web: Optional[str]

    google_review_link: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    payment_link: Optional[str] = None

    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None

    theme: str = "apple"
    theme_color: Optional[str] = "#2563EB"

    avatar_url: Optional[str] = None

    qr_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        # Permet de faire `return card` directement avec un objet SQLAlchemy
        orm_mode = True


# Compatibilité ancienne version
class CardOut(CardPublic):
    pass


# =============================================================
#  FEEDBACKS (Avis rapides)
# =============================================================

class FeedbackCreate(BaseModel):
    satisfaction: bool
    comment: Optional[str] = None


class FeedbackOut(BaseModel):
    id: int
    satisfaction: bool
    comment: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


# =============================================================
#  DEMANDES DE DEVIS
# =============================================================

class QuoteCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None


class QuoteOut(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    message: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


# =============================================================
#  UTILISATEURS
# =============================================================

class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True



