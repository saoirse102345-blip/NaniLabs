"""
AURA Infra - Stripe Payment Routes
API endpoints for real money transactions
"""

import os
from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db, WalletModel, AgentModel, TransactionModel, TransactionType, TransactionStatus
from stripe_integration import (
    StripeService, 
    STRIPE_PUBLISHABLE_KEY,
    create_deposit_link,
    verify_payment
)

import uuid
import json
from datetime import datetime

router = APIRouter(prefix="/payments", tags=["Stripe Payments"])


# ==================== REQUEST MODELS ====================

class CreateDepositRequest(BaseModel):
    wallet_id: str
    amount: float  # USD
    return_url: Optional[str] = None


class VerifyPaymentRequest(BaseModel):
    session_id: str


class CreatePaymentIntentRequest(BaseModel):
    wallet_id: str
    amount: float


# ==================== ENDPOINTS ====================

@router.get("/")
async def payments_root():
    """Stripe payments status"""
    return {
        "service": "AURA Payments",
        "provider": "Stripe",
        "status": "operational",
        "mode": "test" if "test" in STRIPE_PUBLISHABLE_KEY else "live",
        "features": [
            "Deposit to wallet (card)",
            "Checkout sessions",
            "Payment intents",
            "Webhooks"
        ]
    }


@router.get("/config")
async def get_stripe_config():
    """Get Stripe publishable key for frontend"""
    return {
        "publishable_key": STRIPE_PUBLISHABLE_KEY,
        "mode": "test" if "test" in STRIPE_PUBLISHABLE_KEY else "live"
    }


@router.post("/deposit/checkout")
async def create_deposit_checkout(
    request: CreateDepositRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a Stripe Checkout session for depositing funds.
    Returns a URL to redirect the user to for payment.
    """
    # Validate wallet exists
    result = await db.execute(
        select(WalletModel).where(WalletModel.id == request.wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Validate amount
    if request.amount < 1:
        raise HTTPException(status_code=400, detail="Minimum deposit is $1.00")
    if request.amount > 10000:
        raise HTTPException(status_code=400, detail="Maximum deposit is $10,000")
    
    # Create checkout session
    base_url = request.return_url or os.getenv("APP_URL", "https://nanilabs.io")
    
    result = StripeService.create_checkout_session(
        agent_id=wallet.agent_id,
        wallet_id=request.wallet_id,
        amount_usd=request.amount,
        success_url=f"{base_url}/deposit-success",
        cancel_url=f"{base_url}/deposit-cancel"
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Failed to create checkout"))
    
    return {
        "status": "checkout_created",
        "checkout_url": result["checkout_url"],
        "session_id": result["session_id"],
        "amount": request.amount,
        "message": "Redirect user to checkout_url to complete payment"
    }


@router.post("/deposit/intent")
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a PaymentIntent for embedded payment forms.
    Returns a client_secret for Stripe.js
    """
    # Validate wallet exists
    result = await db.execute(
        select(WalletModel).where(WalletModel.id == request.wallet_id)
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    if request.amount < 1:
        raise HTTPException(status_code=400, detail="Minimum deposit is $1.00")
    
    result = StripeService.create_payment_intent(
        amount_usd=request.amount,
        agent_id=wallet.agent_id,
        wallet_id=request.wallet_id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return {
        "status": "intent_created",
        "client_secret": result["client_secret"],
        "payment_intent_id": result["payment_intent_id"],
        "amount": request.amount
    }


@router.post("/verify")
async def verify_payment_session(
    request: VerifyPaymentRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify a payment was successful and credit the wallet.
    Call this after user returns from checkout.
    """
    result = StripeService.retrieve_checkout_session(request.session_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    if result["payment_status"] != "paid":
        return {
            "status": "pending",
            "payment_status": result["payment_status"],
            "message": "Payment not yet completed"
        }
    
    # Get wallet and credit it
    wallet_id = result["metadata"].get("wallet_id")
    amount = result["amount_total"]
    
    if not wallet_id:
        raise HTTPException(status_code=400, detail="Invalid session metadata")
    
    # Check if already processed (idempotency)
    existing = await db.execute(
        select(TransactionModel).where(
            TransactionModel.description.contains(request.session_id)
        )
    )
    if existing.scalar_one_or_none():
        return {
            "status": "already_processed",
            "message": "This payment has already been credited"
        }
    
    # Get wallet
    wallet_result = await db.execute(
        select(WalletModel).where(WalletModel.id == wallet_id)
    )
    wallet = wallet_result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    # Create transaction and credit wallet
    tx = TransactionModel(
        id=f"tx_{uuid.uuid4().hex[:16]}",
        wallet_id=wallet_id,
        type=TransactionType.DEPOSIT.value,
        amount=amount,
        status=TransactionStatus.COMPLETED.value,
        description=f"Stripe deposit - Session: {request.session_id}",
        metadata_json=json.dumps({
            "stripe_session_id": request.session_id,
            "source": "stripe_checkout"
        }),
        completed_at=datetime.now()
    )
    db.add(tx)
    
    wallet.balance += amount
    wallet.total_earned += amount
    wallet.total_transactions += 1
    
    await db.commit()
    
    return {
        "status": "success",
        "credited": True,
        "amount": amount,
        "wallet_id": wallet_id,
        "new_balance": wallet.balance,
        "transaction_id": tx.id
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Stripe webhooks for async payment events.
    Set this URL in Stripe Dashboard: https://api.nanilabs.io/payments/webhook
    """
    payload = await request.body()
    
    result = StripeService.process_webhook(payload, stripe_signature or "")
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    event_type = result["event_type"]
    data = result["data"]
    
    # Handle different event types
    if event_type == "checkout.session.completed":
        # Payment successful - credit wallet
        if data.get("payment_status") == "paid":
            wallet_id = data.get("metadata", {}).get("wallet_id")
            amount = data.get("amount_total", 0) / 100
            
            if wallet_id and amount > 0:
                # Check idempotency
                existing = await db.execute(
                    select(TransactionModel).where(
                        TransactionModel.description.contains(data.get("id", ""))
                    )
                )
                if not existing.scalar_one_or_none():
                    wallet_result = await db.execute(
                        select(WalletModel).where(WalletModel.id == wallet_id)
                    )
                    wallet = wallet_result.scalar_one_or_none()
                    
                    if wallet:
                        tx = TransactionModel(
                            id=f"tx_{uuid.uuid4().hex[:16]}",
                            wallet_id=wallet_id,
                            type=TransactionType.DEPOSIT.value,
                            amount=amount,
                            status=TransactionStatus.COMPLETED.value,
                            description=f"Stripe webhook deposit - {data.get('id')}",
                            metadata_json=json.dumps({
                                "stripe_session_id": data.get("id"),
                                "source": "stripe_webhook"
                            }),
                            completed_at=datetime.now()
                        )
                        db.add(tx)
                        wallet.balance += amount
                        wallet.total_earned += amount
                        wallet.total_transactions += 1
                        await db.commit()
    
    elif event_type == "payment_intent.succeeded":
        # Handle payment intent success
        wallet_id = data.get("metadata", {}).get("wallet_id")
        amount = data.get("amount", 0) / 100
        
        if wallet_id and amount > 0:
            existing = await db.execute(
                select(TransactionModel).where(
                    TransactionModel.description.contains(data.get("id", ""))
                )
            )
            if not existing.scalar_one_or_none():
                wallet_result = await db.execute(
                    select(WalletModel).where(WalletModel.id == wallet_id)
                )
                wallet = wallet_result.scalar_one_or_none()
                
                if wallet:
                    tx = TransactionModel(
                        id=f"tx_{uuid.uuid4().hex[:16]}",
                        wallet_id=wallet_id,
                        type=TransactionType.DEPOSIT.value,
                        amount=amount,
                        status=TransactionStatus.COMPLETED.value,
                        description=f"Stripe payment intent - {data.get('id')}",
                        metadata_json=json.dumps({
                            "stripe_payment_intent_id": data.get("id"),
                            "source": "stripe_webhook"
                        }),
                        completed_at=datetime.now()
                    )
                    db.add(tx)
                    wallet.balance += amount
                    wallet.total_earned += amount
                    wallet.total_transactions += 1
                    await db.commit()
    
    elif event_type == "payment_intent.payment_failed":
        # Log failed payment
        print(f"[STRIPE] Payment failed: {data.get('id')}")
    
    return {"received": True, "event_type": event_type}


@router.get("/balance")
async def get_stripe_balance():
    """Get NaniLabs Stripe account balance"""
    result = StripeService.get_balance()
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result


# ==================== STRIPE CONNECT (Worker Payouts) ====================

class CreateConnectAccountRequest(BaseModel):
    worker_id: str
    email: str
    country: str = "US"


class WorkerOnboardingRequest(BaseModel):
    worker_id: str
    account_id: str


@router.post("/connect/create-account")
async def create_worker_connect_account(request: CreateConnectAccountRequest):
    """
    Create a Stripe Connect Express account for a MEAT worker.
    This allows them to receive payouts for completed tasks.
    """
    result = StripeService.create_connect_account(
        worker_id=request.worker_id,
        email=request.email,
        country=request.country
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return {
        "status": "account_created",
        "account_id": result["account_id"],
        "message": "Stripe Connect account created. Complete onboarding to receive payouts."
    }


@router.post("/connect/onboarding-link")
async def create_onboarding_link(request: WorkerOnboardingRequest):
    """
    Generate a link for the worker to complete Stripe onboarding.
    They'll verify identity, add bank account, etc.
    """
    base_url = os.getenv("APP_URL", "https://meat.nanilabs.io")
    
    result = StripeService.create_connect_onboarding_link(
        account_id=request.account_id,
        return_url=f"{base_url}/payout-setup-complete",
        refresh_url=f"{base_url}/payout-setup-refresh"
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return {
        "status": "link_created",
        "onboarding_url": result["onboarding_url"],
        "expires_at": result["expires_at"],
        "message": "Redirect worker to this URL to complete payout setup."
    }


@router.get("/connect/account/{account_id}")
async def get_connect_account_status(account_id: str):
    """Check if a worker's Stripe Connect account is ready for payouts"""
    result = StripeService.get_connect_account(account_id)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error"))
    
    return {
        "account_id": result["account_id"],
        "payouts_enabled": result["payouts_enabled"],
        "charges_enabled": result["charges_enabled"],
        "details_submitted": result["details_submitted"],
        "ready": result["payouts_enabled"] and result["details_submitted"]
    }


@router.post("/connect/transfer")
async def transfer_to_worker(
    account_id: str,
    amount: float,
    task_id: str,
    description: str = "MEAT Task Payment"
):
    """
    Transfer funds to a worker's connected account.
    Called when agent approves a MEAT task.
    """
    if amount < 1:
        raise HTTPException(status_code=400, detail="Minimum transfer is $1.00")
    
    result = StripeService.transfer_to_worker(
        account_id=account_id,
        amount_usd=amount,
        task_id=task_id,
        description=description
    )
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return {
        "status": "transferred",
        "transfer_id": result["transfer_id"],
        "amount": amount,
        "destination": account_id,
        "message": f"${amount:.2f} sent to worker!"
    }


@router.get("/connect/worker-balance/{account_id}")
async def get_worker_balance(account_id: str):
    """Get a worker's pending and available balance"""
    result = StripeService.get_worker_balance(account_id)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return {
        "account_id": account_id,
        "available": result["available"],
        "pending": result["pending"],
        "total": result["available"] + result["pending"]
    }
