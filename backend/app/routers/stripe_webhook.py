import os
import stripe
from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/api/webhooks", tags=["stripe"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")

@router.post("/stripe")
async def stripe_webhook(request: Request):
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET manquant")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    if not sig_header:
        raise HTTPException(status_code=400, detail="Header Stripe-Signature manquant")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=webhook_secret,
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Signature webhook invalide")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    # ✅ Event principal : paiement Checkout confirmé
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        # session.get("metadata", {}) contiendra order_id plus tard
        print("✅ checkout.session.completed:", session.get("id"))

    return {"received": True}
