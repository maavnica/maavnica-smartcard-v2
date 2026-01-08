import os, uuid
import stripe
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from app.db import get_engine

router = APIRouter(prefix="/api", tags=["checkout"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://maavnica-smartcard-v2.onrender.com"
)

PRICE_SOLO = os.getenv("STRIPE_PRICE_SOLO")
PRICE_BUSINESS = os.getenv("STRIPE_PRICE_BUSINESS")


class CheckoutIn(BaseModel):
    offer: str
    email: EmailStr
    fullname: str
    phone: str | None = None
    company: str | None = None
    request: str | None = None


@router.post("/create-checkout")
def create_checkout(data: CheckoutIn):
    offer = data.offer.lower()

    if offer not in ("solo", "business"):
        raise HTTPException(400, "Offre invalide")

    price_id = PRICE_SOLO if offer == "solo" else PRICE_BUSINESS
    if not price_id:
        raise HTTPException(500, "PRICE_ID Stripe manquant")

    order_id = f"SC-{uuid.uuid4().hex[:8].upper()}"

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO ordres (order_id, offer, email)
            VALUES (:order_id, :offer, :email)
        """), {
            "order_id": order_id,
            "offer": offer,
            "email": data.email
        })

    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{
            "price": price_id,
            "quantity": 1
        }],
        customer_email=data.email,
        success_url=f"{PUBLIC_BASE_URL}/success?order_id={order_id}",
        cancel_url=f"{PUBLIC_BASE_URL}/static/contact-smartcard.html?offre={offer}",
        metadata={
            "order_id": order_id,
            "offer": offer
        }
    )

    return {
        "checkout_url": session.url,
        "order_id": order_id
    }
