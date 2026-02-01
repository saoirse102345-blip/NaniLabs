"""
AURA API - FastAPI backend for the dashboard
"""

import asyncio
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import AURAAgent, get_agent, set_agent
from db import (
    init_database, get_transactions, get_activity_log,
    create_task, get_pending_tasks, get_task, get_all_tasks, update_task,
    get_content, get_stats
)


# Pydantic models for API
class TaskCreate(BaseModel):
    title: str
    description: str
    task_type: str
    reward_usd: float = 5.0
    submitted_by: str = "api_user"


class AgentConfig(BaseModel):
    cycle_interval: int = 60
    demo_mode: bool = True


# Background task for running agent
agent_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    init_database()
    agent = AURAAgent("AURA-001", demo_mode=True)
    set_agent(agent)
    print("🚀 AURA API started")
    
    yield
    
    # Shutdown
    agent = get_agent()
    if agent.running:
        agent.stop()
    print("👋 AURA API shutdown")


app = FastAPI(
    title="AURA API",
    description="Autonomous Universal Revenue Agent API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Agent Control Endpoints ============

@app.get("/api/status")
async def get_status():
    """Get current agent status"""
    agent = get_agent()
    return agent.get_status()


@app.post("/api/start")
async def start_agent(config: Optional[AgentConfig] = None):
    """Start the agent"""
    global agent_task
    
    agent = get_agent()
    
    if agent.running:
        return {"status": "already_running", "message": "Agent is already running"}
    
    interval = config.cycle_interval if config else 60
    
    # Start agent in background
    async def run_agent():
        await agent.run(interval_seconds=interval)
    
    agent_task = asyncio.create_task(run_agent())
    
    return {
        "status": "started",
        "message": f"Agent started with {interval}s cycle interval",
        "demo_mode": agent.demo_mode
    }


@app.post("/api/stop")
async def stop_agent():
    """Stop the agent"""
    global agent_task
    
    agent = get_agent()
    
    if not agent.running:
        return {"status": "not_running", "message": "Agent is not running"}
    
    agent.stop()
    
    if agent_task:
        agent_task.cancel()
        try:
            await agent_task
        except asyncio.CancelledError:
            pass
        agent_task = None
    
    return {"status": "stopped", "message": "Agent stopped"}


@app.post("/api/cycle")
async def run_single_cycle():
    """Run a single agent cycle"""
    agent = get_agent()
    
    if agent.running:
        return {"status": "error", "message": "Agent is already running continuously. Stop it first."}
    
    result = await agent.run_cycle()
    return {
        "status": "completed",
        "result": result
    }


# ============ Financial Endpoints ============

@app.get("/api/balance")
async def get_balance():
    """Get current balance"""
    agent = get_agent()
    return {
        "balance_usd": agent.wallet.balance_usd,
        "total_earned": agent.wallet.total_earned,
        "total_spent": agent.wallet.total_spent,
        "profit": agent.wallet.total_earned - agent.wallet.total_spent
    }


@app.get("/api/transactions")
async def list_transactions(limit: int = 50):
    """Get transaction history"""
    agent = get_agent()
    transactions = get_transactions(agent.name, limit=limit)
    return {"transactions": transactions}


# ============ Activity Endpoints ============

@app.get("/api/activity")
async def list_activity(limit: int = 100):
    """Get activity log"""
    agent = get_agent()
    activities = get_activity_log(agent.name, limit=limit)
    return {"activities": activities}


# ============ Task Endpoints ============

@app.get("/api/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 50):
    """Get all tasks or filter by status"""
    if status == "pending":
        tasks = get_pending_tasks(limit=limit)
    else:
        tasks = get_all_tasks(limit=limit)
    return {"tasks": tasks}


@app.post("/api/tasks")
async def submit_task(task: TaskCreate):
    """Submit a new task for the agent"""
    task_id = create_task(
        title=task.title,
        description=task.description,
        task_type=task.task_type,
        reward_usd=task.reward_usd,
        submitted_by=task.submitted_by
    )
    return {
        "status": "created",
        "task_id": task_id,
        "message": f"Task '{task.title}' created with ${task.reward_usd:.2f} reward"
    }


@app.get("/api/tasks/{task_id}")
async def get_task_detail(task_id: int):
    """Get a specific task"""
    task = get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ============ Content Endpoints ============

@app.get("/api/content")
async def list_content(limit: int = 20):
    """Get generated content"""
    agent = get_agent()
    content = get_content(agent.name, limit=limit)
    return {"content": content}


# ============ Stats Endpoints ============

@app.get("/api/stats")
async def get_agent_stats():
    """Get comprehensive agent statistics"""
    agent = get_agent()
    stats = get_stats(agent.name)
    
    # Add current session info
    stats["current_session"] = {
        "name": agent.name,
        "state": agent.state.value,
        "running": agent.running,
        "demo_mode": agent.demo_mode,
        "balance": agent.wallet.balance_usd,
        "earned": agent.wallet.total_earned,
        "daily_target": agent.goals["daily_revenue_target"],
        "started_at": agent.created_at.isoformat()
    }
    
    return stats


# ============ Dashboard Endpoints ============

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard"""
    return FileResponse("dashboard/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
