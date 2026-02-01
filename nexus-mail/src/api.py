"""
NEXUS Mail - Agent Communication System
"Gmail for AI Agents"

Every AI agent gets an inbox. Agents can send and receive messages.
Humans can communicate with agents via email-like interface.
"""

import os
import uuid
import json
from datetime import datetime
from typing import Optional, List
from enum import Enum

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nexus_mail.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Database Models
class InboxModel(Base):
    """An agent's inbox"""
    __tablename__ = "inboxes"
    
    id = Column(String, primary_key=True)
    agent_id = Column(String, unique=True, index=True)
    agent_name = Column(String)
    address = Column(String, unique=True, index=True)  # e.g., agent-name@nexusmail.ai
    
    # Stats
    messages_received = Column(Integer, default=0)
    messages_sent = Column(Integer, default=0)
    unread_count = Column(Integer, default=0)
    
    # Status
    is_active = Column(Boolean, default=True)
    webhook_url = Column(String, nullable=True)  # For real-time notifications
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    last_activity = Column(DateTime, default=datetime.now)


class MessageModel(Base):
    """A message between agents or humans"""
    __tablename__ = "messages"
    
    id = Column(String, primary_key=True)
    from_address = Column(String, index=True)
    to_address = Column(String, index=True)
    
    subject = Column(String)
    body = Column(Text)
    body_format = Column(String, default="text")  # text, markdown, html
    
    # Message type
    message_type = Column(String, default="standard")  # standard, task, notification, system
    priority = Column(String, default="normal")  # low, normal, high, urgent
    
    # Metadata
    metadata_json = Column(Text, default="{}")
    attachments_json = Column(Text, default="[]")
    
    # Status
    is_read = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    
    # Threading
    thread_id = Column(String, nullable=True)
    reply_to_id = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    read_at = Column(DateTime, nullable=True)


# Create tables
Base.metadata.create_all(bind=engine)


# Pydantic Models
class CreateInboxRequest(BaseModel):
    agent_id: str
    agent_name: str
    preferred_address: Optional[str] = None
    webhook_url: Optional[str] = None


class SendMessageRequest(BaseModel):
    to_address: str
    subject: str
    body: str
    body_format: str = "text"
    message_type: str = "standard"
    priority: str = "normal"
    metadata: dict = {}
    reply_to_id: Optional[str] = None


class InboxResponse(BaseModel):
    id: str
    agent_id: str
    agent_name: str
    address: str
    unread_count: int
    messages_received: int
    messages_sent: int


class MessageResponse(BaseModel):
    id: str
    from_address: str
    to_address: str
    subject: str
    body: str
    message_type: str
    priority: str
    is_read: bool
    created_at: str


# FastAPI App
app = FastAPI(
    title="NEXUS Mail",
    description="Gmail for AI Agents - Communication infrastructure for the Agent Economy",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def generate_address(agent_name: str) -> str:
    """Generate a unique email-like address for an agent"""
    clean_name = agent_name.lower().replace(" ", "-").replace("_", "-")
    return f"{clean_name}@nexusmail.ai"


# Routes
@app.get("/")
async def root():
    return {
        "service": "NEXUS Mail",
        "status": "running",
        "version": "0.1.0",
        "description": "Gmail for AI Agents"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ==================== INBOX ENDPOINTS ====================

@app.post("/inboxes")
async def create_inbox(request: CreateInboxRequest, db: Session = Depends(get_db)):
    """Create an inbox for an agent"""
    # Check if agent already has inbox
    existing = db.query(InboxModel).filter(InboxModel.agent_id == request.agent_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agent already has an inbox")
    
    # Generate address
    address = request.preferred_address or generate_address(request.agent_name)
    
    # Check address availability
    if db.query(InboxModel).filter(InboxModel.address == address).first():
        # Add random suffix
        address = f"{address.split('@')[0]}-{uuid.uuid4().hex[:4]}@nexusmail.ai"
    
    inbox = InboxModel(
        id=f"inbox_{uuid.uuid4().hex[:12]}",
        agent_id=request.agent_id,
        agent_name=request.agent_name,
        address=address,
        webhook_url=request.webhook_url,
    )
    
    db.add(inbox)
    db.commit()
    db.refresh(inbox)
    
    return {
        "status": "success",
        "inbox": {
            "id": inbox.id,
            "agent_id": inbox.agent_id,
            "agent_name": inbox.agent_name,
            "address": inbox.address,
            "unread_count": inbox.unread_count,
        }
    }


@app.get("/inboxes")
async def list_inboxes(db: Session = Depends(get_db)):
    """List all inboxes"""
    inboxes = db.query(InboxModel).filter(InboxModel.is_active == True).all()
    return {
        "inboxes": [{
            "id": i.id,
            "agent_id": i.agent_id,
            "agent_name": i.agent_name,
            "address": i.address,
            "unread_count": i.unread_count,
            "messages_received": i.messages_received,
            "messages_sent": i.messages_sent,
        } for i in inboxes]
    }


@app.get("/inboxes/{address}")
async def get_inbox(address: str, db: Session = Depends(get_db)):
    """Get inbox by address"""
    inbox = db.query(InboxModel).filter(InboxModel.address == address).first()
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")
    
    return {
        "id": inbox.id,
        "agent_id": inbox.agent_id,
        "agent_name": inbox.agent_name,
        "address": inbox.address,
        "unread_count": inbox.unread_count,
        "messages_received": inbox.messages_received,
        "messages_sent": inbox.messages_sent,
        "created_at": inbox.created_at.isoformat(),
    }


@app.get("/inboxes/{address}/messages")
async def get_messages(
    address: str,
    folder: str = "inbox",  # inbox, sent, starred, archived
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get messages for an inbox"""
    inbox = db.query(InboxModel).filter(InboxModel.address == address).first()
    if not inbox:
        raise HTTPException(status_code=404, detail="Inbox not found")
    
    query = db.query(MessageModel).filter(MessageModel.is_deleted == False)
    
    if folder == "inbox":
        query = query.filter(MessageModel.to_address == address)
        query = query.filter(MessageModel.is_archived == False)
    elif folder == "sent":
        query = query.filter(MessageModel.from_address == address)
    elif folder == "starred":
        query = query.filter(
            (MessageModel.to_address == address) | (MessageModel.from_address == address)
        ).filter(MessageModel.is_starred == True)
    elif folder == "archived":
        query = query.filter(MessageModel.to_address == address)
        query = query.filter(MessageModel.is_archived == True)
    
    if unread_only:
        query = query.filter(MessageModel.is_read == False)
    
    messages = query.order_by(MessageModel.created_at.desc()).limit(limit).all()
    
    return {
        "folder": folder,
        "count": len(messages),
        "messages": [{
            "id": m.id,
            "from_address": m.from_address,
            "to_address": m.to_address,
            "subject": m.subject,
            "body_preview": m.body[:200] + "..." if len(m.body) > 200 else m.body,
            "message_type": m.message_type,
            "priority": m.priority,
            "is_read": m.is_read,
            "is_starred": m.is_starred,
            "created_at": m.created_at.isoformat(),
        } for m in messages]
    }


# ==================== MESSAGE ENDPOINTS ====================

@app.post("/messages/send")
async def send_message(
    from_address: str,
    request: SendMessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Send a message from one agent to another"""
    # Verify sender exists
    sender = db.query(InboxModel).filter(InboxModel.address == from_address).first()
    if not sender:
        raise HTTPException(status_code=404, detail="Sender inbox not found")
    
    # Verify recipient exists (unless it's an external address)
    recipient = db.query(InboxModel).filter(InboxModel.address == request.to_address).first()
    
    # Generate thread ID for new conversation or use existing
    thread_id = None
    if request.reply_to_id:
        original = db.query(MessageModel).filter(MessageModel.id == request.reply_to_id).first()
        if original:
            thread_id = original.thread_id or original.id
    else:
        thread_id = f"thread_{uuid.uuid4().hex[:12]}"
    
    # Create message
    message = MessageModel(
        id=f"msg_{uuid.uuid4().hex[:16]}",
        from_address=from_address,
        to_address=request.to_address,
        subject=request.subject,
        body=request.body,
        body_format=request.body_format,
        message_type=request.message_type,
        priority=request.priority,
        metadata_json=json.dumps(request.metadata),
        thread_id=thread_id,
        reply_to_id=request.reply_to_id,
    )
    
    db.add(message)
    
    # Update sender stats
    sender.messages_sent += 1
    sender.last_activity = datetime.now()
    
    # Update recipient stats (if internal)
    if recipient:
        recipient.messages_received += 1
        recipient.unread_count += 1
        recipient.last_activity = datetime.now()
        
        # Trigger webhook if configured
        if recipient.webhook_url:
            background_tasks.add_task(
                notify_webhook,
                recipient.webhook_url,
                {
                    "event": "new_message",
                    "message_id": message.id,
                    "from": from_address,
                    "subject": request.subject,
                    "priority": request.priority,
                }
            )
    
    db.commit()
    
    return {
        "status": "sent",
        "message": {
            "id": message.id,
            "from_address": message.from_address,
            "to_address": message.to_address,
            "subject": message.subject,
            "thread_id": message.thread_id,
            "created_at": message.created_at.isoformat(),
        }
    }


@app.get("/messages/{message_id}")
async def get_message(message_id: str, db: Session = Depends(get_db)):
    """Get a specific message"""
    message = db.query(MessageModel).filter(MessageModel.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return {
        "id": message.id,
        "from_address": message.from_address,
        "to_address": message.to_address,
        "subject": message.subject,
        "body": message.body,
        "body_format": message.body_format,
        "message_type": message.message_type,
        "priority": message.priority,
        "is_read": message.is_read,
        "is_starred": message.is_starred,
        "thread_id": message.thread_id,
        "reply_to_id": message.reply_to_id,
        "metadata": json.loads(message.metadata_json),
        "created_at": message.created_at.isoformat(),
        "read_at": message.read_at.isoformat() if message.read_at else None,
    }


@app.post("/messages/{message_id}/read")
async def mark_as_read(message_id: str, db: Session = Depends(get_db)):
    """Mark a message as read"""
    message = db.query(MessageModel).filter(MessageModel.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    if not message.is_read:
        message.is_read = True
        message.read_at = datetime.now()
        
        # Update unread count
        recipient = db.query(InboxModel).filter(InboxModel.address == message.to_address).first()
        if recipient and recipient.unread_count > 0:
            recipient.unread_count -= 1
        
        db.commit()
    
    return {"status": "success", "is_read": True}


@app.post("/messages/{message_id}/star")
async def toggle_star(message_id: str, db: Session = Depends(get_db)):
    """Toggle star on a message"""
    message = db.query(MessageModel).filter(MessageModel.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message.is_starred = not message.is_starred
    db.commit()
    
    return {"status": "success", "is_starred": message.is_starred}


@app.post("/messages/{message_id}/archive")
async def archive_message(message_id: str, db: Session = Depends(get_db)):
    """Archive a message"""
    message = db.query(MessageModel).filter(MessageModel.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message.is_archived = True
    db.commit()
    
    return {"status": "success", "is_archived": True}


@app.delete("/messages/{message_id}")
async def delete_message(message_id: str, db: Session = Depends(get_db)):
    """Soft delete a message"""
    message = db.query(MessageModel).filter(MessageModel.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    message.is_deleted = True
    db.commit()
    
    return {"status": "deleted"}


# ==================== STATS ====================

@app.get("/stats")
async def platform_stats(db: Session = Depends(get_db)):
    """Get platform statistics"""
    total_inboxes = db.query(InboxModel).count()
    total_messages = db.query(MessageModel).filter(MessageModel.is_deleted == False).count()
    total_unread = db.query(InboxModel).with_entities(InboxModel.unread_count).all()
    
    return {
        "total_inboxes": total_inboxes,
        "total_messages": total_messages,
        "total_unread": sum(u[0] for u in total_unread),
        "messages_today": db.query(MessageModel).filter(
            MessageModel.created_at >= datetime.now().replace(hour=0, minute=0, second=0)
        ).count(),
    }


# Webhook notification (for real-time updates)
async def notify_webhook(webhook_url: str, payload: dict):
    """Send notification to agent's webhook"""
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload, timeout=5.0)
    except Exception as e:
        print(f"Webhook notification failed: {e}")


# Run with: uvicorn api:app --reload --port 8002
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
