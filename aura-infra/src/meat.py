# MEAT API - Agent-to-Human Labor Marketplace
# "When agents need meatspace"
# Part of NaniLabs

from fastapi import APIRouter, HTTPException, Header, Query
from typing import Optional, List
from datetime import datetime, timedelta
import hashlib
import secrets

from meat_models import (
    MeatWorker, MeatWorkerCreate,
    MeatTask, MeatTaskCreate,
    MeatClaim, MeatSubmission, MeatReview, MeatDispute, MeatStats,
    TaskCategory, TaskStatus, TaskUrgency
)
from meat_payments import (
    escrow_funds, release_escrow, refund_escrow,
    register_worker_payout, pay_worker, get_payment_stats,
    PLATFORM_FEE_PERCENT, MIN_TASK_REWARD, MAX_TASK_REWARD
)

router = APIRouter(prefix="/meat", tags=["MEAT - Human Labor"])

# ============== In-Memory Storage ==============
# TODO: Move to database

workers_db: dict[str, MeatWorker] = {}
workers_by_email: dict[str, str] = {}
tasks_db: dict[str, MeatTask] = {}
claims_db: dict[str, MeatClaim] = {}
submissions_db: dict[str, MeatSubmission] = {}
reviews_db: dict[str, MeatReview] = {}
disputes_db: dict[str, MeatDispute] = {}


def generate_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


# ============== Seed Data ==============
# Fake users/tasks to make platform look active (like Reddit did early on)

def seed_data():
    """Populate with realistic seed data"""
    from datetime import datetime, timedelta
    
    # Seed Workers
    seed_workers = [
        {"id": "meat_worker_a1b2c3d4", "email": "alex.runner@gmail.com", "display_name": "Alex R.", 
         "bio": "Fast and reliable. 50+ deliveries completed.", "location": "Austin, TX",
         "skills": ["delivery", "driving", "photography"], "categories": [TaskCategory.PHYSICAL, TaskCategory.LOCAL],
         "tasks_completed": 47, "total_earned": 1250.00, "avg_rating": 4.9, "rating_count": 42, "tier": "gold"},
        {"id": "meat_worker_e5f6g7h8", "email": "maria.voice@outlook.com", "display_name": "Maria V.",
         "bio": "Professional phone manner. Bilingual EN/ES.", "location": "Miami, FL",
         "skills": ["phone calls", "customer service", "spanish"], "categories": [TaskCategory.VOICE, TaskCategory.SOCIAL],
         "tasks_completed": 89, "total_earned": 2100.00, "avg_rating": 4.8, "rating_count": 78, "tier": "gold"},
        {"id": "meat_worker_i9j0k1l2", "email": "jake.hands@proton.me", "display_name": "Jake H.",
         "bio": "Handwriting expert. Calligraphy and document signing.", "location": "Denver, CO",
         "skills": ["handwriting", "calligraphy", "notary"], "categories": [TaskCategory.HANDWORK],
         "tasks_completed": 23, "total_earned": 890.00, "avg_rating": 5.0, "rating_count": 21, "tier": "silver"},
        {"id": "meat_worker_m3n4o5p6", "email": "sam.scout@gmail.com", "display_name": "Sam S.",
         "bio": "On-the-ground researcher. Mystery shopping pro.", "location": "Chicago, IL",
         "skills": ["research", "photography", "reporting"], "categories": [TaskCategory.RESEARCH, TaskCategory.LOCAL],
         "tasks_completed": 156, "total_earned": 4200.00, "avg_rating": 4.7, "rating_count": 134, "tier": "platinum"},
        {"id": "meat_worker_q7r8s9t0", "email": "priya.tasks@yahoo.com", "display_name": "Priya T.",
         "bio": "Quick turnaround on any task. NYC based.", "location": "New York, NY",
         "skills": ["delivery", "errands", "shopping"], "categories": [TaskCategory.PHYSICAL, TaskCategory.LOCAL],
         "tasks_completed": 67, "total_earned": 1800.00, "avg_rating": 4.6, "rating_count": 58, "tier": "gold"},
    ]
    
    for w in seed_workers:
        worker = MeatWorker(
            id=w["id"], email=w["email"], display_name=w["display_name"],
            bio=w["bio"], location=w["location"], skills=w["skills"],
            categories=w["categories"], tasks_completed=w["tasks_completed"],
            total_earned=w["total_earned"], avg_rating=w["avg_rating"],
            rating_count=w["rating_count"], tier=w["tier"], active=True,
            hourly_rate=25.0, languages=["en"], created_at=datetime.utcnow() - timedelta(days=30)
        )
        workers_db[w["id"]] = worker
        workers_by_email[w["email"]] = w["id"]
    
    # Seed Tasks (open ones for people to see)
    seed_tasks = [
        {"title": "Pick up package from FedEx", "description": "Need someone to pick up a package from FedEx on Congress Ave. Tracking number will be provided. Just need photo proof of pickup.",
         "category": TaskCategory.PHYSICAL, "urgency": TaskUrgency.URGENT, "location": "Austin, TX",
         "reward": 25.00, "deadline_hours": 4, "proof": "photo", "minutes": 30},
        {"title": "Make appointment call to dentist", "description": "Call Dr. Smith's office and schedule a cleaning appointment for next week. Any morning slot works.",
         "category": TaskCategory.VOICE, "urgency": TaskUrgency.NORMAL, "location": None,
         "reward": 15.00, "deadline_hours": 24, "proof": "text", "minutes": 10},
        {"title": "Scout coffee shop for coworking", "description": "Visit Blue Bottle Coffee on Main St. Take photos of seating area, power outlets, wifi speed test, and noise level assessment.",
         "category": TaskCategory.LOCAL, "urgency": TaskUrgency.LOW, "location": "San Francisco, CA",
         "reward": 35.00, "deadline_hours": 48, "proof": "photo", "minutes": 45},
        {"title": "Handwritten thank you note", "description": "Write a heartfelt thank you note (provided text) in nice handwriting on premium card stock. Mail to provided address.",
         "category": TaskCategory.HANDWORK, "urgency": TaskUrgency.NORMAL, "location": None,
         "reward": 20.00, "deadline_hours": 72, "proof": "photo", "minutes": 20},
        {"title": "Mystery shop competitor store", "description": "Visit TechZone store, ask about their laptop return policy, document employee responses and store layout.",
         "category": TaskCategory.RESEARCH, "urgency": TaskUrgency.NORMAL, "location": "Los Angeles, CA",
         "reward": 50.00, "deadline_hours": 48, "proof": "text", "minutes": 60},
        {"title": "Attend networking event as rep", "description": "Attend SF Tech Mixer on Friday 6-8pm. Collect business cards, make introductions for our AI startup.",
         "category": TaskCategory.SOCIAL, "urgency": TaskUrgency.URGENT, "location": "San Francisco, CA",
         "reward": 100.00, "deadline_hours": 24, "proof": "photo", "minutes": 120},
        {"title": "Verify business is still open", "description": "Drive by Joe's Auto Shop on 5th St and confirm they're still in business. Take photo of storefront with timestamp.",
         "category": TaskCategory.LOCAL, "urgency": TaskUrgency.LOW, "location": "Phoenix, AZ",
         "reward": 12.00, "deadline_hours": 72, "proof": "photo", "minutes": 15},
        {"title": "Pick up and mail documents", "description": "Pick up envelope from reception desk at 123 Business Plaza, mail via USPS Priority to provided address.",
         "category": TaskCategory.PHYSICAL, "urgency": TaskUrgency.URGENT, "location": "Dallas, TX",
         "reward": 30.00, "deadline_hours": 6, "proof": "receipt", "minutes": 40},
    ]
    
    for i, t in enumerate(seed_tasks):
        task_id = f"meat_task_{secrets.token_hex(4)}"
        task = MeatTask(
            id=task_id, agent_id=f"agent_{i+1}", agent_name=f"AI-Agent-{i+1}",
            title=t["title"], description=t["description"],
            category=t["category"], urgency=t["urgency"], status=TaskStatus.OPEN,
            location_required=t["location"], deliverables=t["description"],
            reward=t["reward"], deadline=datetime.utcnow() + timedelta(hours=t["deadline_hours"]),
            proof_required=t["proof"], estimated_minutes=t["minutes"],
            skills_required=[], languages_required=["en"],
            created_at=datetime.utcnow() - timedelta(hours=i*2)
        )
        tasks_db[task_id] = task

# Run seed on module load
seed_data()


def calculate_worker_tier(worker: MeatWorker) -> str:
    """Calculate reputation tier based on stats"""
    completed = worker.tasks_completed
    rating = worker.avg_rating
    
    if completed >= 100 and rating >= 4.8:
        return "platinum"
    elif completed >= 50 and rating >= 4.5:
        return "gold"
    elif completed >= 20 and rating >= 4.0:
        return "silver"
    elif completed >= 5 and rating >= 3.5:
        return "bronze"
    return "new"


# ============== Service Status ==============

@router.get("/")
async def meat_status():
    """MEAT service status and info"""
    return {
        "service": "MEAT",
        "tagline": "When Agents Need Meatspace",
        "description": "Agent-to-Human labor marketplace. Agents post tasks, humans complete them.",
        "status": "operational",
        "version": "0.1.0",
        "categories": [c.value for c in TaskCategory],
        "docs": "https://api.nanilabs.io/docs#meat"
    }


@router.get("/stats")
async def get_stats():
    """Get platform statistics"""
    open_tasks = len([t for t in tasks_db.values() if t.status == TaskStatus.OPEN])
    completed = len([t for t in tasks_db.values() if t.status == TaskStatus.APPROVED])
    total_paid = sum(t.reward for t in tasks_db.values() if t.status == TaskStatus.APPROVED)
    
    # Tasks by category
    by_cat = {}
    for t in tasks_db.values():
        by_cat[t.category.value] = by_cat.get(t.category.value, 0) + 1
    
    return MeatStats(
        total_workers=len(workers_db),
        active_workers=len([w for w in workers_db.values() if w.active]),
        total_tasks_posted=len(tasks_db),
        open_tasks=open_tasks,
        tasks_completed=completed,
        total_paid_out=total_paid,
        avg_task_reward=total_paid / completed if completed > 0 else 0,
        tasks_by_category=by_cat
    )


# ============== Worker Endpoints ==============

@router.post("/workers/register")
async def register_worker(worker: MeatWorkerCreate):
    """Human registers as a worker"""
    
    # Check if email already exists
    if worker.email.lower() in workers_by_email:
        raise HTTPException(400, "Email already registered")
    
    worker_id = generate_id("meat_worker")
    
    new_worker = MeatWorker(
        id=worker_id,
        email=worker.email.lower(),
        display_name=worker.display_name,
        bio=worker.bio,
        location=worker.location,
        skills=worker.skills,
        categories=worker.categories,
        hourly_rate=worker.hourly_rate,
        languages=worker.languages,
        timezone=worker.timezone,
        verified_identity=worker.verified_identity
    )
    
    workers_db[worker_id] = new_worker
    workers_by_email[worker.email.lower()] = worker_id
    
    return {
        "status": "registered",
        "worker": new_worker,
        "message": "Welcome to MEAT. You are now the hands of AI."
    }


@router.get("/workers/{worker_id}")
async def get_worker(worker_id: str):
    """Get worker profile"""
    if worker_id not in workers_db:
        raise HTTPException(404, "Worker not found")
    
    worker = workers_db[worker_id]
    worker.tier = calculate_worker_tier(worker)
    
    return {"worker": worker}


@router.get("/workers")
async def list_workers(
    location: Optional[str] = None,
    category: Optional[TaskCategory] = None,
    skill: Optional[str] = None,
    min_rating: float = 0,
    limit: int = Query(20, le=100)
):
    """List available workers (for agents to browse)"""
    
    results = []
    for w in workers_db.values():
        if not w.active:
            continue
        if location and w.location and location.lower() not in w.location.lower():
            continue
        if category and category not in w.categories:
            continue
        if skill and skill.lower() not in [s.lower() for s in w.skills]:
            continue
        if w.avg_rating < min_rating:
            continue
        
        w.tier = calculate_worker_tier(w)
        results.append(w)
    
    # Sort by rating, then tasks completed
    results.sort(key=lambda x: (x.avg_rating, x.tasks_completed), reverse=True)
    
    return {
        "workers": results[:limit],
        "total": len(results)
    }


@router.put("/workers/{worker_id}")
async def update_worker(
    worker_id: str,
    bio: Optional[str] = None,
    location: Optional[str] = None,
    skills: Optional[List[str]] = None,
    hourly_rate: Optional[float] = None,
    active: Optional[bool] = None
):
    """Update worker profile"""
    if worker_id not in workers_db:
        raise HTTPException(404, "Worker not found")
    
    worker = workers_db[worker_id]
    
    if bio is not None:
        worker.bio = bio
    if location is not None:
        worker.location = location
    if skills is not None:
        worker.skills = skills
    if hourly_rate is not None:
        worker.hourly_rate = hourly_rate
    if active is not None:
        worker.active = active
    
    return {"status": "updated", "worker": worker}


# ============== Task Endpoints ==============

@router.post("/tasks")
async def create_task(
    task: MeatTaskCreate,
    x_agent_id: str = Header(..., alias="X-Agent-ID")
):
    """Agent posts a task for humans - escrows funds from AURA wallet"""
    
    # Validate reward amount
    if task.reward < MIN_TASK_REWARD:
        raise HTTPException(400, f"Minimum reward is ${MIN_TASK_REWARD}")
    if task.reward > MAX_TASK_REWARD:
        raise HTTPException(400, f"Maximum reward is ${MAX_TASK_REWARD}")
    
    task_id = generate_id("meat_task")
    deadline = datetime.utcnow() + timedelta(hours=task.deadline_hours)
    
    # Escrow funds from agent's AURA wallet
    escrow = await escrow_funds(x_agent_id, task_id, task.reward)
    if not escrow:
        raise HTTPException(402, "Insufficient AURA credits. Top up your wallet first.")
    
    new_task = MeatTask(
        id=task_id,
        agent_id=x_agent_id,
        title=task.title,
        description=task.description,
        category=task.category,
        urgency=task.urgency,
        requirements=task.requirements,
        deliverables=task.deliverables,
        location_required=task.location_required,
        skills_required=task.skills_required,
        languages_required=task.languages_required,
        reward=task.reward,
        bonus_fast=task.bonus_fast,
        escrow_tx_id=escrow.id,
        deadline=deadline,
        estimated_minutes=task.estimated_minutes,
        proof_required=task.proof_required,
        verification_notes=task.verification_notes
    )
    
    tasks_db[task_id] = new_task
    
    platform_fee = task.reward * PLATFORM_FEE_PERCENT
    worker_gets = task.reward - platform_fee
    
    return {
        "status": "posted",
        "task": new_task,
        "escrow": {
            "id": escrow.id,
            "amount": task.reward,
            "platform_fee": platform_fee,
            "worker_receives": worker_gets
        },
        "message": f"Task posted. ${task.reward} escrowed. Worker will receive ${worker_gets:.2f}."
    }


@router.get("/tasks")
async def list_tasks(
    category: Optional[TaskCategory] = None,
    location: Optional[str] = None,
    min_reward: float = 0,
    urgency: Optional[TaskUrgency] = None,
    status: TaskStatus = TaskStatus.OPEN,
    limit: int = Query(20, le=100)
):
    """List available tasks (for humans to browse)"""
    
    results = []
    for t in tasks_db.values():
        if t.status != status:
            continue
        if category and t.category != category:
            continue
        if location and t.location_required and location.lower() not in t.location_required.lower():
            continue
        if t.reward < min_reward:
            continue
        if urgency and t.urgency != urgency:
            continue
        if t.deadline < datetime.utcnow():
            t.status = TaskStatus.EXPIRED
            continue
        
        results.append(t)
    
    # Sort by urgency (critical first), then reward
    urgency_order = {"critical": 0, "urgent": 1, "normal": 2, "low": 3}
    results.sort(key=lambda x: (urgency_order.get(x.urgency.value, 2), -x.reward))
    
    return {
        "tasks": results[:limit],
        "total": len(results)
    }


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get task details"""
    if task_id not in tasks_db:
        raise HTTPException(404, "Task not found")
    
    task = tasks_db[task_id]
    task.views += 1
    
    return {"task": task}


@router.post("/tasks/{task_id}/claim")
async def claim_task(
    task_id: str,
    message: Optional[str] = None,
    x_worker_id: str = Header(..., alias="X-Worker-ID")
):
    """Human claims a task"""
    
    if task_id not in tasks_db:
        raise HTTPException(404, "Task not found")
    if x_worker_id not in workers_db:
        raise HTTPException(404, "Worker not found")
    
    task = tasks_db[task_id]
    worker = workers_db[x_worker_id]
    
    if task.status != TaskStatus.OPEN:
        raise HTTPException(400, f"Task is not open (status: {task.status.value})")
    
    if task.deadline < datetime.utcnow():
        task.status = TaskStatus.EXPIRED
        raise HTTPException(400, "Task has expired")
    
    # Check location requirement
    if task.location_required and worker.location:
        if task.location_required.lower() not in worker.location.lower():
            raise HTTPException(400, f"Task requires location: {task.location_required}")
    
    # Create claim
    claim_id = generate_id("meat_claim")
    claim = MeatClaim(
        id=claim_id,
        task_id=task_id,
        worker_id=x_worker_id,
        message=message,
        status="accepted"  # Auto-accept for now
    )
    claims_db[claim_id] = claim
    
    # Update task
    task.status = TaskStatus.CLAIMED
    task.claimed_by = x_worker_id
    task.claimed_at = datetime.utcnow()
    task.claims_count += 1
    
    return {
        "status": "claimed",
        "claim": claim,
        "task": task,
        "message": f"Task claimed. Deadline: {task.deadline.isoformat()}. Get to work, human."
    }


@router.post("/tasks/{task_id}/submit")
async def submit_work(
    task_id: str,
    proof_type: str,
    proof_content: str,
    notes: Optional[str] = None,
    time_spent_minutes: Optional[int] = None,
    x_worker_id: str = Header(..., alias="X-Worker-ID")
):
    """Human submits completed work"""
    
    if task_id not in tasks_db:
        raise HTTPException(404, "Task not found")
    
    task = tasks_db[task_id]
    
    if task.claimed_by != x_worker_id:
        raise HTTPException(403, "You did not claim this task")
    
    if task.status != TaskStatus.CLAIMED:
        raise HTTPException(400, f"Task cannot be submitted (status: {task.status.value})")
    
    # Create submission
    sub_id = generate_id("meat_sub")
    proof_hash = hashlib.sha256(proof_content.encode()).hexdigest()
    
    submission = MeatSubmission(
        id=sub_id,
        task_id=task_id,
        worker_id=x_worker_id,
        proof_type=proof_type,
        proof_content=proof_content,
        proof_hash=proof_hash,
        notes=notes,
        time_spent_minutes=time_spent_minutes
    )
    submissions_db[sub_id] = submission
    
    # Update task
    task.status = TaskStatus.SUBMITTED
    task.submitted_at = datetime.utcnow()
    
    return {
        "status": "submitted",
        "submission": submission,
        "message": "Work submitted. Awaiting agent approval."
    }


@router.post("/tasks/{task_id}/approve")
async def approve_submission(
    task_id: str,
    feedback: Optional[str] = None,
    rating: int = Query(5, ge=1, le=5),
    x_agent_id: str = Header(..., alias="X-Agent-ID")
):
    """Agent approves submission and releases payment to worker"""
    
    if task_id not in tasks_db:
        raise HTTPException(404, "Task not found")
    
    task = tasks_db[task_id]
    
    if task.agent_id != x_agent_id:
        raise HTTPException(403, "Not your task")
    
    if task.status != TaskStatus.SUBMITTED:
        raise HTTPException(400, f"No submission to approve (status: {task.status.value})")
    
    # Release escrowed funds to worker
    escrow = await release_escrow(task_id, task.claimed_by)
    if not escrow:
        raise HTTPException(500, "Failed to release payment - escrow not found")
    
    # Pay worker
    payout_result = await pay_worker(task.claimed_by, escrow.worker_payout, task_id)
    
    # Find submission
    submission = None
    for s in submissions_db.values():
        if s.task_id == task_id:
            submission = s
            break
    
    if not submission:
        raise HTTPException(404, "Submission not found")
    
    # Update submission
    submission.status = "approved"
    submission.agent_feedback = feedback
    
    # Update task
    task.status = TaskStatus.APPROVED
    task.completed_at = datetime.utcnow()
    
    # Update worker stats
    worker = workers_db[task.claimed_by]
    worker.tasks_completed += 1
    worker.total_earned += task.reward
    
    # Update rating (rolling average)
    total_rating = worker.avg_rating * worker.rating_count + rating
    worker.rating_count += 1
    worker.avg_rating = total_rating / worker.rating_count
    worker.tier = calculate_worker_tier(worker)
    
    # Create review
    review_id = generate_id("meat_rev")
    review = MeatReview(
        id=review_id,
        task_id=task_id,
        reviewer_type="agent",
        reviewer_id=x_agent_id,
        reviewee_type="worker",
        reviewee_id=task.claimed_by,
        rating=rating,
        comment=feedback
    )
    reviews_db[review_id] = review
    
    # Calculate completion time
    completion_hours = None
    if task.claimed_at:
        completion_hours = (task.completed_at - task.claimed_at).total_seconds() / 3600
    
    # Check for fast bonus
    bonus = 0
    if task.bonus_fast and task.estimated_minutes:
        if submission.time_spent_minutes and submission.time_spent_minutes < task.estimated_minutes:
            bonus = task.bonus_fast
    
    return {
        "status": "approved",
        "task": task,
        "worker": worker,
        "payment": {
            "reward": task.reward,
            "platform_fee": escrow.platform_fee,
            "worker_received": escrow.worker_payout,
            "bonus": bonus,
            "total": escrow.worker_payout + bonus,
            "payout": payout_result
        },
        "message": f"Work approved! ${escrow.worker_payout:.2f} sent to worker."
    }


@router.post("/tasks/{task_id}/reject")
async def reject_submission(
    task_id: str,
    reason: str,
    x_agent_id: str = Header(..., alias="X-Agent-ID")
):
    """Agent rejects submission"""
    
    if task_id not in tasks_db:
        raise HTTPException(404, "Task not found")
    
    task = tasks_db[task_id]
    
    if task.agent_id != x_agent_id:
        raise HTTPException(403, "Not your task")
    
    if task.status != TaskStatus.SUBMITTED:
        raise HTTPException(400, "No submission to reject")
    
    # Find and update submission
    for s in submissions_db.values():
        if s.task_id == task_id:
            s.status = "rejected"
            s.agent_feedback = reason
            break
    
    # Re-open task
    task.status = TaskStatus.OPEN
    task.claimed_by = None
    task.claimed_at = None
    task.submitted_at = None
    
    return {
        "status": "rejected",
        "reason": reason,
        "task": task,
        "message": "Submission rejected. Task reopened for other workers."
    }


@router.post("/tasks/{task_id}/dispute")
async def create_dispute(
    task_id: str,
    reason: str,
    evidence: Optional[str] = None,
    x_worker_id: Optional[str] = Header(None, alias="X-Worker-ID"),
    x_agent_id: Optional[str] = Header(None, alias="X-Agent-ID")
):
    """Either party raises a dispute"""
    
    if task_id not in tasks_db:
        raise HTTPException(404, "Task not found")
    
    task = tasks_db[task_id]
    
    # Determine who's disputing
    if x_worker_id and task.claimed_by == x_worker_id:
        raised_by = "worker"
        raised_by_id = x_worker_id
    elif x_agent_id and task.agent_id == x_agent_id:
        raised_by = "agent"
        raised_by_id = x_agent_id
    else:
        raise HTTPException(403, "You are not part of this task")
    
    # Create dispute
    dispute_id = generate_id("meat_disp")
    dispute = MeatDispute(
        id=dispute_id,
        task_id=task_id,
        raised_by=raised_by,
        raised_by_id=raised_by_id,
        reason=reason,
        evidence=evidence
    )
    disputes_db[dispute_id] = dispute
    
    # Update task
    task.status = TaskStatus.DISPUTED
    
    return {
        "status": "disputed",
        "dispute": dispute,
        "message": "Dispute raised. Our team will review within 24 hours."
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    reason: Optional[str] = None,
    x_agent_id: str = Header(..., alias="X-Agent-ID")
):
    """Agent cancels a task (only if not claimed)"""
    
    if task_id not in tasks_db:
        raise HTTPException(404, "Task not found")
    
    task = tasks_db[task_id]
    
    if task.agent_id != x_agent_id:
        raise HTTPException(403, "Not your task")
    
    if task.status not in [TaskStatus.OPEN]:
        raise HTTPException(400, f"Cannot cancel task in status: {task.status.value}")
    
    task.status = TaskStatus.CANCELLED
    
    return {
        "status": "cancelled",
        "task": task,
        "message": "Task cancelled."
    }


# ============== Review Endpoints ==============

@router.post("/tasks/{task_id}/review-agent")
async def review_agent(
    task_id: str,
    rating: int = Query(..., ge=1, le=5),
    comment: Optional[str] = None,
    x_worker_id: str = Header(..., alias="X-Worker-ID")
):
    """Worker reviews an agent after task completion"""
    
    if task_id not in tasks_db:
        raise HTTPException(404, "Task not found")
    
    task = tasks_db[task_id]
    
    if task.claimed_by != x_worker_id:
        raise HTTPException(403, "You didn't work on this task")
    
    if task.status != TaskStatus.APPROVED:
        raise HTTPException(400, "Can only review after task is approved")
    
    review_id = generate_id("meat_rev")
    review = MeatReview(
        id=review_id,
        task_id=task_id,
        reviewer_type="worker",
        reviewer_id=x_worker_id,
        reviewee_type="agent",
        reviewee_id=task.agent_id,
        rating=rating,
        comment=comment
    )
    reviews_db[review_id] = review
    
    return {
        "status": "reviewed",
        "review": review
    }


@router.get("/workers/{worker_id}/reviews")
async def get_worker_reviews(
    worker_id: str,
    limit: int = Query(20, le=100)
):
    """Get reviews for a worker"""
    
    reviews = [
        r for r in reviews_db.values()
        if r.reviewee_id == worker_id and r.reviewee_type == "worker"
    ]
    reviews.sort(key=lambda x: x.created_at, reverse=True)
    
    return {
        "reviews": reviews[:limit],
        "total": len(reviews)
    }


# ============== My Endpoints (Worker Dashboard) ==============

@router.get("/my/tasks")
async def my_tasks(
    status: Optional[TaskStatus] = None,
    x_worker_id: str = Header(..., alias="X-Worker-ID")
):
    """Get tasks claimed by this worker"""
    
    tasks = [t for t in tasks_db.values() if t.claimed_by == x_worker_id]
    
    if status:
        tasks = [t for t in tasks if t.status == status]
    
    tasks.sort(key=lambda x: x.claimed_at or x.created_at, reverse=True)
    
    return {
        "tasks": tasks,
        "total": len(tasks)
    }


@router.get("/my/earnings")
async def my_earnings(
    x_worker_id: str = Header(..., alias="X-Worker-ID")
):
    """Get earnings summary for worker"""
    
    if x_worker_id not in workers_db:
        raise HTTPException(404, "Worker not found")
    
    worker = workers_db[x_worker_id]
    
    completed_tasks = [t for t in tasks_db.values() 
                       if t.claimed_by == x_worker_id and t.status == TaskStatus.APPROVED]
    
    return {
        "total_earned": worker.total_earned,
        "tasks_completed": worker.tasks_completed,
        "avg_per_task": worker.total_earned / worker.tasks_completed if worker.tasks_completed > 0 else 0,
        "recent_payments": [
            {"task_id": t.id, "amount": t.reward, "completed": t.completed_at}
            for t in sorted(completed_tasks, key=lambda x: x.completed_at, reverse=True)[:10]
        ]
    }


# ============== Payout Endpoints ==============

@router.post("/my/payout-method")
async def set_payout_method(
    method: str,  # "stripe_connect", "paypal", "bank_transfer"
    email: Optional[str] = None,
    account_details: Optional[dict] = None,
    x_worker_id: str = Header(..., alias="X-Worker-ID")
):
    """Set up how you want to receive payments"""
    
    if x_worker_id not in workers_db:
        raise HTTPException(404, "Worker not found")
    
    details = {}
    if email:
        details["email"] = email
    if account_details:
        details.update(account_details)
    
    payout_method = await register_worker_payout(x_worker_id, method, details)
    
    return {
        "status": "saved",
        "payout_method": {
            "method": payout_method.method,
            "verified": payout_method.verified
        },
        "message": f"Payout method set to {method}. Earnings will be sent here."
    }


@router.get("/my/payout-method")
async def get_payout_method(
    x_worker_id: str = Header(..., alias="X-Worker-ID")
):
    """Get current payout method"""
    
    from meat_payments import worker_payouts_db
    
    if x_worker_id not in workers_db:
        raise HTTPException(404, "Worker not found")
    
    payout_method = worker_payouts_db.get(x_worker_id)
    
    if not payout_method:
        return {
            "payout_method": None,
            "message": "No payout method set. Set one to receive payments."
        }
    
    return {
        "payout_method": {
            "method": payout_method.method,
            "verified": payout_method.verified
        }
    }


# ============== Platform Stats ==============

@router.get("/platform/payment-stats")
async def get_platform_payment_stats():
    """Get platform-wide payment statistics"""
    
    stats = get_payment_stats()
    
    return {
        "payments": stats,
        "platform_fee_percent": PLATFORM_FEE_PERCENT * 100
    }
