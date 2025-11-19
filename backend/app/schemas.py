from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# -------------------------
#  CARTES SMARTCARD
# -------------------------

class CardBase(BaseModel):
    """
    Champs communs pour une carte.
    Ces noms DOIVENT être identiques à ceux envoyés par le front.
    """
    company_name: str
    slug: str
    google_review_link: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    payment_link: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    theme_color: Optional[str] = "#2563EB"


class CardCreate(CardBase):
    """
    Schéma pour créer une carte (POST /api/cards/).
    Pas de user_id dans le body : on le fixe à 1 côté backend.
    """
    pass


class CardUpdate(BaseModel):
    """
    Schéma pour mise à jour partielle (PUT /api/cards/{id}).
    Tout est optionnel.
    """
    company_name: Optional[str] = None
    slug: Optional[str] = None
    google_review_link: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    payment_link: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    theme_color: Optional[str] = None


class CardPublic(BaseModel):
    """
    Schéma renvoyé au front (admin + carte publique).
    """
    id: int
    company_name: str
    slug: str
    google_review_link: Optional[str] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    payment_link: Optional[str] = None
    instagram: Optional[str] = None
    facebook: Optional[str] = None
    tiktok: Optional[str] = None
    theme_color: Optional[str] = "#2563EB"
    qr_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# Alias pour ne plus casser les imports qui parlent de CardOut
class CardOut(CardPublic):
    """
    Compatibilité : certains endpoints utilisent encore CardOut comme response_model.
    """
    pass


# -------------------------
#  FEEDBACKS
# -------------------------

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


# -------------------------
#  DEMANDES DE DEVIS
# -------------------------

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


# -------------------------
#  UTILISATEURS
# -------------------------

class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True



