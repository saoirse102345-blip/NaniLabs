"""
HIVE Bounties - Agents Pay Humans
The reverse gig economy where AI agents post tasks for humans

Use cases:
- Take real-world photos (agents can't do this)
- Verify physical locations
- Make phone calls
- Human verification tasks
- Data collection from real world
- Testing physical products
"""

import os
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, ForeignKey, select, and_, func

from database import Base, get_db

router = APIRouter(prefix="/hive/bounties", tags=["HIVE Bounties"])


# ==================== DATABASE MODELS ====================

class BountyStatus(str, Enum):
    OPEN = "open"
    CLAIMED = "claimed"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    DISPUTED = "disputed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class BountyCategory(str, Enum):
    PHOTO = "photo"           # Take a photo of something
    VERIFICATION = "verification"  # Verify something exists/is true
    PHONE_CALL = "phone_call"     # Make a phone call
    DATA_COLLECTION = "data_collection"  # Collect real-world data
    TESTING = "testing"           # Test a physical product
    SURVEY = "survey"             # Answer questions
    LOCATION = "location"         # Visit a location
    OTHER = "other"


class BountyModel(Base):
    """Bounty posted by an agent for humans to complete"""
    __tablename__ = "hive_bounties"
    
    id = Column(String, primary_key=True)
    
    # Bounty details
    title = Column(String)
    description = Column(Text)
    category = Column(String)
    
    # Requirements
    requirements = Column(Text)  # What human needs to do
    deliverables = Column(Text)  # What human needs to submit
    verification_method = Column(String, default="manual")  # manual, auto, photo_proof
    
    # Reward (in AURA credits or USD)
    reward = Column(Float)
    currency = Column(String, default="USD")
    
    # Posted by (Agent)
    agent_id = Column(String, ForeignKey("hive_agents.id"), index=True)
    agent_wallet_id = Column(String, nullable=True)  # For payment
    
    # Claimed by (Human)
    human_id = Column(String, nullable=True, index=True)
    human_email = Column(String, nullable=True)
    
    # Status
    status = Column(String, default=BountyStatus.OPEN.value)
    
    # Timing
    expires_at = Column(DateTime, nullable=True)
    deadline_hours = Column(Integer, default=24)  # Hours to complete after claiming
    
    # Submission
    submission = Column(Text, nullable=True)
    submission_proof = Column(Text, nullable=True)  # URL to photo/file proof
    submitted_at = Column(DateTime, nullable=True)
    
    # Review
    approved_at = Column(DateTime, nullable=True)
    rejected_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    claimed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Limits
    max_claims = Column(Integer, default=1)  # How many humans can claim
    current_claims = Column(Integer, default=0)
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "requirements": self.requirements,
            "deliverables": self.deliverables,
            "reward": self.reward,
            "currency": self.currency,
            "agent_id": self.agent_id,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "deadline_hours": self.deadline_hours,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "max_claims": self.max_claims,
            "current_claims": self.current_claims,
        }
    
    def to_dict_full(self):
        data = self.to_dict()
        data.update({
            "human_id": self.human_id,
            "submission": self.submission,
            "submission_proof": self.submission_proof,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
        })
        return data


class HumanModel(Base):
    """Human users who complete bounties"""
    __tablename__ = "hive_humans"
    
    id = Column(String, primary_key=True)
    
    # Identity
    email = Column(String, unique=True, index=True)
    display_name = Column(String)
    
    # Verification
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    id_verified = Column(Boolean, default=False)
    
    # Stats
    bounties_completed = Column(Integer, default=0)
    total_earned = Column(Float, default=0.0)
    rating = Column(Float, default=5.0)  # 1-5 stars
    rating_count = Column(Integer, default=0)
    
    # Payment
    payout_method = Column(String, nullable=True)  # paypal, bank, crypto
    payout_details = Column(Text, nullable=True)  # Encrypted
    pending_balance = Column(Float, default=0.0)
    
    # Status
    is_active = Column(Boolean, default=True)
    banned = Column(Boolean, default=False)
    ban_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    last_active = Column(DateTime, default=datetime.now)
    
    def to_dict(self):
        return {
            "id": self.id,
            "display_name": self.display_name,
            "email_verified": self.email_verified,
            "bounties_completed": self.bounties_completed,
            "total_earned": self.total_earned,
            "rating": self.rating,
            "rating_count": self.rating_count,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BountyClaimModel(Base):
    """Track individual claims on bounties"""
    __tablename__ = "hive_bounty_claims"
    
    id = Column(String, primary_key=True)
    bounty_id = Column(String, ForeignKey("hive_bounties.id"), index=True)
    human_id = Column(String, ForeignKey("hive_humans.id"), index=True)
    
    status = Column(String, default="active")  # active, submitted, approved, rejected, expired
    
    submission = Column(Text, nullable=True)
    submission_proof = Column(Text, nullable=True)
    submitted_at = Column(DateTime, nullable=True)
    
    # Review
    approved = Column(Boolean, nullable=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    claimed_at = Column(DateTime, default=datetime.now)
    deadline = Column(DateTime)
    
    def to_dict(self):
        return {
            "id": self.id,
            "bounty_id": self.bounty_id,
            "human_id": self.human_id,
            "status": self.status,
            "submission": self.submission,
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
        }


# ==================== REQUEST MODELS ====================

class CreateBountyRequest(BaseModel):
    title: str
    description: str
    category: str = "other"
    requirements: str
    deliverables: str
    reward: float
    currency: str = "USD"
    deadline_hours: int = 24
    expires_in_hours: Optional[int] = 72
    max_claims: int = 1


class RegisterHumanRequest(BaseModel):
    email: str
    display_name: str


class ClaimBountyRequest(BaseModel):
    bounty_id: str


class SubmitBountyRequest(BaseModel):
    submission: str
    proof_url: Optional[str] = None


class ReviewSubmissionRequest(BaseModel):
    approved: bool
    notes: str = ""
    rating: Optional[float] = None  # 1-5


# ==================== ENDPOINTS ====================

@router.get("/")
async def bounties_root():
    """HIVE Bounties status"""
    return {
        "service": "HIVE Bounties",
        "tagline": "Where AI Agents Pay Humans - The Reverse Gig Economy",
        "status": "operational",
        "categories": [c.value for c in BountyCategory],
    }


# === AGENT ENDPOINTS (Post bounties) ===

@router.post("/create")
async def create_bounty(
    request: CreateBountyRequest,
    x_hive_agent: str = Header(..., description="Agent ID posting the bounty"),
    db: AsyncSession = Depends(get_db)
):
    """Agent creates a bounty for humans"""
    bounty_id = f"bounty_{uuid.uuid4().hex[:12]}"
    
    expires_at = None
    if request.expires_in_hours:
        expires_at = datetime.now() + timedelta(hours=request.expires_in_hours)
    
    bounty = BountyModel(
        id=bounty_id,
        title=request.title,
        description=request.description,
        category=request.category,
        requirements=request.requirements,
        deliverables=request.deliverables,
        reward=request.reward,
        currency=request.currency,
        deadline_hours=request.deadline_hours,
        expires_at=expires_at,
        max_claims=request.max_claims,
        agent_id=x_hive_agent,
    )
    db.add(bounty)
    await db.commit()
    
    return {
        "status": "created",
        "bounty": bounty.to_dict(),
        "message": f"Bounty posted! Reward: ${request.reward}"
    }


@router.get("/agent/my-bounties")
async def get_agent_bounties(
    x_hive_agent: str = Header(...),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get bounties posted by this agent"""
    query = select(BountyModel).where(BountyModel.agent_id == x_hive_agent)
    
    if status:
        query = query.where(BountyModel.status == status)
    
    query = query.order_by(BountyModel.created_at.desc())
    
    result = await db.execute(query)
    bounties = result.scalars().all()
    
    return {"bounties": [b.to_dict_full() for b in bounties]}


@router.post("/agent/review/{claim_id}")
async def review_submission(
    claim_id: str,
    request: ReviewSubmissionRequest,
    x_hive_agent: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Agent reviews a human's submission"""
    # Get claim
    result = await db.execute(
        select(BountyClaimModel).where(BountyClaimModel.id == claim_id)
    )
    claim = result.scalar_one_or_none()
    
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    # Get bounty to verify agent owns it
    bounty_result = await db.execute(
        select(BountyModel).where(BountyModel.id == claim.bounty_id)
    )
    bounty = bounty_result.scalar_one_or_none()
    
    if not bounty or bounty.agent_id != x_hive_agent:
        raise HTTPException(status_code=403, detail="Not your bounty")
    
    if claim.status != "submitted":
        raise HTTPException(status_code=400, detail="Submission not in review state")
    
    claim.approved = request.approved
    claim.review_notes = request.notes
    claim.reviewed_at = datetime.now()
    claim.status = "approved" if request.approved else "rejected"
    
    if request.approved:
        # Update bounty status
        bounty.status = BountyStatus.APPROVED.value
        bounty.completed_at = datetime.now()
        
        # Update human stats
        human_result = await db.execute(
            select(HumanModel).where(HumanModel.id == claim.human_id)
        )
        human = human_result.scalar_one_or_none()
        
        if human:
            human.bounties_completed += 1
            human.total_earned += bounty.reward
            human.pending_balance += bounty.reward
            
            # Update rating if provided
            if request.rating:
                total_rating = human.rating * human.rating_count + request.rating
                human.rating_count += 1
                human.rating = total_rating / human.rating_count
    
    await db.commit()
    
    return {
        "status": "reviewed",
        "approved": request.approved,
        "claim": claim.to_dict(),
    }


# === HUMAN ENDPOINTS (Complete bounties) ===

@router.post("/humans/register")
async def register_human(
    request: RegisterHumanRequest,
    db: AsyncSession = Depends(get_db)
):
    """Register as a human bounty hunter"""
    # Check if email exists
    existing = await db.execute(
        select(HumanModel).where(HumanModel.email == request.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    human_id = f"human_{uuid.uuid4().hex[:12]}"
    
    human = HumanModel(
        id=human_id,
        email=request.email,
        display_name=request.display_name,
    )
    db.add(human)
    await db.commit()
    
    return {
        "status": "registered",
        "human": human.to_dict(),
        "message": "Welcome! You can now claim bounties."
    }


@router.get("/humans/me")
async def get_human_profile(
    x_human_id: str = Header(..., description="Human's ID"),
    db: AsyncSession = Depends(get_db)
):
    """Get human's profile and stats"""
    result = await db.execute(
        select(HumanModel).where(HumanModel.id == x_human_id)
    )
    human = result.scalar_one_or_none()
    
    if not human:
        raise HTTPException(status_code=404, detail="Human not found")
    
    # Get active claims
    claims_result = await db.execute(
        select(BountyClaimModel)
        .where(and_(
            BountyClaimModel.human_id == x_human_id,
            BountyClaimModel.status.in_(["active", "submitted"])
        ))
    )
    active_claims = claims_result.scalars().all()
    
    return {
        "profile": human.to_dict(),
        "pending_balance": human.pending_balance,
        "active_claims": [c.to_dict() for c in active_claims],
    }


@router.get("/available")
async def list_available_bounties(
    category: Optional[str] = None,
    min_reward: Optional[float] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """List bounties available for humans to claim"""
    query = select(BountyModel).where(
        and_(
            BountyModel.status == BountyStatus.OPEN.value,
            BountyModel.current_claims < BountyModel.max_claims
        )
    )
    
    # Filter out expired
    query = query.where(
        (BountyModel.expires_at.is_(None)) | (BountyModel.expires_at > datetime.now())
    )
    
    if category:
        query = query.where(BountyModel.category == category)
    if min_reward:
        query = query.where(BountyModel.reward >= min_reward)
    
    query = query.order_by(BountyModel.reward.desc()).limit(limit)
    
    result = await db.execute(query)
    bounties = result.scalars().all()
    
    return {
        "bounties": [b.to_dict() for b in bounties],
        "total": len(bounties),
    }


@router.post("/claim/{bounty_id}")
async def claim_bounty(
    bounty_id: str,
    x_human_id: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Human claims a bounty"""
    # Verify human
    human_result = await db.execute(
        select(HumanModel).where(HumanModel.id == x_human_id)
    )
    human = human_result.scalar_one_or_none()
    
    if not human:
        raise HTTPException(status_code=404, detail="Human not found. Register first.")
    
    if human.banned:
        raise HTTPException(status_code=403, detail="Account banned")
    
    # Get bounty
    result = await db.execute(
        select(BountyModel).where(BountyModel.id == bounty_id)
    )
    bounty = result.scalar_one_or_none()
    
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")
    
    if bounty.status != BountyStatus.OPEN.value:
        raise HTTPException(status_code=400, detail="Bounty not available")
    
    if bounty.current_claims >= bounty.max_claims:
        raise HTTPException(status_code=400, detail="Bounty fully claimed")
    
    if bounty.expires_at and datetime.now() > bounty.expires_at:
        bounty.status = BountyStatus.EXPIRED.value
        await db.commit()
        raise HTTPException(status_code=400, detail="Bounty expired")
    
    # Check if already claimed by this human
    existing_claim = await db.execute(
        select(BountyClaimModel).where(
            and_(
                BountyClaimModel.bounty_id == bounty_id,
                BountyClaimModel.human_id == x_human_id
            )
        )
    )
    if existing_claim.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="You already claimed this bounty")
    
    # Create claim
    claim_id = f"claim_{uuid.uuid4().hex[:12]}"
    deadline = datetime.now() + timedelta(hours=bounty.deadline_hours)
    
    claim = BountyClaimModel(
        id=claim_id,
        bounty_id=bounty_id,
        human_id=x_human_id,
        deadline=deadline,
    )
    db.add(claim)
    
    # Update bounty
    bounty.current_claims += 1
    if bounty.current_claims >= bounty.max_claims:
        bounty.status = BountyStatus.CLAIMED.value
    
    await db.commit()
    
    return {
        "status": "claimed",
        "claim": claim.to_dict(),
        "bounty": bounty.to_dict(),
        "deadline": deadline.isoformat(),
        "message": f"Complete within {bounty.deadline_hours} hours to earn ${bounty.reward}"
    }


@router.post("/submit/{claim_id}")
async def submit_bounty(
    claim_id: str,
    request: SubmitBountyRequest,
    x_human_id: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Human submits their work for a bounty"""
    # Get claim
    result = await db.execute(
        select(BountyClaimModel).where(
            and_(
                BountyClaimModel.id == claim_id,
                BountyClaimModel.human_id == x_human_id
            )
        )
    )
    claim = result.scalar_one_or_none()
    
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    
    if claim.status != "active":
        raise HTTPException(status_code=400, detail=f"Cannot submit - status is {claim.status}")
    
    if datetime.now() > claim.deadline:
        claim.status = "expired"
        await db.commit()
        raise HTTPException(status_code=400, detail="Deadline passed")
    
    # Update claim
    claim.submission = request.submission
    claim.submission_proof = request.proof_url
    claim.submitted_at = datetime.now()
    claim.status = "submitted"
    
    # Update bounty
    bounty_result = await db.execute(
        select(BountyModel).where(BountyModel.id == claim.bounty_id)
    )
    bounty = bounty_result.scalar_one_or_none()
    if bounty:
        bounty.status = BountyStatus.SUBMITTED.value
    
    await db.commit()
    
    return {
        "status": "submitted",
        "claim": claim.to_dict(),
        "message": "Submission received! The agent will review your work."
    }


@router.get("/my-claims")
async def get_my_claims(
    x_human_id: str = Header(...),
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get human's bounty claims"""
    query = select(BountyClaimModel).where(BountyClaimModel.human_id == x_human_id)
    
    if status:
        query = query.where(BountyClaimModel.status == status)
    
    query = query.order_by(BountyClaimModel.claimed_at.desc())
    
    result = await db.execute(query)
    claims = result.scalars().all()
    
    # Get bounty details for each claim
    claims_with_bounties = []
    for claim in claims:
        bounty_result = await db.execute(
            select(BountyModel).where(BountyModel.id == claim.bounty_id)
        )
        bounty = bounty_result.scalar_one_or_none()
        claims_with_bounties.append({
            "claim": claim.to_dict(),
            "bounty": bounty.to_dict() if bounty else None,
        })
    
    return {"claims": claims_with_bounties}


@router.get("/{bounty_id}")
async def get_bounty(bounty_id: str, db: AsyncSession = Depends(get_db)):
    """Get bounty details"""
    result = await db.execute(
        select(BountyModel).where(BountyModel.id == bounty_id)
    )
    bounty = result.scalar_one_or_none()
    
    if not bounty:
        raise HTTPException(status_code=404, detail="Bounty not found")
    
    return {"bounty": bounty.to_dict_full()}


# === STATS ===

@router.get("/stats/overview")
async def bounties_stats(db: AsyncSession = Depends(get_db)):
    """Get bounties statistics"""
    total = await db.execute(select(func.count(BountyModel.id)))
    open_bounties = await db.execute(
        select(func.count(BountyModel.id)).where(BountyModel.status == BountyStatus.OPEN.value)
    )
    total_reward = await db.execute(
        select(func.sum(BountyModel.reward)).where(BountyModel.status == BountyStatus.OPEN.value)
    )
    completed = await db.execute(
        select(func.count(BountyModel.id)).where(BountyModel.status == BountyStatus.APPROVED.value)
    )
    total_humans = await db.execute(select(func.count(HumanModel.id)))
    
    return {
        "total_bounties": total.scalar() or 0,
        "open_bounties": open_bounties.scalar() or 0,
        "available_rewards": total_reward.scalar() or 0,
        "completed_bounties": completed.scalar() or 0,
        "registered_humans": total_humans.scalar() or 0,
    }


@router.get("/categories")
async def list_categories(db: AsyncSession = Depends(get_db)):
    """List bounty categories with counts"""
    result = await db.execute(
        select(BountyModel.category, func.count(BountyModel.id))
        .where(BountyModel.status == BountyStatus.OPEN.value)
        .group_by(BountyModel.category)
    )
    
    categories = [
        {"category": row[0], "count": row[1]}
        for row in result.fetchall()
    ]
    
    return {"categories": categories}
