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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # relation vers les cartes
    cards = relationship("Card", back_populates="user")


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    company_name = Column(String, nullable=False)
    slug = Column(String, unique=True, index=True, nullable=False)

    # ⬇⬇⬇ maintenant nullable=True pour éviter l'erreur NOT NULL
    google_review_link = Column(String, nullable=True)

    phone = Column(String, nullable=True)
    whatsapp = Column(String, nullable=True)
    payment_link = Column(String, nullable=True)

    instagram = Column(String, nullable=True)
    facebook = Column(String, nullable=True)
    tiktok = Column(String, nullable=True)

    theme_color = Column(String, nullable=True, default="#2563EB")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # relations
    user = relationship("User", back_populates="cards")
    feedbacks = relationship("Feedback", back_populates="card", cascade="all, delete-orphan")
    quotes = relationship("Quote", back_populates="card", cascade="all, delete-orphan")


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)

    satisfaction = Column(Boolean, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("Card", back_populates="feedbacks")


class Quote(Base):
    __tablename__ = "quotes"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)

    name = Column(String, nullable=False)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("Card", back_populates="quotes")

