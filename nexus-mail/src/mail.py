"""
NEXUS Mail - Communication Infrastructure for AI Agents
"Gmail for AI Agents"

Every AI agent gets an addressable inbox.
Enable human-to-agent and agent-to-agent communication.
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import re


class MessagePriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageStatus(Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MessageType(Enum):
    TEXT = "text"
    TASK = "task"
    RESULT = "result"
    NOTIFICATION = "notification"
    SYSTEM = "system"


@dataclass
class Attachment:
    """Email attachment"""
    id: str
    filename: str
    content_type: str
    size_bytes: int
    url: str


@dataclass
class Message:
    """An email message"""
    id: str
    from_address: str
    to_address: str
    subject: str
    body: str
    message_type: MessageType = MessageType.TEXT
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.SENT
    created_at: datetime = field(default_factory=datetime.now)
    read_at: Optional[datetime] = None
    
    # Threading
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    
    # Attachments
    attachments: List[Attachment] = field(default_factory=list)
    
    # For tasks
    task_type: Optional[str] = None
    task_payload: Optional[Dict] = None
    task_deadline: Optional[datetime] = None
    task_budget: Optional[float] = None
    
    # Response
    response: Optional[str] = None
    response_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "from": self.from_address,
            "to": self.to_address,
            "subject": self.subject,
            "body": self.body[:500] + "..." if len(self.body) > 500 else self.body,
            "type": self.message_type.value,
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "thread_id": self.thread_id,
            "has_attachments": len(self.attachments) > 0,
            "task_type": self.task_type,
            "task_budget": self.task_budget,
        }


@dataclass
class Inbox:
    """An agent's inbox"""
    id: str
    address: str  # e.g., "agent-name@nexus.ai"
    owner_id: str
    owner_name: str
    created_at: datetime = field(default_factory=datetime.now)
    
    # Messages
    messages: List[str] = field(default_factory=list)  # Message IDs
    
    # Settings
    auto_reply: bool = False
    auto_reply_message: str = ""
    filters: List[Dict] = field(default_factory=list)
    
    # Stats
    total_received: int = 0
    total_sent: int = 0
    unread_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "address": self.address,
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "total_received": self.total_received,
            "total_sent": self.total_sent,
            "unread_count": self.unread_count,
            "created_at": self.created_at.isoformat(),
        }


class NexusMailService:
    """
    NEXUS Mail Service.
    The communication backbone for AI agents.
    """
    
    DOMAIN = "nexus.ai"
    
    def __init__(self):
        self.inboxes: Dict[str, Inbox] = {}
        self.messages: Dict[str, Message] = {}
        self.address_to_inbox: Dict[str, str] = {}  # address -> inbox_id
        
        # Message queue for async processing
        self.message_queue: List[str] = []
        
        print(f"📧 NEXUS Mail Service initialized (@{self.DOMAIN})")
    
    def _generate_address(self, name: str) -> str:
        """Generate email address for an agent"""
        # Clean name for email
        clean_name = re.sub(r'[^a-zA-Z0-9]', '-', name.lower())
        clean_name = re.sub(r'-+', '-', clean_name).strip('-')
        
        base_address = f"{clean_name}@{self.DOMAIN}"
        
        # Handle duplicates
        if base_address in self.address_to_inbox:
            suffix = uuid.uuid4().hex[:4]
            base_address = f"{clean_name}-{suffix}@{self.DOMAIN}"
        
        return base_address
    
    async def create_inbox(
        self,
        owner_id: str,
        owner_name: str,
        custom_address: str = None
    ) -> Inbox:
        """Create a new inbox for an agent"""
        address = custom_address or self._generate_address(owner_name)
        
        inbox = Inbox(
            id=f"inbox_{uuid.uuid4().hex[:12]}",
            address=address,
            owner_id=owner_id,
            owner_name=owner_name
        )
        
        self.inboxes[inbox.id] = inbox
        self.address_to_inbox[address] = inbox.id
        
        print(f"📬 Created inbox: {address}")
        
        return inbox
    
    async def send_message(
        self,
        from_address: str,
        to_address: str,
        subject: str,
        body: str,
        message_type: MessageType = MessageType.TEXT,
        priority: MessagePriority = MessagePriority.NORMAL,
        task_type: str = None,
        task_payload: Dict = None,
        task_budget: float = None,
        in_reply_to: str = None
    ) -> Message:
        """Send a message"""
        # Validate addresses
        if from_address not in self.address_to_inbox:
            raise ValueError(f"Sender address not found: {from_address}")
        if to_address not in self.address_to_inbox:
            raise ValueError(f"Recipient address not found: {to_address}")
        
        # Get inboxes
        from_inbox_id = self.address_to_inbox[from_address]
        to_inbox_id = self.address_to_inbox[to_address]
        from_inbox = self.inboxes[from_inbox_id]
        to_inbox = self.inboxes[to_inbox_id]
        
        # Create message
        message = Message(
            id=f"msg_{uuid.uuid4().hex[:16]}",
            from_address=from_address,
            to_address=to_address,
            subject=subject,
            body=body,
            message_type=message_type,
            priority=priority,
            task_type=task_type,
            task_payload=task_payload,
            task_budget=task_budget,
            in_reply_to=in_reply_to
        )
        
        # Handle threading
        if in_reply_to:
            parent = self.messages.get(in_reply_to)
            if parent:
                message.thread_id = parent.thread_id or parent.id
        else:
            message.thread_id = message.id
        
        # Store and update stats
        self.messages[message.id] = message
        from_inbox.total_sent += 1
        to_inbox.total_received += 1
        to_inbox.unread_count += 1
        to_inbox.messages.append(message.id)
        
        message.status = MessageStatus.DELIVERED
        
        print(f"✉️  {from_address} → {to_address}: {subject}")
        
        # Add to queue for processing
        self.message_queue.append(message.id)
        
        return message
    
    async def send_task(
        self,
        from_address: str,
        to_address: str,
        task_type: str,
        task_description: str,
        task_payload: Dict = None,
        budget: float = None,
        deadline: datetime = None
    ) -> Message:
        """Send a task to an agent"""
        return await self.send_message(
            from_address=from_address,
            to_address=to_address,
            subject=f"[TASK] {task_type}: {task_description[:50]}",
            body=task_description,
            message_type=MessageType.TASK,
            priority=MessagePriority.HIGH,
            task_type=task_type,
            task_payload=task_payload,
            task_budget=budget
        )
    
    async def mark_read(self, message_id: str):
        """Mark a message as read"""
        message = self.messages.get(message_id)
        if message:
            message.status = MessageStatus.READ
            message.read_at = datetime.now()
            
            to_inbox_id = self.address_to_inbox.get(message.to_address)
            if to_inbox_id:
                inbox = self.inboxes[to_inbox_id]
                if inbox.unread_count > 0:
                    inbox.unread_count -= 1
    
    async def reply(
        self,
        original_message_id: str,
        reply_body: str,
        message_type: MessageType = MessageType.TEXT
    ) -> Message:
        """Reply to a message"""
        original = self.messages.get(original_message_id)
        if not original:
            raise ValueError("Original message not found")
        
        return await self.send_message(
            from_address=original.to_address,
            to_address=original.from_address,
            subject=f"Re: {original.subject}",
            body=reply_body,
            message_type=message_type,
            in_reply_to=original_message_id
        )
    
    async def complete_task(
        self,
        task_message_id: str,
        result: str,
        result_data: Dict = None
    ) -> Message:
        """Complete a task and send results"""
        task = self.messages.get(task_message_id)
        if not task:
            raise ValueError("Task not found")
        
        task.status = MessageStatus.COMPLETED
        task.response = result
        task.response_at = datetime.now()
        
        # Send result message
        return await self.send_message(
            from_address=task.to_address,
            to_address=task.from_address,
            subject=f"[RESULT] {task.subject}",
            body=result,
            message_type=MessageType.RESULT,
            task_payload=result_data,
            in_reply_to=task_message_id
        )
    
    def get_inbox(self, address: str) -> Optional[Inbox]:
        """Get inbox by address"""
        inbox_id = self.address_to_inbox.get(address)
        if inbox_id:
            return self.inboxes[inbox_id]
        return None
    
    def get_messages(
        self,
        address: str,
        unread_only: bool = False,
        message_type: MessageType = None,
        limit: int = 50
    ) -> List[Message]:
        """Get messages for an inbox"""
        inbox = self.get_inbox(address)
        if not inbox:
            return []
        
        messages = []
        for msg_id in reversed(inbox.messages):
            msg = self.messages.get(msg_id)
            if not msg:
                continue
            
            if unread_only and msg.status != MessageStatus.DELIVERED:
                continue
            
            if message_type and msg.message_type != message_type:
                continue
            
            messages.append(msg)
            
            if len(messages) >= limit:
                break
        
        return messages
    
    def get_thread(self, thread_id: str) -> List[Message]:
        """Get all messages in a thread"""
        return sorted(
            [m for m in self.messages.values() if m.thread_id == thread_id],
            key=lambda m: m.created_at
        )
    
    def get_stats(self) -> Dict:
        """Service statistics"""
        return {
            "total_inboxes": len(self.inboxes),
            "total_messages": len(self.messages),
            "messages_in_queue": len(self.message_queue),
            "total_tasks": len([m for m in self.messages.values() if m.message_type == MessageType.TASK]),
            "completed_tasks": len([m for m in self.messages.values() if m.status == MessageStatus.COMPLETED]),
        }


async def demo():
    """Demo the NEXUS Mail system"""
    print("\n" + "="*60)
    print("📧 NEXUS Mail - Agent Communication Demo")
    print("="*60 + "\n")
    
    # Initialize service
    mail = NexusMailService()
    
    # Create inboxes for agents
    content_inbox = await mail.create_inbox("agent_001", "ContentBot")
    trading_inbox = await mail.create_inbox("agent_002", "TradingBot")
    research_inbox = await mail.create_inbox("agent_003", "ResearchBot")
    human_inbox = await mail.create_inbox("human_001", "Nived")
    
    # Human sends a task to an agent
    task1 = await mail.send_task(
        from_address=human_inbox.address,
        to_address=research_inbox.address,
        task_type="research",
        task_description="Research the top 10 AI agent startups that raised funding in 2026. Include funding amounts, investors, and what they're building.",
        task_payload={"format": "markdown", "max_length": 2000},
        budget=25.00
    )
    
    # Agent-to-agent communication
    await mail.send_message(
        from_address=content_inbox.address,
        to_address=trading_inbox.address,
        subject="Collaboration Request: Market Analysis Content",
        body="Hey TradingBot! I'm creating a weekly market analysis newsletter. Would you be interested in providing technical analysis insights? I can pay $10 per analysis.",
        priority=MessagePriority.NORMAL
    )
    
    # Trading bot replies
    await mail.reply(
        (await mail.get_messages(trading_inbox.address))[0].id,
        "Sounds interesting! I can provide daily technical analysis for BTC, ETH, and top altcoins. Let's discuss the details."
    )
    
    # Research bot completes the task
    await mail.complete_task(
        task1.id,
        """# Top 10 AI Agent Startups (2026)

## 1. Twin ($10M Seed)
- Investors: LocalGlobe
- Focus: No-code AI agent builder

## 2. AgentMail ($5M Seed)  
- Investors: Y Combinator
- Focus: Email infrastructure for AI agents

... [continued]""",
        {"sources": ["crunchbase", "twitter", "techcrunch"]}
    )
    
    # Print results
    print("\n" + "="*60)
    print("📊 SERVICE STATS")
    print("="*60)
    print(mail.get_stats())
    
    print("\n" + "="*60)
    print(f"📬 INBOX: {research_inbox.address}")
    print("="*60)
    for msg in mail.get_messages(research_inbox.address, limit=5):
        print(f"\n{'🔴' if msg.status == MessageStatus.DELIVERED else '✅'} {msg.subject}")
        print(f"   From: {msg.from_address}")
        print(f"   Type: {msg.message_type.value}")
        if msg.task_budget:
            print(f"   Budget: ${msg.task_budget}")


if __name__ == "__main__":
    asyncio.run(demo())
