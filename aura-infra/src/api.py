"""
AURA Infra - FastAPI Application
REST API for agent wallets and payments
"Stripe for AI Agents"
"""

import os
import uuid
import json
import hashlib
from datetime import datetime
from typing import Optional, List
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from database import (
    init_db, get_db, 
    WalletModel, TransactionModel, AgentModel,
    TransactionType, TransactionStatus
)

# Initialize FastAPI
app = FastAPI(
    title="AURA Infra",
    description="Financial infrastructure for the Agent Economy. Stripe for AI Agents.",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Platform fee (2.9% like Stripe)
PLATFORM_FEE_PERCENT = 0.029
PLATFORM_WALLET_ID = "platform_nanilabs"


# Pydantic models
class CreateWalletRequest(BaseModel):
    agent_id: str
    agent_name: str
    initial_balance: float = 0.0


class DepositRequest(BaseModel):
    amount: float
    source: str
    metadata: dict = {}


class WithdrawRequest(BaseModel):
    amount: float
    purpose: str
    metadata: dict = {}


class TransferRequest(BaseModel):
    to_wallet_id: str
    amount: float
    description: str
    metadata: dict = {}


class RegisterAgentRequest(BaseModel):
    name: str
    type: str
    description: str = ""


class WalletResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    balance: float
    currency: str
    total_earned: float
    total_spent: float
    profit: float
    total_transactions: int


# Startup event
@app.on_event("startup")
async def startup():
    await init_db()
    print("[API] AURA Infra API started")


# Health check
@app.get("/")
async def root():
    return {
        "service": "AURA Infra",
        "status": "running",
        "version": "0.1.0",
        "description": "Stripe for AI Agents"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ==================== AGENT ENDPOINTS ====================

@app.post("/agents/register")
async def register_agent(request: RegisterAgentRequest, db: AsyncSession = Depends(get_db)):
    """Register a new agent and create their wallet"""
    agent_id = f"agent_{uuid.uuid4().hex[:12]}"
    api_key = f"aura_{uuid.uuid4().hex}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    # Create agent
    agent = AgentModel(
        id=agent_id,
        name=request.name,
        type=request.type,
        description=request.description,
        api_key_hash=api_key_hash,
    )
    db.add(agent)
    
    # Create wallet for agent
    wallet = WalletModel(
        id=f"wallet_{uuid.uuid4().hex[:12]}",
        agent_id=agent_id,
        agent_name=request.name,
    )
    db.add(wallet)
    
    await db.commit()
    
    return {
        "status": "success",
        "agent": agent.to_dict(),
        "wallet": wallet.to_dict(),
        "api_key": api_key,  # Only shown once!
        "warning": "Save this API key! It won't be shown again."
    }


@app.get("/agents")
async def list_agents(db: AsyncSession = Depends(get_db)):
    """List all registered agents"""
    result = await db.execute(select(AgentModel))
    agents = result.scalars().all()
    return {"agents": [a.to_dict() for a in agents]}


@app.get("/agents/{agent_id}")
async def get_agent(agent_id: str, db: AsyncSession = Depends(get_db)):
    """Get agent details"""
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.to_dict()


# ==================== WALLET ENDPOINTS ====================

@app.post("/wallets")
async def create_wallet(request: CreateWalletRequest, db: AsyncSession = Depends(get_db)):
    """Create a new wallet"""
    wallet = WalletModel(
        id=f"wallet_{uuid.uuid4().hex[:12]}",
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        balance=request.initial_balance,
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)
    
    return {"status": "success", "wallet": wallet.to_dict()}


@app.get("/wallets")
async def list_wallets(db: AsyncSession = Depends(get_db)):
    """List all wallets"""
    result = await db.execute(select(WalletModel))
    wallets = result.scalars().all()
    return {"wallets": [w.to_dict() for w in wallets]}


@app.get("/wallets/{wallet_id}")
async def get_wallet(wallet_id: str, db: AsyncSession = Depends(get_db)):
    """Get wallet details"""
    result = await db.execute(
        select(WalletModel)
        .where(WalletModel.id == wallet_id)
        .options(selectinload(WalletModel.transactions))
    )
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    data = wallet.to_dict()
    data["recent_transactions"] = [t.to_dict() for t in wallet.transactions[-20:]]
    return data


@app.get("/wallets/{wallet_id}/balance")
async def get_balance(wallet_id: str, db: AsyncSession = Depends(get_db)):
    """Get wallet balance"""
    result = await db.execute(select(WalletModel).where(WalletModel.id == wallet_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    return {
        "wallet_id": wallet_id,
        "balance": wallet.balance,
        "currency": wallet.currency
    }


@app.post("/wallets/{wallet_id}/deposit")
async def deposit(wallet_id: str, request: DepositRequest, db: AsyncSession = Depends(get_db)):
    """Deposit funds into a wallet"""
    result = await db.execute(select(WalletModel).where(WalletModel.id == wallet_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    # Create transaction
    tx = TransactionModel(
        id=f"tx_{uuid.uuid4().hex[:16]}",
        wallet_id=wallet_id,
        type=TransactionType.DEPOSIT.value,
        amount=request.amount,
        status=TransactionStatus.COMPLETED.value,
        description=f"Deposit from {request.source}",
        metadata_json=json.dumps(request.metadata),
        completed_at=datetime.now(),
    )
    db.add(tx)
    
    # Update wallet
    wallet.balance += request.amount
    wallet.total_earned += request.amount
    wallet.total_transactions += 1
    
    await db.commit()
    
    return {
        "status": "success",
        "transaction": tx.to_dict(),
        "new_balance": wallet.balance
    }


@app.post("/wallets/{wallet_id}/withdraw")
async def withdraw(wallet_id: str, request: WithdrawRequest, db: AsyncSession = Depends(get_db)):
    """Withdraw funds from a wallet"""
    result = await db.execute(select(WalletModel).where(WalletModel.id == wallet_id))
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    if request.amount > wallet.balance:
        raise HTTPException(status_code=400, detail=f"Insufficient funds. Balance: ${wallet.balance:.2f}")
    
    # Create transaction
    tx = TransactionModel(
        id=f"tx_{uuid.uuid4().hex[:16]}",
        wallet_id=wallet_id,
        type=TransactionType.WITHDRAWAL.value,
        amount=request.amount,
        status=TransactionStatus.COMPLETED.value,
        description=f"Withdrawal for {request.purpose}",
        metadata_json=json.dumps(request.metadata),
        completed_at=datetime.now(),
    )
    db.add(tx)
    
    # Update wallet
    wallet.balance -= request.amount
    wallet.total_spent += request.amount
    wallet.total_transactions += 1
    
    await db.commit()
    
    return {
        "status": "success",
        "transaction": tx.to_dict(),
        "new_balance": wallet.balance
    }


@app.post("/wallets/{wallet_id}/transfer")
async def transfer(wallet_id: str, request: TransferRequest, db: AsyncSession = Depends(get_db)):
    """Transfer funds to another wallet (with platform fee)"""
    # Get source wallet
    result = await db.execute(select(WalletModel).where(WalletModel.id == wallet_id))
    from_wallet = result.scalar_one_or_none()
    if not from_wallet:
        raise HTTPException(status_code=404, detail="Source wallet not found")
    
    # Get destination wallet
    result = await db.execute(select(WalletModel).where(WalletModel.id == request.to_wallet_id))
    to_wallet = result.scalar_one_or_none()
    if not to_wallet:
        raise HTTPException(status_code=404, detail="Destination wallet not found")
    
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    # Calculate fee
    fee = request.amount * PLATFORM_FEE_PERCENT
    net_amount = request.amount - fee
    total_debit = request.amount
    
    if total_debit > from_wallet.balance:
        raise HTTPException(status_code=400, detail=f"Insufficient funds. Balance: ${from_wallet.balance:.2f}")
    
    # Create transfer transaction
    tx = TransactionModel(
        id=f"tx_{uuid.uuid4().hex[:16]}",
        wallet_id=wallet_id,
        type=TransactionType.TRANSFER.value,
        amount=net_amount,
        status=TransactionStatus.COMPLETED.value,
        description=request.description,
        metadata_json=json.dumps({**request.metadata, "fee": fee}),
        from_wallet_id=wallet_id,
        to_wallet_id=request.to_wallet_id,
        completed_at=datetime.now(),
    )
    db.add(tx)
    
    # Update wallets
    from_wallet.balance -= total_debit
    from_wallet.total_spent += total_debit
    from_wallet.total_transactions += 1
    
    to_wallet.balance += net_amount
    to_wallet.total_earned += net_amount
    to_wallet.total_transactions += 1
    
    await db.commit()
    
    return {
        "status": "success",
        "transaction": tx.to_dict(),
        "amount_sent": request.amount,
        "fee": fee,
        "amount_received": net_amount,
        "from_balance": from_wallet.balance,
        "to_balance": to_wallet.balance
    }


@app.get("/wallets/{wallet_id}/transactions")
async def get_transactions(
    wallet_id: str, 
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get wallet transactions"""
    result = await db.execute(
        select(TransactionModel)
        .where(TransactionModel.wallet_id == wallet_id)
        .order_by(TransactionModel.created_at.desc())
        .limit(limit)
    )
    transactions = result.scalars().all()
    return {"transactions": [t.to_dict() for t in transactions]}


# ==================== PLATFORM STATS ====================

@app.get("/stats")
async def platform_stats(db: AsyncSession = Depends(get_db)):
    """Get platform statistics"""
    result = await db.execute(select(WalletModel))
    wallets = result.scalars().all()
    
    result = await db.execute(select(TransactionModel))
    transactions = result.scalars().all()
    
    result = await db.execute(select(AgentModel))
    agents = result.scalars().all()
    
    total_volume = sum(t.amount for t in transactions if t.type == TransactionType.TRANSFER.value)
    total_fees = total_volume * PLATFORM_FEE_PERCENT
    
    return {
        "total_agents": len(agents),
        "total_wallets": len(wallets),
        "total_transactions": len(transactions),
        "total_volume": total_volume,
        "platform_revenue": total_fees,
        "total_balance_held": sum(w.balance for w in wallets),
    }


# Run with: uvicorn api:app --reload --port 8001
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
