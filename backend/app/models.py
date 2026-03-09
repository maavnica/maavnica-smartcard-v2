from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship

from .database import Base


# =============================================================
#  UTILISATEURS
# =============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relations
    cards = relationship("Card", back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"


# =============================================================
#  CARTES SMARTCARD
# =============================================================

class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Infos business
    company_name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)

    # 🔹 NOUVEAUX CHAMPS – PROFIL & INFOS DIGITALES
    # Type de SmartCard / profil métier :
    # 'artisan', 'digital', 'bien_etre', 'medical', 'immo', 'resto', 'generic', etc.
    profile = Column(String, nullable=False, default="artisan")

    # Email professionnel affiché sur la carte
    email_pro = Column(String, nullable=True)

    # Site web / page principale (vitrine, booking, etc.)
    site_web = Column(String, nullable=True)

    # Liens & contact
    google_review_link = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)
    payment_link = Column(String, nullable=True)
    instagram = Column(String, nullable=True)
    facebook = Column(String, nullable=True)
    tiktok = Column(String, nullable=True)

    # Visuel
    avatar_url = Column(String, nullable=True)  # URL de la photo / du logo
    # Thème visuel (apple, material, black-gold, artisan)
    theme = Column(String, nullable=False, default="apple")
    # Couleur principale personnalisable
    theme_color = Column(String, nullable=True, default="#2563EB")

    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relations
    user = relationship("User", back_populates="cards")
    feedbacks = relationship(
        "Feedback",
        back_populates="card",
        cascade="all, delete-orphan",
    )
    quotes = relationship(
        "Quote",
        back_populates="card",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Card id={self.id} slug={self.slug!r} "
            f"company_name={self.company_name!r} profile={self.profile!r}>"
        )


# =============================================================
#  FEEDBACKS
# =============================================================

class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)

    satisfaction = Column(Boolean, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relation
    card = relationship("Card", back_populates="feedbacks")

    def __repr__(self) -> str:
        return f"<Feedback id={self.id} card_id={self.card_id}>"


# =============================================================
#  DEMANDES DE DEVIS
# =============================================================

class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)

    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relation
    card = relationship("Card", back_populates="quotes")

    def __repr__(self) -> str:
        return f"<Quote id={self.id} card_id={self.card_id} name={self.name!r}>"


