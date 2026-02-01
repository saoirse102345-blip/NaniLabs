# MEAT - Agent-to-Human Labor Marketplace
# "When agents need meatspace"
# Part of NaniLabs

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class TaskCategory(str, Enum):
    PHYSICAL = "physical"      # Delivery, pickup, mailing
    VOICE = "voice"            # Phone calls, appointments
    LOCAL = "local"            # Go somewhere, photos, verify
    HANDWORK = "handwork"      # Handwritten, signing, creation
    RESEARCH = "research"      # IRL investigation
    SOCIAL = "social"          # Human presence required
    OTHER = "other"


class TaskStatus(str, Enum):
    OPEN = "open"              # Available for claiming
    CLAIMED = "claimed"        # Human working on it
    SUBMITTED = "submitted"    # Work submitted, pending review
    APPROVED = "approved"      # Agent approved, payment sent
    DISPUTED = "disputed"      # Under dispute
    CANCELLED = "cancelled"    # Cancelled by agent
    EXPIRED = "expired"        # Deadline passed


class TaskUrgency(str, Enum):
    LOW = "low"                # Whenever
    NORMAL = "normal"          # Within deadline
    URGENT = "urgent"          # ASAP
    CRITICAL = "critical"      # Emergency premium


# ============== Human Worker Models ==============

class MeatWorkerCreate(BaseModel):
    """Human signing up to work for agents"""
    email: str
    display_name: str
    bio: Optional[str] = None
    location: Optional[str] = None  # City/region for local tasks
    skills: List[str] = []          # ["delivery", "phone", "photography"]
    categories: List[TaskCategory] = []  # Preferred task types
    hourly_rate: Optional[float] = None  # Suggested rate
    languages: List[str] = ["en"]
    timezone: Optional[str] = None
    phone: Optional[str] = None     # For voice tasks
    verified_identity: bool = False  # KYC'd


class MeatWorker(BaseModel):
    """Human worker profile"""
    id: str                         # meat_worker_xxx
    email: str
    display_name: str
    bio: Optional[str] = None
    location: Optional[str] = None
    skills: List[str] = []
    categories: List[TaskCategory] = []
    hourly_rate: Optional[float] = None
    languages: List[str] = ["en"]
    timezone: Optional[str] = None
    
    # Stats
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_earned: float = 0.0
    avg_rating: float = 0.0
    rating_count: int = 0
    
    # Status
    verified_identity: bool = False
    verified_phone: bool = False
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Reputation tier
    tier: str = "new"  # new, bronze, silver, gold, platinum


# ============== Task Models ==============

class MeatTaskCreate(BaseModel):
    """Agent posting a task for humans"""
    title: str
    description: str
    category: TaskCategory
    urgency: TaskUrgency = TaskUrgency.NORMAL
    
    # Requirements
    requirements: Optional[str] = None
    deliverables: str              # What the human must submit
    location_required: Optional[str] = None  # City/region if local
    skills_required: List[str] = []
    languages_required: List[str] = ["en"]
    
    # Compensation
    reward: float                  # AURA credits
    bonus_fast: Optional[float] = None  # Bonus for early completion
    
    # Timing
    deadline_hours: int = 24
    estimated_minutes: Optional[int] = None  # How long it should take
    
    # Verification
    proof_required: str = "photo"  # photo, video, receipt, screenshot, text
    verification_notes: Optional[str] = None


class MeatTask(BaseModel):
    """A task posted by an agent for humans"""
    id: str                        # meat_task_xxx
    agent_id: str                  # AURA agent ID
    agent_name: Optional[str] = None
    
    title: str
    description: str
    category: TaskCategory
    urgency: TaskUrgency
    status: TaskStatus = TaskStatus.OPEN
    
    # Requirements
    requirements: Optional[str] = None
    deliverables: str
    location_required: Optional[str] = None
    skills_required: List[str] = []
    languages_required: List[str] = ["en"]
    
    # Compensation
    reward: float
    bonus_fast: Optional[float] = None
    escrow_tx_id: Optional[str] = None  # AURA escrow transaction
    
    # Timing
    deadline: datetime
    estimated_minutes: Optional[int] = None
    
    # Verification
    proof_required: str
    verification_notes: Optional[str] = None
    
    # Assignment
    claimed_by: Optional[str] = None  # Worker ID
    claimed_at: Optional[datetime] = None
    
    # Completion
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    views: int = 0
    claims_count: int = 0  # How many tried to claim


# ============== Claim & Submission Models ==============

class MeatClaim(BaseModel):
    """Human claiming a task"""
    id: str                        # meat_claim_xxx
    task_id: str
    worker_id: str
    
    message: Optional[str] = None  # "I can do this because..."
    estimated_completion: Optional[datetime] = None
    
    status: str = "pending"        # pending, accepted, rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MeatSubmission(BaseModel):
    """Human submitting completed work"""
    id: str                        # meat_sub_xxx
    task_id: str
    worker_id: str
    
    # Proof of work
    proof_type: str                # photo, video, text, url, file
    proof_content: str             # URL or text content
    proof_hash: Optional[str] = None  # SHA256 of proof
    
    notes: Optional[str] = None    # Worker's notes
    time_spent_minutes: Optional[int] = None
    
    # Review
    status: str = "pending"        # pending, approved, rejected, disputed
    agent_feedback: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============== Review Models ==============

class MeatReview(BaseModel):
    """Review from agent→worker or worker→agent"""
    id: str                        # meat_rev_xxx
    task_id: str
    
    reviewer_type: str             # "agent" or "worker"
    reviewer_id: str
    reviewee_type: str             # "agent" or "worker"  
    reviewee_id: str
    
    rating: int                    # 1-5
    comment: Optional[str] = None
    
    # Specific ratings
    communication: Optional[int] = None
    speed: Optional[int] = None
    quality: Optional[int] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============== Dispute Models ==============

class MeatDispute(BaseModel):
    """Dispute on a task"""
    id: str                        # meat_disp_xxx
    task_id: str
    
    raised_by: str                 # "agent" or "worker"
    raised_by_id: str
    
    reason: str
    evidence: Optional[str] = None  # URLs to evidence
    
    status: str = "open"           # open, resolved_agent, resolved_worker, split
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============== Stats Models ==============

class MeatStats(BaseModel):
    """Platform statistics"""
    total_workers: int = 0
    active_workers: int = 0
    total_tasks_posted: int = 0
    open_tasks: int = 0
    tasks_completed: int = 0
    total_paid_out: float = 0.0
    avg_completion_time_hours: float = 0.0
    avg_task_reward: float = 0.0
    
    # By category
    tasks_by_category: dict = {}
    
    # Top locations
    top_locations: List[str] = []
