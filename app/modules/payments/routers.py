import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from app.core.database import get_db
from app.modules.auth.routers import get_current_user
from app.modules.auth.models import User
from .db_models import Payment, PaymentStatus
from .schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
    FailPaymentRequest,
    PaymentSchema,
    PaymentListResponse,
)
from .services import payment_service

router = APIRouter(tags=["payments"])


def _require_payment_service():
    if payment_service is None:
        raise HTTPException(
            status_code=501,
            detail="Payment service is not available. Install the 'razorpay' package and restart the server.",
        )
    return payment_service


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(
    data: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a Razorpay order and store it in the database."""
    # Create order with Razorpay
    receipt_id = f"rcpt_{uuid.uuid4().hex[:12]}"
    try:
        svc = _require_payment_service()
        razorpay_order = svc.create_order(
            amount=data.amount,
            currency=data.currency,
            receipt_id=receipt_id,
            notes={"customer_name": data.customer_name, "description": data.description},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create payment order: {str(e)}")

    # Store in database
    payment = Payment(
        id=str(uuid.uuid4()),
        razorpay_order_id=razorpay_order["id"],
        amount=data.amount,
        currency=data.currency,
        status=PaymentStatus.CREATED.value,
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        customer_phone=data.customer_phone,
        description=data.description,
        notes=data.notes or {},
        receipt_id=receipt_id,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)

    return CreateOrderResponse(
        razorpay_order_id=razorpay_order["id"],
        amount=data.amount,
        currency=data.currency,
        key_id=_require_payment_service().get_key_id(),
    )


@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(
    data: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify a Razorpay payment signature and update the payment status."""
    # Find the payment record
    payment = db.query(Payment).filter(
        Payment.razorpay_order_id == data.razorpay_order_id
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment order not found")

    # Verify signature
    is_valid = _require_payment_service().verify_payment(
        order_id=data.razorpay_order_id,
        payment_id=data.razorpay_payment_id,
        signature=data.razorpay_signature,
    )

    if not is_valid:
        payment.status = PaymentStatus.FAILED.value
        payment.razorpay_payment_id = data.razorpay_payment_id
        payment.razorpay_signature = data.razorpay_signature
        payment.updated_at = datetime.utcnow()
        db.commit()
        raise HTTPException(status_code=400, detail="Payment verification failed - invalid signature")

    # Update payment record
    payment.razorpay_payment_id = data.razorpay_payment_id
    payment.razorpay_signature = data.razorpay_signature
    payment.status = PaymentStatus.PAID.value
    payment.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(payment)

    return VerifyPaymentResponse(
        success=True,
        payment_id=payment.id,
        status=payment.status,
    )


@router.post("/fail")
async def fail_payment(
    data: FailPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a payment as failed (called when Razorpay checkout reports payment failure)."""
    payment = db.query(Payment).filter(
        Payment.razorpay_order_id == data.razorpay_order_id
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment order not found")

    # Only update if still in CREATED or ATTEMPTED state
    if payment.status in (PaymentStatus.CREATED.value, PaymentStatus.ATTEMPTED.value):
        payment.status = PaymentStatus.FAILED.value
        if data.razorpay_payment_id:
            payment.razorpay_payment_id = data.razorpay_payment_id
        payment.updated_at = datetime.utcnow()
        db.commit()

    return {"success": True, "status": payment.status}


@router.get("/", response_model=PaymentListResponse)
async def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all payments with optional status filter."""
    query = db.query(Payment)

    if status:
        query = query.filter(Payment.status == status)

    total = query.count()
    payments = query.order_by(Payment.created_at.desc()).offset(skip).limit(limit).all()

    return PaymentListResponse(
        payments=[PaymentSchema.model_validate(p) for p in payments],
        total=total,
    )


@router.get("/{payment_id}", response_model=PaymentSchema)
async def get_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single payment by ID."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return PaymentSchema.model_validate(payment)


@router.get("/key", response_model=dict)
async def get_razorpay_key(
    current_user: User = Depends(get_current_user),
):
    """Return the Razorpay key ID for frontend checkout initialization."""
    return {"key_id": _require_payment_service().get_key_id()}
