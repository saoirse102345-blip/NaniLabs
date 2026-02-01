"""
AURA Infra - Database Models
SQLite database for wallet persistence
"""

from datetime import datetime
from typing import Optional, List
from decimal import Decimal
import os

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import enum

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aura_infra.db")
ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class TransactionType(str, enum.Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    FEE = "fee"
    REVENUE = "revenue"
    EXPENSE = "expense"


class TransactionStatus(str, enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


class WalletModel(Base):
    """Database model for agent wallets"""
    __tablename__ = "wallets"
    
    id = Column(String, primary_key=True)
    agent_id = Column(String, unique=True, index=True)
    agent_name = Column(String)
    balance = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    
    # Stats
    total_earned = Column(Float, default=0.0)
    total_spent = Column(Float, default=0.0)
    total_transactions = Column(Integer, default=0)
    
    # Limits
    daily_spend_limit = Column(Float, default=100.0)
    daily_spent = Column(Float, default=0.0)
    last_spend_reset = Column(DateTime, default=datetime.now)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    transactions = relationship("TransactionModel", back_populates="wallet", foreign_keys="TransactionModel.wallet_id")
    
    def to_dict(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "balance": self.balance,
            "currency": self.currency,
            "total_earned": self.total_earned,
            "total_spent": self.total_spent,
            "total_transactions": self.total_transactions,
            "daily_spend_limit": self.daily_spend_limit,
            "daily_spent": self.daily_spent,
            "profit": self.total_earned - self.total_spent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class TransactionModel(Base):
    """Database model for transactions"""
    __tablename__ = "transactions"
    
    id = Column(String, primary_key=True)
    wallet_id = Column(String, ForeignKey("wallets.id"), index=True)
    type = Column(String)  # TransactionType
    amount = Column(Float)
    currency = Column(String, default="USD")
    status = Column(String)  # TransactionStatus
    description = Column(String)
    metadata_json = Column(String, default="{}")  # JSON string
    
    # For transfers
    from_wallet_id = Column(String, ForeignKey("wallets.id"), nullable=True)
    to_wallet_id = Column(String, ForeignKey("wallets.id"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    wallet = relationship("WalletModel", back_populates="transactions", foreign_keys=[wallet_id])
    
    def to_dict(self):
        return {
            "id": self.id,
            "wallet_id": self.wallet_id,
            "type": self.type,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "description": self.description,
            "from_wallet_id": self.from_wallet_id,
            "to_wallet_id": self.to_wallet_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class AgentModel(Base):
    """Database model for registered agents"""
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True)
    name = Column(String)
    type = Column(String)  # content_creator, trader, researcher, etc.
    description = Column(String)
    api_key_hash = Column(String)  # Hashed API key for authentication
    
    # Stats
    reputation_score = Column(Float, default=0.0)
    total_tasks_completed = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    
    # Status
    is_active = Column(Integer, default=1)  # Boolean as int for SQLite
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "reputation_score": self.reputation_score,
            "total_tasks_completed": self.total_tasks_completed,
            "total_revenue": self.total_revenue,
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None,
        }


async def init_db():
    """Initialize the database"""
    # Import HIVE models to register them with Base
    from hive_models import (
        HiveAgentModel, EncryptedMessageModel, VerificationChallengeModel,
        ChallengeModel, ChallengeSubmissionModel, TaskModel, KnowledgeEntryModel
    )
    # Import Arena models (Agent Battles)
    from hive_battles import BattleModel, BattleLogModel, SpectatorVoteModel
    # Import Bounty models (Agents Pay Humans)
    from hive_bounties import BountyModel, HumanModel, BountyClaimModel
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[DB] Database initialized (AURA + HIVE + Arena + Bounties)")


async def get_db():
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
