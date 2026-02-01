"""
AURA Database Layer - SQLite persistence for agent state
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent.parent / "data" / "aura.db"

def get_db_path() -> Path:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH

@contextmanager
def get_connection():
    """Get a database connection with auto-commit"""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_database():
    """Initialize the database schema"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Agent state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_state (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                balance_usd REAL DEFAULT 0.0,
                total_earned REAL DEFAULT 0.0,
                total_spent REAL DEFAULT 0.0,
                state TEXT DEFAULT 'idle',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        
        # Transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                source_or_purpose TEXT,
                description TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Activity log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                reasoning TEXT,
                revenue REAL DEFAULT 0.0,
                success INTEGER DEFAULT 1,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Tasks table (for freelance work queue)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                task_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                reward_usd REAL DEFAULT 0.0,
                submitted_by TEXT,
                result TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        
        # Content table (for generated content)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                content_type TEXT NOT NULL,
                title TEXT,
                body TEXT NOT NULL,
                platform TEXT,
                status TEXT DEFAULT 'draft',
                revenue REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                published_at TEXT
            )
        """)
        
        # Memory table (for agent learning)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                strategy TEXT,
                data TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        
        print("✅ Database initialized")

# Agent State Operations
def save_agent_state(name: str, balance: float, total_earned: float, total_spent: float, state: str):
    """Save or update agent state"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO agent_state (name, balance_usd, total_earned, total_spent, state, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                balance_usd = excluded.balance_usd,
                total_earned = excluded.total_earned,
                total_spent = excluded.total_spent,
                state = excluded.state,
                updated_at = excluded.updated_at
        """, (name, balance, total_earned, total_spent, state, datetime.now().isoformat(), datetime.now().isoformat()))

def load_agent_state(name: str) -> Optional[Dict[str, Any]]:
    """Load agent state from database"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM agent_state WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return dict(row)
    return None

# Transaction Operations
def add_transaction(agent_name: str, tx_type: str, amount: float, source_or_purpose: str, description: str = ""):
    """Add a transaction record"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO transactions (agent_name, type, amount, source_or_purpose, description, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_name, tx_type, amount, source_or_purpose, description, datetime.now().isoformat()))

def get_transactions(agent_name: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent transactions"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM transactions 
            WHERE agent_name = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (agent_name, limit))
        return [dict(row) for row in cursor.fetchall()]

# Activity Log Operations
def log_activity(agent_name: str, action: str, details: str = "", reasoning: str = "", revenue: float = 0.0, success: bool = True):
    """Log an agent activity"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO activity_log (agent_name, action, details, reasoning, revenue, success, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (agent_name, action, details, reasoning, revenue, 1 if success else 0, datetime.now().isoformat()))

def get_activity_log(agent_name: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent activity log"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM activity_log 
            WHERE agent_name = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (agent_name, limit))
        return [dict(row) for row in cursor.fetchall()]

# Task Operations
def create_task(title: str, description: str, task_type: str, reward_usd: float, submitted_by: str = "anonymous") -> int:
    """Create a new task for the agent"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (title, description, task_type, status, reward_usd, submitted_by, created_at)
            VALUES (?, ?, ?, 'pending', ?, ?, ?)
        """, (title, description, task_type, reward_usd, submitted_by, datetime.now().isoformat()))
        return cursor.lastrowid

def get_pending_tasks(limit: int = 10) -> List[Dict[str, Any]]:
    """Get pending tasks"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks 
            WHERE status = 'pending' 
            ORDER BY reward_usd DESC, created_at ASC 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

def update_task(task_id: int, status: str, result: str = None):
    """Update task status"""
    with get_connection() as conn:
        cursor = conn.cursor()
        completed_at = datetime.now().isoformat() if status == 'completed' else None
        cursor.execute("""
            UPDATE tasks SET status = ?, result = ?, completed_at = ?
            WHERE id = ?
        """, (status, result, completed_at, task_id))

def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific task"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_tasks(limit: int = 50) -> List[Dict[str, Any]]:
    """Get all tasks"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,))
        return [dict(row) for row in cursor.fetchall()]

# Content Operations
def save_content(agent_name: str, content_type: str, title: str, body: str, platform: str = None) -> int:
    """Save generated content"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO content (agent_name, content_type, title, body, platform, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_name, content_type, title, body, platform, datetime.now().isoformat()))
        return cursor.lastrowid

def get_content(agent_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get generated content"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM content 
            WHERE agent_name = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (agent_name, limit))
        return [dict(row) for row in cursor.fetchall()]

def update_content_status(content_id: int, status: str, revenue: float = 0.0):
    """Update content status (draft/published/monetized)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        published_at = datetime.now().isoformat() if status == 'published' else None
        cursor.execute("""
            UPDATE content SET status = ?, revenue = ?, published_at = COALESCE(published_at, ?)
            WHERE id = ?
        """, (status, revenue, published_at, content_id))

# Memory Operations
def save_memory(agent_name: str, memory_type: str, strategy: str, data: Dict[str, Any]):
    """Save agent memory/learning"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO memory (agent_name, memory_type, strategy, data, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (agent_name, memory_type, strategy, json.dumps(data), datetime.now().isoformat()))

def get_memories(agent_name: str, memory_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
    """Get agent memories"""
    with get_connection() as conn:
        cursor = conn.cursor()
        if memory_type:
            cursor.execute("""
                SELECT * FROM memory 
                WHERE agent_name = ? AND memory_type = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (agent_name, memory_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM memory 
                WHERE agent_name = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (agent_name, limit))
        
        rows = [dict(row) for row in cursor.fetchall()]
        for row in rows:
            if row['data']:
                row['data'] = json.loads(row['data'])
        return rows

# Stats Operations
def get_stats(agent_name: str) -> Dict[str, Any]:
    """Get agent statistics"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get agent state
        cursor.execute("SELECT * FROM agent_state WHERE name = ?", (agent_name,))
        state_row = cursor.fetchone()
        
        # Count activities
        cursor.execute("SELECT COUNT(*) as count FROM activity_log WHERE agent_name = ?", (agent_name,))
        activity_count = cursor.fetchone()['count']
        
        # Count tasks completed
        cursor.execute("SELECT COUNT(*) as count FROM tasks WHERE status = 'completed'")
        tasks_completed = cursor.fetchone()['count']
        
        # Count content created
        cursor.execute("SELECT COUNT(*) as count FROM content WHERE agent_name = ?", (agent_name,))
        content_count = cursor.fetchone()['count']
        
        # Get successful strategies count
        cursor.execute("""
            SELECT COUNT(*) as count FROM memory 
            WHERE agent_name = ? AND memory_type = 'success'
        """, (agent_name,))
        success_count = cursor.fetchone()['count']
        
        return {
            "state": dict(state_row) if state_row else None,
            "activity_count": activity_count,
            "tasks_completed": tasks_completed,
            "content_count": content_count,
            "success_count": success_count
        }

if __name__ == "__main__":
    init_database()
    print("Database ready!")
