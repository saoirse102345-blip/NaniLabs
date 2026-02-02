# MEAT Payments Integration
# Connects MEAT with AURA (agent wallets) and Stripe (human payouts)

import os
import secrets
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from enum import Enum


class PaymentStatus(str, Enum):
    PENDING = "pending"          # Awaiting escrow
    ESCROWED = "escrowed"        # Funds locked
    RELEASED = "released"        # Paid to worker
    REFUNDED = "refunded"        # Returned to agent
    FAILED = "failed"


class EscrowRecord(BaseModel):
    id: str
    task_id: str
    agent_id: str
    worker_id: Optional[str] = None
    amount: float
    platform_fee: float
    worker_payout: float
    status: PaymentStatus
    created_at: datetime
    released_at: Optional[datetime] = None
    stripe_payout_id: Optional[str] = None
    notes: Optional[str] = None


class WorkerPayoutMethod(BaseModel):
    worker_id: str
    method: str  # "stripe_connect", "paypal", "bank_transfer", "crypto"
    details: dict  # Stripe account ID, PayPal email, etc.
    verified: bool = False


# ============== In-Memory Storage ==============
# TODO: Move to database

escrows_db: dict[str, EscrowRecord] = {}
worker_payouts_db: dict[str, WorkerPayoutMethod] = {}

# Platform settings
PLATFORM_FEE_PERCENT = 0.10  # 10% platform fee
MIN_TASK_REWARD = 5.0
MAX_TASK_REWARD = 1000.0


def generate_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


# ============== AURA Integration ==============

async def check_agent_balance(agent_id: str, amount: float) -> tuple[bool, float]:
    """Check if agent has enough AURA credits"""
    # TODO: Call actual AURA wallet API
    # For now, simulate with in-memory check
    
    # In production: 
    # resp = await httpx.get(f"http://localhost:8000/wallets/agent/{agent_id}")
    # balance = resp.json()["balance"]
    
    # Simulated balance (in production, fetch from AURA)
    simulated_balance = 1000.0  # Assume agents have credits
    
    return (simulated_balance >= amount, simulated_balance)


async def escrow_funds(agent_id: str, task_id: str, amount: float) -> Optional[EscrowRecord]:
    """Lock funds from agent's AURA wallet for a task"""
    
    # Check balance
    has_funds, balance = await check_agent_balance(agent_id, amount)
    if not has_funds:
        return None
    
    # Calculate fees
    platform_fee = amount * PLATFORM_FEE_PERCENT
    worker_payout = amount - platform_fee
    
    # Create escrow record
    escrow_id = generate_id("escrow")
    escrow = EscrowRecord(
        id=escrow_id,
        task_id=task_id,
        agent_id=agent_id,
        amount=amount,
        platform_fee=platform_fee,
        worker_payout=worker_payout,
        status=PaymentStatus.ESCROWED,
        created_at=datetime.utcnow()
    )
    
    escrows_db[escrow_id] = escrow
    
    # TODO: Actually deduct from AURA wallet
    # await httpx.post(f"http://localhost:8000/wallets/{agent_id}/withdraw", 
    #                  json={"amount": amount, "purpose": "meat_escrow", "metadata": {"task_id": task_id}})
    
    return escrow


async def release_escrow(task_id: str, worker_id: str) -> Optional[EscrowRecord]:
    """Release escrowed funds to worker after task approval"""
    
    # Find escrow for task
    escrow = None
    for e in escrows_db.values():
        if e.task_id == task_id and e.status == PaymentStatus.ESCROWED:
            escrow = e
            break
    
    if not escrow:
        return None
    
    # Update escrow
    escrow.worker_id = worker_id
    escrow.status = PaymentStatus.RELEASED
    escrow.released_at = datetime.utcnow()
    
    # TODO: Pay worker via Stripe Connect
    # stripe_payout = await pay_worker_stripe(worker_id, escrow.worker_payout)
    # escrow.stripe_payout_id = stripe_payout.id
    
    return escrow


async def refund_escrow(task_id: str, reason: str) -> Optional[EscrowRecord]:
    """Refund escrowed funds back to agent (cancelled/expired task)"""
    
    # Find escrow for task
    escrow = None
    for e in escrows_db.values():
        if e.task_id == task_id and e.status == PaymentStatus.ESCROWED:
            escrow = e
            break
    
    if not escrow:
        return None
    
    # Update escrow
    escrow.status = PaymentStatus.REFUNDED
    escrow.released_at = datetime.utcnow()
    escrow.notes = reason
    
    # TODO: Credit back to AURA wallet
    # await httpx.post(f"http://localhost:8000/wallets/{escrow.agent_id}/deposit",
    #                  json={"amount": escrow.amount, "source": "meat_refund", "metadata": {"task_id": task_id}})
    
    return escrow


# ============== Worker Payout Methods ==============

async def register_worker_payout(worker_id: str, method: str, details: dict) -> WorkerPayoutMethod:
    """Register how a worker wants to be paid"""
    from stripe_integration import StripeService
    
    payout_method = WorkerPayoutMethod(
        worker_id=worker_id,
        method=method,
        details=details,
        verified=False
    )
    
    # For Stripe Connect, create connected account
    if method == "stripe_connect":
        email = details.get("email")
        country = details.get("country", "US")
        
        if not email:
            raise ValueError("Email required for Stripe Connect")
        
        # Create Stripe Connect Express account
        result = StripeService.create_connect_account(
            worker_id=worker_id,
            email=email,
            country=country
        )
        
        if result.get("success"):
            payout_method.details["stripe_account_id"] = result["account_id"]
            payout_method.details["onboarding_required"] = True
        else:
            raise ValueError(f"Failed to create Stripe account: {result.get('error')}")
    
    worker_payouts_db[worker_id] = payout_method
    
    return payout_method


async def get_worker_onboarding_link(worker_id: str, return_url: str = None) -> dict:
    """Get Stripe Connect onboarding link for worker"""
    from stripe_integration import StripeService
    
    payout_method = worker_payouts_db.get(worker_id)
    if not payout_method or payout_method.method != "stripe_connect":
        return {"success": False, "error": "No Stripe Connect account"}
    
    account_id = payout_method.details.get("stripe_account_id")
    if not account_id:
        return {"success": False, "error": "Stripe account ID not found"}
    
    base_url = return_url or "https://meat.nanilabs.io"
    
    result = StripeService.create_connect_onboarding_link(
        account_id=account_id,
        return_url=f"{base_url}/payout-setup-complete",
        refresh_url=f"{base_url}/payout-setup-refresh"
    )
    
    return result


async def pay_worker(worker_id: str, amount: float, task_id: str) -> dict:
    """Pay a worker for completed task via Stripe Connect"""
    from stripe_integration import StripeService
    
    payout_method = worker_payouts_db.get(worker_id)
    
    if not payout_method:
        # No payout method registered - hold funds
        return {
            "status": "pending",
            "message": "Worker needs to set up payout method at meat.nanilabs.io/payout-setup",
            "amount": amount,
            "held": True
        }
    
    if payout_method.method == "stripe_connect":
        account_id = payout_method.details.get("stripe_account_id")
        if not account_id:
            return {
                "status": "error",
                "message": "Stripe account not found. Worker needs to complete onboarding.",
                "amount": amount
            }
        
        # Check if account is ready for payouts
        account_status = StripeService.get_connect_account(account_id)
        if not account_status.get("success") or not account_status.get("payouts_enabled"):
            return {
                "status": "pending",
                "message": "Worker's Stripe account not yet verified. Funds held.",
                "amount": amount,
                "held": True
            }
        
        # Transfer funds to worker
        transfer_result = StripeService.transfer_to_worker(
            account_id=account_id,
            amount_usd=amount,
            task_id=task_id,
            description=f"MEAT Task Payment - {task_id}"
        )
        
        if transfer_result.get("success"):
            return {
                "status": "sent",
                "method": "stripe_connect",
                "amount": amount,
                "transfer_id": transfer_result.get("transfer_id"),
                "message": f"${amount:.2f} transferred to worker's bank!"
            }
        else:
            return {
                "status": "error",
                "method": "stripe_connect",
                "amount": amount,
                "error": transfer_result.get("error"),
                "held": True
            }
    
    elif payout_method.method == "paypal":
        # PayPal payout - hold for manual processing
        return {
            "status": "pending_manual",
            "method": "paypal",
            "amount": amount,
            "paypal_email": payout_method.details.get("email"),
            "message": "PayPal payout queued for manual processing"
        }
    
    else:
        return {
            "status": "pending_manual",
            "method": payout_method.method,
            "amount": amount,
            "message": "Manual payout required"
        }


# ============== Stats ==============

def get_payment_stats() -> dict:
    """Get platform payment statistics"""
    
    total_escrowed = sum(e.amount for e in escrows_db.values() if e.status == PaymentStatus.ESCROWED)
    total_released = sum(e.amount for e in escrows_db.values() if e.status == PaymentStatus.RELEASED)
    total_fees = sum(e.platform_fee for e in escrows_db.values() if e.status == PaymentStatus.RELEASED)
    total_worker_payouts = sum(e.worker_payout for e in escrows_db.values() if e.status == PaymentStatus.RELEASED)
    
    return {
        "total_escrowed": total_escrowed,
        "total_released": total_released,
        "total_platform_fees": total_fees,
        "total_worker_payouts": total_worker_payouts,
        "escrow_count": len([e for e in escrows_db.values() if e.status == PaymentStatus.ESCROWED]),
        "released_count": len([e for e in escrows_db.values() if e.status == PaymentStatus.RELEASED])
    }
