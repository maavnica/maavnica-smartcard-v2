from datetime import datetime
from typing import Optional

import re

from pydantic import BaseModel, EmailStr, Field, validator

# Règles communes anti-spam (contact, feedback, devis public)
_URL_PATTERN = re.compile(r"(https?://|www\.)", re.IGNORECASE)
_EMAIL_IN_TEXT_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)
_PHONE_PATTERN = re.compile(r"^[0-9+\-\s()./]{6,25}$")
_AFFILIATE_REF_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


def _reject_urls_and_angle_brackets(v: str) -> str:
    if _URL_PATTERN.search(v):
        raise ValueError("Les URLs ne sont pas autorisées dans ce champ.")
    if "<" in v or ">" in v:
        raise ValueError("Contenu invalide.")
    return v


def _reject_email_like_in_text(v: str) -> str:
    if _EMAIL_IN_TEXT_PATTERN.search(v):
        raise ValueError("Les adresses e-mail ne sont pas autorisées dans ce champ.")
    return v


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
    google_rating: Optional[float] = None
    google_review_count: Optional[int] = None
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
    google_rating: Optional[float] = None
    google_review_count: Optional[int] = None
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
    google_rating: Optional[float] = None
    google_review_count: Optional[int] = None
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
    comment: Optional[str] = Field(None, max_length=2000)

    @validator("comment", pre=True)
    def _feedback_comment_empty(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip() if isinstance(v, str) else v

    @validator("comment")
    def _feedback_comment_rules(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = _reject_urls_and_angle_brackets(v)
        return _reject_email_like_in_text(v)


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
    name: str = Field(..., min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=25)
    message: Optional[str] = Field(None, max_length=5000)

    @validator("name", "phone", "message", pre=True)
    def _quote_strip(cls, v):
        if v is None:
            return v
        return v.strip() if isinstance(v, str) else v

    @validator("email", pre=True)
    def _quote_email_empty(cls, v):
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return None
        return str(v).strip() if isinstance(v, str) else v

    @validator("name")
    def _quote_name(cls, v: str) -> str:
        return _reject_urls_and_angle_brackets(v)

    @validator("phone")
    def _quote_phone(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return v
        if not _PHONE_PATTERN.match(v):
            raise ValueError("Numéro de téléphone invalide.")
        return _reject_urls_and_angle_brackets(v)

    @validator("message")
    def _quote_message(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        v = _reject_urls_and_angle_brackets(v)
        return _reject_email_like_in_text(v)


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
#  CONTACT SMARTCARD (Landing)
# =============================================================


class ContactRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=80)
    last_name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    phone: str = Field(default="", min_length=0, max_length=25)
    company_name: str = Field(default="", min_length=0, max_length=120)
    message: str = Field(default="", min_length=0, max_length=4000)
    source: str = Field(..., min_length=1, max_length=80)
    honey: str = Field(default="", max_length=200)
    affiliate_ref: str = Field(default="", max_length=32)

    @validator("affiliate_ref", pre=True)
    def affiliate_ref_normalize(cls, v):
        if v is None or not isinstance(v, str):
            return ""
        return v.strip().lower()

    @validator("affiliate_ref")
    def affiliate_ref_validate(cls, v: str) -> str:
        if not v:
            return v
        if not _AFFILIATE_REF_PATTERN.fullmatch(v):
            raise ValueError("Référence affiliation invalide.")
        return v

    @validator("first_name", "last_name", "phone", "company_name", "message", "source", "honey", pre=True)
    def strip_strings(cls, v):
        return v.strip() if isinstance(v, str) else v

    @validator("first_name", "last_name", "phone", "company_name", "message", "source")
    def block_urls_in_text_fields(cls, v: str) -> str:
        return _reject_urls_and_angle_brackets(v)

    @validator("phone")
    def validate_phone_format(cls, v: str) -> str:
        if not v:
            return v
        if not _PHONE_PATTERN.match(v):
            raise ValueError("Numéro de téléphone invalide.")
        return v


# =============================================================
#  KIT AFFILIÉ (outil interne — envoi email)
# =============================================================


class AffiliateKitSendRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=80)
    last_name: str = Field(..., min_length=1, max_length=80)
    email: EmailStr
    affiliate_ref: str = Field(..., min_length=1, max_length=32)

    @validator("first_name", "last_name", "affiliate_ref", pre=True)
    def strip_affiliate_kit_strings(cls, v):
        return v.strip() if isinstance(v, str) else v

    @validator("affiliate_ref", pre=True)
    def affiliate_kit_ref_lower(cls, v):
        if not isinstance(v, str):
            return ""
        return v.strip().lower()

    @validator("affiliate_ref")
    def affiliate_kit_ref_validate(cls, v: str) -> str:
        if not _AFFILIATE_REF_PATTERN.fullmatch(v):
            raise ValueError("Référence affiliation invalide.")
        return v

    @validator("first_name", "last_name")
    def affiliate_kit_names_no_url(cls, v: str) -> str:
        return _reject_urls_and_angle_brackets(v)


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



