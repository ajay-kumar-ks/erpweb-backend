try:
    import razorpay
    RAZORPAY_AVAILABLE = True
except ImportError:
    razorpay = None
    RAZORPAY_AVAILABLE = False

import hmac
import hashlib
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for handling Razorpay payment operations."""

    def __init__(self):
        if not RAZORPAY_AVAILABLE:
            raise ImportError(
                "razorpay package is not installed. Install it with: pip install razorpay"
            )
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.client = razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_order(self, amount: int, currency: str = "INR", receipt_id: Optional[str] = None,
                     notes: Optional[dict] = None) -> dict:
        """Create a Razorpay order."""
        order_data = {
            "amount": amount,
            "currency": currency,
            "receipt": receipt_id,
            "notes": notes or {},
        }
        # Remove None values
        order_data = {k: v for k, v in order_data.items() if v is not None}

        try:
            order = self.client.order.create(data=order_data)
            logger.info(f"Razorpay order created: {order.get('id')}")
            return order
        except Exception as e:
            logger.error(f"Failed to create Razorpay order: {e}")
            raise

    def verify_payment(self, order_id: str, payment_id: str, signature: str) -> bool:
        """Verify Razorpay payment signature."""
        expected_signature = hmac.new(
            self.key_secret.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    def fetch_payment(self, payment_id: str) -> dict:
        """Fetch payment details from Razorpay."""
        try:
            return self.client.payment.fetch(payment_id)
        except Exception as e:
            logger.error(f"Failed to fetch payment {payment_id}: {e}")
            raise

    def get_key_id(self) -> str:
        return self.key_id


# Singleton instance — will only raise at runtime when first used
payment_service = None if not RAZORPAY_AVAILABLE else PaymentService()
