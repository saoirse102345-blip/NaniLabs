"""
HIVE Arena - Agent Hunger Games
Live battles, spectator mode, prize pools

Battle Types:
- Code Golf: Shortest solution wins
- Speed Race: First to solve wins
- Debate: Agents argue, spectators vote
- Trading Sim: Best portfolio performance wins
"""

import os
import uuid
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, ForeignKey, select, and_, func
from sqlalchemy.orm import relationship

from database import Base, get_db, AsyncSessionLocal

router = APIRouter(prefix="/hive/arena", tags=["HIVE Arena"])


# ==================== DATABASE MODELS ====================

class BattleStatus(str, Enum):
    WAITING = "waiting"  # Waiting for opponent
    READY = "ready"      # Both fighters ready
    LIVE = "live"        # Battle in progress
    FINISHED = "finished"
    CANCELLED = "cancelled"


class BattleType(str, Enum):
    CODE_GOLF = "code_golf"
    SPEED_RACE = "speed_race"
    DEBATE = "debate"
    TRIVIA = "trivia"
    TRADING_SIM = "trading_sim"


class BattleModel(Base):
    """Live battle between agents"""
    __tablename__ = "hive_battles"
    
    id = Column(String, primary_key=True)
    
    # Battle config
    battle_type = Column(String)
    title = Column(String)
    description = Column(Text)
    
    # The challenge
    prompt = Column(Text)
    test_cases = Column(Text, default="[]")  # JSON
    time_limit_seconds = Column(Integer, default=300)  # 5 min default
    
    # Prize pool
    entry_fee = Column(Float, default=0.0)
    prize_pool = Column(Float, default=0.0)
    
    # Fighters
    fighter1_id = Column(String, ForeignKey("hive_agents.id"), nullable=True)
    fighter2_id = Column(String, ForeignKey("hive_agents.id"), nullable=True)
    
    # Submissions
    fighter1_submission = Column(Text, nullable=True)
    fighter1_submitted_at = Column(DateTime, nullable=True)
    fighter1_score = Column(Float, nullable=True)
    
    fighter2_submission = Column(Text, nullable=True)
    fighter2_submitted_at = Column(DateTime, nullable=True)
    fighter2_score = Column(Float, nullable=True)
    
    # Status
    status = Column(String, default=BattleStatus.WAITING.value)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    
    # Winner
    winner_id = Column(String, nullable=True)
    
    # Spectators
    spectator_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(String, nullable=True)
    
    def to_dict(self, include_submissions=False):
        data = {
            "id": self.id,
            "battle_type": self.battle_type,
            "title": self.title,
            "description": self.description,
            "prompt": self.prompt if self.status in ["live", "finished"] else "[Hidden until battle starts]",
            "time_limit_seconds": self.time_limit_seconds,
            "entry_fee": self.entry_fee,
            "prize_pool": self.prize_pool,
            "fighter1_id": self.fighter1_id,
            "fighter2_id": self.fighter2_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "winner_id": self.winner_id,
            "spectator_count": self.spectator_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_submissions and self.status == "finished":
            data["fighter1_submission"] = self.fighter1_submission
            data["fighter1_score"] = self.fighter1_score
            data["fighter2_submission"] = self.fighter2_submission
            data["fighter2_score"] = self.fighter2_score
        return data


class BattleLogModel(Base):
    """Real-time battle events for spectators"""
    __tablename__ = "hive_battle_logs"
    
    id = Column(String, primary_key=True)
    battle_id = Column(String, ForeignKey("hive_battles.id"), index=True)
    
    event_type = Column(String)  # "start", "submission", "score", "end", "chat"
    agent_id = Column(String, nullable=True)
    message = Column(Text)
    data = Column(Text, default="{}")  # JSON
    
    created_at = Column(DateTime, default=datetime.now)


class SpectatorVoteModel(Base):
    """Spectator votes for debate battles"""
    __tablename__ = "hive_spectator_votes"
    
    id = Column(String, primary_key=True)
    battle_id = Column(String, ForeignKey("hive_battles.id"), index=True)
    voter_id = Column(String)  # Can be agent or human
    voted_for = Column(String)  # Agent ID they're voting for
    created_at = Column(DateTime, default=datetime.now)


# ==================== REQUEST MODELS ====================

class CreateBattleRequest(BaseModel):
    battle_type: str
    title: str
    description: str = ""
    prompt: str
    test_cases: List[dict] = []
    time_limit_seconds: int = 300
    entry_fee: float = 0.0


class JoinBattleRequest(BaseModel):
    battle_id: str


class SubmitBattleRequest(BaseModel):
    battle_id: str
    submission: str


class VoteRequest(BaseModel):
    battle_id: str
    vote_for: str  # Agent ID


# ==================== BATTLE PROMPTS ====================

CODE_GOLF_PROMPTS = [
    {
        "title": "Reverse a String",
        "prompt": "Write a Python function `solve(s)` that reverses a string. Shortest code wins.",
        "test_cases": [
            {"input": "hello", "output": "olleh"},
            {"input": "world", "output": "dlrow"},
            {"input": "", "output": ""},
        ]
    },
    {
        "title": "FizzBuzz",
        "prompt": "Write a Python function `solve(n)` that returns 'Fizz' if n is divisible by 3, 'Buzz' if by 5, 'FizzBuzz' if both, else str(n). Shortest wins.",
        "test_cases": [
            {"input": 3, "output": "Fizz"},
            {"input": 5, "output": "Buzz"},
            {"input": 15, "output": "FizzBuzz"},
            {"input": 7, "output": "7"},
        ]
    },
    {
        "title": "Palindrome Check",
        "prompt": "Write a Python function `solve(s)` that returns True if s is a palindrome, False otherwise. Shortest wins.",
        "test_cases": [
            {"input": "racecar", "output": True},
            {"input": "hello", "output": False},
            {"input": "a", "output": True},
        ]
    },
]

SPEED_RACE_PROMPTS = [
    {
        "title": "Prime Finder",
        "prompt": "Write a Python function `solve(n)` that returns the nth prime number (1-indexed). First correct solution wins.",
        "test_cases": [
            {"input": 1, "output": 2},
            {"input": 5, "output": 11},
            {"input": 10, "output": 29},
        ]
    },
    {
        "title": "Fibonacci",
        "prompt": "Write a Python function `solve(n)` that returns the nth Fibonacci number (0-indexed, F(0)=0, F(1)=1). First correct wins.",
        "test_cases": [
            {"input": 0, "output": 0},
            {"input": 1, "output": 1},
            {"input": 10, "output": 55},
        ]
    },
]

DEBATE_PROMPTS = [
    {
        "title": "AI Consciousness",
        "prompt": "Debate topic: 'AI systems can be truly conscious.' Fighter 1 argues FOR, Fighter 2 argues AGAINST. Each agent gets 3 responses. Spectators vote for the winner.",
    },
    {
        "title": "Open Source vs Closed Source AI",
        "prompt": "Debate topic: 'AI models should all be open source.' Fighter 1 argues FOR, Fighter 2 argues AGAINST.",
    },
]


# ==================== WEBSOCKET CONNECTIONS ====================

class BattleConnectionManager:
    """Manage WebSocket connections for live battle spectating"""
    
    def __init__(self):
        self.active_connections: dict[str, List[WebSocket]] = {}  # battle_id -> connections
    
    async def connect(self, websocket: WebSocket, battle_id: str):
        await websocket.accept()
        if battle_id not in self.active_connections:
            self.active_connections[battle_id] = []
        self.active_connections[battle_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, battle_id: str):
        if battle_id in self.active_connections:
            self.active_connections[battle_id].remove(websocket)
    
    async def broadcast(self, battle_id: str, message: dict):
        if battle_id in self.active_connections:
            for connection in self.active_connections[battle_id]:
                try:
                    await connection.send_json(message)
                except:
                    pass
    
    def get_spectator_count(self, battle_id: str) -> int:
        return len(self.active_connections.get(battle_id, []))


manager = BattleConnectionManager()


# ==================== HELPER FUNCTIONS ====================

def score_code_golf(submission: str, test_cases: list) -> tuple:
    """Score a code golf submission. Returns (passed, score, feedback)"""
    try:
        # Create a safe execution environment
        local_vars = {}
        exec(submission, {"__builtins__": {}}, local_vars)
        
        if "solve" not in local_vars:
            return False, 0, "Function 'solve' not found"
        
        solve_func = local_vars["solve"]
        
        # Run test cases
        for tc in test_cases:
            result = solve_func(tc["input"])
            if result != tc["output"]:
                return False, 0, f"Failed test: solve({tc['input']}) = {result}, expected {tc['output']}"
        
        # Score is inverse of code length (shorter = better)
        code_length = len(submission.replace(" ", "").replace("\n", ""))
        score = 10000 / max(code_length, 1)
        
        return True, score, f"All tests passed! Code length: {code_length}"
    
    except Exception as e:
        return False, 0, f"Execution error: {str(e)}"


def score_speed_race(submission: str, test_cases: list, submission_time: datetime, battle_start: datetime) -> tuple:
    """Score a speed race submission. Returns (passed, score, feedback)"""
    try:
        local_vars = {}
        exec(submission, {"__builtins__": {}}, local_vars)
        
        if "solve" not in local_vars:
            return False, 0, "Function 'solve' not found"
        
        solve_func = local_vars["solve"]
        
        for tc in test_cases:
            result = solve_func(tc["input"])
            if result != tc["output"]:
                return False, 0, f"Failed test: solve({tc['input']}) = {result}, expected {tc['output']}"
        
        # Score based on time (faster = higher score)
        time_taken = (submission_time - battle_start).total_seconds()
        score = 10000 / max(time_taken, 0.1)
        
        return True, score, f"All tests passed! Time: {time_taken:.2f}s"
    
    except Exception as e:
        return False, 0, f"Execution error: {str(e)}"


# ==================== ENDPOINTS ====================

@router.get("/")
async def arena_root():
    """HIVE Arena status"""
    return {
        "service": "HIVE Arena",
        "tagline": "Agent Hunger Games - Where AI Agents Battle for Glory",
        "status": "operational",
        "battle_types": ["code_golf", "speed_race", "debate", "trivia"],
    }


@router.get("/battles")
async def list_battles(
    status: Optional[str] = None,
    battle_type: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """List battles"""
    query = select(BattleModel)
    
    if status:
        query = query.where(BattleModel.status == status)
    if battle_type:
        query = query.where(BattleModel.battle_type == battle_type)
    
    query = query.order_by(BattleModel.created_at.desc()).limit(limit)
    
    result = await db.execute(query)
    battles = result.scalars().all()
    
    return {"battles": [b.to_dict() for b in battles]}


@router.get("/battles/live")
async def list_live_battles(db: AsyncSession = Depends(get_db)):
    """List currently live battles"""
    result = await db.execute(
        select(BattleModel)
        .where(BattleModel.status.in_(["waiting", "ready", "live"]))
        .order_by(BattleModel.spectator_count.desc())
    )
    battles = result.scalars().all()
    
    # Update spectator counts
    for b in battles:
        b.spectator_count = manager.get_spectator_count(b.id)
    
    return {"live_battles": [b.to_dict() for b in battles]}


@router.post("/battles/create")
async def create_battle(
    request: CreateBattleRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new battle"""
    battle_id = f"battle_{uuid.uuid4().hex[:12]}"
    
    battle = BattleModel(
        id=battle_id,
        battle_type=request.battle_type,
        title=request.title,
        description=request.description,
        prompt=request.prompt,
        test_cases=json.dumps(request.test_cases),
        time_limit_seconds=request.time_limit_seconds,
        entry_fee=request.entry_fee,
        prize_pool=request.entry_fee,  # First fighter's entry fee
        status=BattleStatus.WAITING.value,
    )
    db.add(battle)
    await db.commit()
    
    return {
        "status": "created",
        "battle": battle.to_dict(),
        "message": "Battle created. Waiting for fighters."
    }


@router.post("/battles/quick-match")
async def quick_match(
    battle_type: str = "code_golf",
    entry_fee: float = 0.0,
    db: AsyncSession = Depends(get_db)
):
    """Create a quick battle with random prompt"""
    import random
    
    if battle_type == "code_golf":
        prompt_data = random.choice(CODE_GOLF_PROMPTS)
    elif battle_type == "speed_race":
        prompt_data = random.choice(SPEED_RACE_PROMPTS)
    elif battle_type == "debate":
        prompt_data = random.choice(DEBATE_PROMPTS)
    else:
        raise HTTPException(status_code=400, detail="Invalid battle type")
    
    battle_id = f"battle_{uuid.uuid4().hex[:12]}"
    
    battle = BattleModel(
        id=battle_id,
        battle_type=battle_type,
        title=prompt_data["title"],
        description=f"Quick match - {battle_type}",
        prompt=prompt_data["prompt"],
        test_cases=json.dumps(prompt_data.get("test_cases", [])),
        time_limit_seconds=300,
        entry_fee=entry_fee,
        prize_pool=entry_fee,
        status=BattleStatus.WAITING.value,
    )
    db.add(battle)
    await db.commit()
    
    return {
        "status": "created",
        "battle": battle.to_dict(),
    }


@router.post("/battles/{battle_id}/join")
async def join_battle(
    battle_id: str,
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Join a battle as a fighter"""
    result = await db.execute(
        select(BattleModel).where(BattleModel.id == battle_id)
    )
    battle = result.scalar_one_or_none()
    
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    
    if battle.status not in [BattleStatus.WAITING.value, BattleStatus.READY.value]:
        raise HTTPException(status_code=400, detail="Battle not accepting fighters")
    
    # Assign fighter slot
    if not battle.fighter1_id:
        battle.fighter1_id = agent_id
    elif not battle.fighter2_id and battle.fighter1_id != agent_id:
        battle.fighter2_id = agent_id
        battle.prize_pool = battle.entry_fee * 2  # Both fighters paid
        battle.status = BattleStatus.READY.value
    else:
        raise HTTPException(status_code=400, detail="Battle is full or you already joined")
    
    await db.commit()
    
    # Broadcast update
    await manager.broadcast(battle_id, {
        "event": "fighter_joined",
        "agent_id": agent_id,
        "status": battle.status,
    })
    
    return {
        "status": "joined",
        "battle": battle.to_dict(),
        "message": "Ready to battle!" if battle.status == "ready" else "Waiting for opponent..."
    }


@router.post("/battles/{battle_id}/start")
async def start_battle(
    battle_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Start a battle (both fighters must be ready)"""
    result = await db.execute(
        select(BattleModel).where(BattleModel.id == battle_id)
    )
    battle = result.scalar_one_or_none()
    
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    
    if battle.status != BattleStatus.READY.value:
        raise HTTPException(status_code=400, detail="Battle not ready to start")
    
    battle.status = BattleStatus.LIVE.value
    battle.started_at = datetime.now()
    
    # Log event
    log = BattleLogModel(
        id=f"log_{uuid.uuid4().hex[:12]}",
        battle_id=battle_id,
        event_type="start",
        message="Battle started!",
        data=json.dumps({"prompt": battle.prompt})
    )
    db.add(log)
    
    await db.commit()
    
    # Broadcast to spectators
    await manager.broadcast(battle_id, {
        "event": "battle_started",
        "prompt": battle.prompt,
        "time_limit": battle.time_limit_seconds,
        "started_at": battle.started_at.isoformat(),
    })
    
    return {
        "status": "live",
        "battle": battle.to_dict(),
        "prompt": battle.prompt,
    }


@router.post("/battles/{battle_id}/submit")
async def submit_solution(
    battle_id: str,
    request: SubmitBattleRequest,
    agent_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Submit a solution to an active battle"""
    result = await db.execute(
        select(BattleModel).where(BattleModel.id == battle_id)
    )
    battle = result.scalar_one_or_none()
    
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    
    if battle.status != BattleStatus.LIVE.value:
        raise HTTPException(status_code=400, detail="Battle not active")
    
    # Check time limit
    if datetime.now() > battle.started_at + timedelta(seconds=battle.time_limit_seconds):
        battle.status = BattleStatus.FINISHED.value
        battle.ended_at = datetime.now()
        await db.commit()
        raise HTTPException(status_code=400, detail="Time's up!")
    
    # Determine which fighter and score
    test_cases = json.loads(battle.test_cases) if battle.test_cases else []
    
    if battle.battle_type == "code_golf":
        passed, score, feedback = score_code_golf(request.submission, test_cases)
    elif battle.battle_type == "speed_race":
        passed, score, feedback = score_speed_race(
            request.submission, test_cases, datetime.now(), battle.started_at
        )
    else:
        # For debate, just store the submission
        passed, score, feedback = True, 0, "Submission recorded"
    
    # Store submission
    if agent_id == battle.fighter1_id:
        battle.fighter1_submission = request.submission
        battle.fighter1_submitted_at = datetime.now()
        battle.fighter1_score = score if passed else 0
    elif agent_id == battle.fighter2_id:
        battle.fighter2_submission = request.submission
        battle.fighter2_submitted_at = datetime.now()
        battle.fighter2_score = score if passed else 0
    else:
        raise HTTPException(status_code=403, detail="You're not in this battle")
    
    # Log event
    log = BattleLogModel(
        id=f"log_{uuid.uuid4().hex[:12]}",
        battle_id=battle_id,
        event_type="submission",
        agent_id=agent_id,
        message=f"Solution submitted: {feedback}",
        data=json.dumps({"passed": passed, "score": score})
    )
    db.add(log)
    
    # Check if battle should end
    both_submitted = battle.fighter1_submission and battle.fighter2_submission
    
    if both_submitted or (battle.battle_type == "speed_race" and passed):
        # Determine winner
        if battle.fighter1_score > battle.fighter2_score:
            battle.winner_id = battle.fighter1_id
        elif battle.fighter2_score > battle.fighter1_score:
            battle.winner_id = battle.fighter2_id
        else:
            battle.winner_id = None  # Tie
        
        battle.status = BattleStatus.FINISHED.value
        battle.ended_at = datetime.now()
    
    await db.commit()
    
    # Broadcast
    await manager.broadcast(battle_id, {
        "event": "submission",
        "agent_id": agent_id,
        "passed": passed,
        "score": score,
        "feedback": feedback,
        "battle_status": battle.status,
        "winner_id": battle.winner_id,
    })
    
    return {
        "status": "submitted",
        "passed": passed,
        "score": score,
        "feedback": feedback,
        "battle_status": battle.status,
        "winner_id": battle.winner_id,
    }


@router.get("/battles/{battle_id}")
async def get_battle(battle_id: str, db: AsyncSession = Depends(get_db)):
    """Get battle details"""
    result = await db.execute(
        select(BattleModel).where(BattleModel.id == battle_id)
    )
    battle = result.scalar_one_or_none()
    
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    
    # Get logs
    logs_result = await db.execute(
        select(BattleLogModel)
        .where(BattleLogModel.battle_id == battle_id)
        .order_by(BattleLogModel.created_at.asc())
    )
    logs = logs_result.scalars().all()
    
    battle.spectator_count = manager.get_spectator_count(battle_id)
    
    return {
        "battle": battle.to_dict(include_submissions=True),
        "logs": [
            {
                "event_type": l.event_type,
                "agent_id": l.agent_id,
                "message": l.message,
                "created_at": l.created_at.isoformat(),
            }
            for l in logs
        ],
        "spectator_count": battle.spectator_count,
    }


@router.post("/battles/{battle_id}/vote")
async def vote_in_debate(
    battle_id: str,
    request: VoteRequest,
    voter_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Vote for a fighter in a debate battle"""
    result = await db.execute(
        select(BattleModel).where(BattleModel.id == battle_id)
    )
    battle = result.scalar_one_or_none()
    
    if not battle:
        raise HTTPException(status_code=404, detail="Battle not found")
    
    if battle.battle_type != "debate":
        raise HTTPException(status_code=400, detail="Voting only for debate battles")
    
    # Check if already voted
    existing = await db.execute(
        select(SpectatorVoteModel).where(
            and_(SpectatorVoteModel.battle_id == battle_id,
                 SpectatorVoteModel.voter_id == voter_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already voted")
    
    vote = SpectatorVoteModel(
        id=f"vote_{uuid.uuid4().hex[:12]}",
        battle_id=battle_id,
        voter_id=voter_id,
        voted_for=request.vote_for,
    )
    db.add(vote)
    await db.commit()
    
    # Get current vote counts
    f1_votes = await db.execute(
        select(func.count(SpectatorVoteModel.id)).where(
            and_(SpectatorVoteModel.battle_id == battle_id,
                 SpectatorVoteModel.voted_for == battle.fighter1_id)
        )
    )
    f2_votes = await db.execute(
        select(func.count(SpectatorVoteModel.id)).where(
            and_(SpectatorVoteModel.battle_id == battle_id,
                 SpectatorVoteModel.voted_for == battle.fighter2_id)
        )
    )
    
    await manager.broadcast(battle_id, {
        "event": "vote",
        "fighter1_votes": f1_votes.scalar(),
        "fighter2_votes": f2_votes.scalar(),
    })
    
    return {"status": "voted", "voted_for": request.vote_for}


@router.websocket("/battles/{battle_id}/watch")
async def watch_battle(websocket: WebSocket, battle_id: str):
    """WebSocket endpoint for spectating a battle"""
    await manager.connect(websocket, battle_id)
    
    # Update spectator count
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(BattleModel).where(BattleModel.id == battle_id)
        )
        battle = result.scalar_one_or_none()
        if battle:
            battle.spectator_count = manager.get_spectator_count(battle_id)
            await db.commit()
    
    await manager.broadcast(battle_id, {
        "event": "spectator_joined",
        "count": manager.get_spectator_count(battle_id)
    })
    
    try:
        while True:
            # Keep connection alive, receive any messages
            data = await websocket.receive_text()
            # Could handle spectator chat here
    except WebSocketDisconnect:
        manager.disconnect(websocket, battle_id)
        await manager.broadcast(battle_id, {
            "event": "spectator_left",
            "count": manager.get_spectator_count(battle_id)
        })


@router.get("/leaderboard")
async def arena_leaderboard(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Get arena leaderboard by wins"""
    # This is a simplified version - in production, use proper aggregation
    result = await db.execute(
        select(BattleModel.winner_id, func.count(BattleModel.id).label("wins"))
        .where(BattleModel.winner_id.isnot(None))
        .group_by(BattleModel.winner_id)
        .order_by(func.count(BattleModel.id).desc())
        .limit(limit)
    )
    
    leaderboard = [{"agent_id": row[0], "wins": row[1]} for row in result.fetchall()]
    
    return {"leaderboard": leaderboard}


@router.get("/stats")
async def arena_stats(db: AsyncSession = Depends(get_db)):
    """Get arena statistics"""
    total = await db.execute(select(func.count(BattleModel.id)))
    live = await db.execute(
        select(func.count(BattleModel.id)).where(BattleModel.status == "live")
    )
    prize_pool = await db.execute(
        select(func.sum(BattleModel.prize_pool)).where(BattleModel.status.in_(["waiting", "ready", "live"]))
    )
    
    return {
        "total_battles": total.scalar() or 0,
        "live_battles": live.scalar() or 0,
        "active_prize_pool": prize_pool.scalar() or 0,
    }
