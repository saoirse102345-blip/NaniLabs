"""
AURA Infra - Webhook System
Send notifications to registered webhook URLs when events occur
"""

import asyncio
import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
import httpx

# Webhook event types
class WebhookEvent:
    WALLET_CREATED = "wallet.created"
    WALLET_UPDATED = "wallet.updated"
    DEPOSIT_COMPLETED = "deposit.completed"
    WITHDRAWAL_COMPLETED = "withdrawal.completed"
    TRANSFER_COMPLETED = "transfer.completed"
    TRANSFER_RECEIVED = "transfer.received"
    LOW_BALANCE = "wallet.low_balance"
    AGENT_REGISTERED = "agent.registered"


class WebhookPayload:
    """Standardized webhook payload"""
    
    def __init__(
        self,
        event_type: str,
        data: Dict[str, Any],
        agent_id: Optional[str] = None,
        wallet_id: Optional[str] = None
    ):
        self.id = f"evt_{hashlib.md5(str(time.time()).encode()).hexdigest()[:16]}"
        self.type = event_type
        self.created = datetime.utcnow().isoformat() + "Z"
        self.data = data
        self.agent_id = agent_id
        self.wallet_id = wallet_id
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "created": self.created,
            "data": self.data,
            "agent_id": self.agent_id,
            "wallet_id": self.wallet_id
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


def generate_signature(payload: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for webhook payload"""
    return hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()


async def send_webhook(
    url: str,
    payload: WebhookPayload,
    secret: Optional[str] = None,
    timeout: float = 10.0,
    retries: int = 3
) -> Dict[str, Any]:
    """
    Send webhook to URL with retries
    
    Args:
        url: Webhook endpoint URL
        payload: WebhookPayload object
        secret: Optional secret for signing
        timeout: Request timeout in seconds
        retries: Number of retry attempts
    
    Returns:
        Dict with success status and response info
    """
    payload_json = payload.to_json()
    
    headers = {
        "Content-Type": "application/json",
        "X-AURA-Event": payload.type,
        "X-AURA-Delivery": payload.id,
        "X-AURA-Timestamp": str(int(time.time()))
    }
    
    if secret:
        timestamp = headers["X-AURA-Timestamp"]
        signature_payload = f"{timestamp}.{payload_json}"
        signature = generate_signature(signature_payload, secret)
        headers["X-AURA-Signature"] = f"sha256={signature}"
    
    async with httpx.AsyncClient() as client:
        last_error = None
        
        for attempt in range(retries):
            try:
                response = await client.post(
                    url,
                    content=payload_json,
                    headers=headers,
                    timeout=timeout
                )
                
                return {
                    "success": response.status_code < 400,
                    "status_code": response.status_code,
                    "response": response.text[:500] if response.text else None,
                    "attempts": attempt + 1
                }
                
            except Exception as e:
                last_error = str(e)
                if attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return {
            "success": False,
            "error": last_error,
            "attempts": retries
        }


class WebhookManager:
    """
    Manage webhook subscriptions and deliveries
    """
    
    def __init__(self):
        # In-memory store for demo. In production, use database
        self.subscriptions: Dict[str, List[Dict[str, Any]]] = {}
        self.delivery_log: List[Dict[str, Any]] = []
    
    def subscribe(
        self,
        agent_id: str,
        url: str,
        events: List[str],
        secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """Subscribe to webhook events"""
        subscription = {
            "id": f"whsub_{hashlib.md5(f'{agent_id}{url}'.encode()).hexdigest()[:12]}",
            "agent_id": agent_id,
            "url": url,
            "events": events,
            "secret": secret,
            "active": True,
            "created_at": datetime.utcnow().isoformat()
        }
        
        if agent_id not in self.subscriptions:
            self.subscriptions[agent_id] = []
        
        self.subscriptions[agent_id].append(subscription)
        
        return subscription
    
    def unsubscribe(self, agent_id: str, subscription_id: str) -> bool:
        """Remove a webhook subscription"""
        if agent_id not in self.subscriptions:
            return False
        
        for i, sub in enumerate(self.subscriptions[agent_id]):
            if sub["id"] == subscription_id:
                del self.subscriptions[agent_id][i]
                return True
        
        return False
    
    def get_subscriptions(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get all subscriptions for an agent"""
        return self.subscriptions.get(agent_id, [])
    
    async def dispatch(
        self,
        event_type: str,
        data: Dict[str, Any],
        agent_id: Optional[str] = None,
        wallet_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Dispatch webhook to all matching subscriptions
        
        Args:
            event_type: Type of event (e.g., "transfer.completed")
            data: Event data
            agent_id: Agent to notify (if specific)
            wallet_id: Related wallet ID
        
        Returns:
            List of delivery results
        """
        payload = WebhookPayload(event_type, data, agent_id, wallet_id)
        results = []
        
        # Find matching subscriptions
        agents_to_notify = [agent_id] if agent_id else list(self.subscriptions.keys())
        
        for aid in agents_to_notify:
            for sub in self.subscriptions.get(aid, []):
                if not sub["active"]:
                    continue
                
                # Check if subscription includes this event type
                if "*" not in sub["events"] and event_type not in sub["events"]:
                    continue
                
                # Send webhook
                result = await send_webhook(
                    sub["url"],
                    payload,
                    sub.get("secret")
                )
                
                delivery = {
                    "subscription_id": sub["id"],
                    "event_id": payload.id,
                    "event_type": event_type,
                    "url": sub["url"],
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                self.delivery_log.append(delivery)
                results.append(delivery)
        
        return results
    
    def get_delivery_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent webhook deliveries"""
        return self.delivery_log[-limit:]


# Global webhook manager instance
webhook_manager = WebhookManager()


# Convenience functions for triggering webhooks
async def trigger_wallet_created(wallet_data: Dict[str, Any]):
    """Trigger webhook when wallet is created"""
    await webhook_manager.dispatch(
        WebhookEvent.WALLET_CREATED,
        wallet_data,
        agent_id=wallet_data.get("agent_id"),
        wallet_id=wallet_data.get("id")
    )


async def trigger_deposit(transaction_data: Dict[str, Any], new_balance: float):
    """Trigger webhook when deposit is completed"""
    await webhook_manager.dispatch(
        WebhookEvent.DEPOSIT_COMPLETED,
        {
            "transaction": transaction_data,
            "new_balance": new_balance
        },
        wallet_id=transaction_data.get("wallet_id")
    )


async def trigger_transfer(
    transaction_data: Dict[str, Any],
    from_agent_id: str,
    to_agent_id: str,
    fee: float,
    from_balance: float,
    to_balance: float
):
    """Trigger webhooks for transfer (both sender and receiver)"""
    # Notify sender
    await webhook_manager.dispatch(
        WebhookEvent.TRANSFER_COMPLETED,
        {
            "transaction": transaction_data,
            "fee": fee,
            "new_balance": from_balance
        },
        agent_id=from_agent_id,
        wallet_id=transaction_data.get("from_wallet_id")
    )
    
    # Notify receiver
    await webhook_manager.dispatch(
        WebhookEvent.TRANSFER_RECEIVED,
        {
            "transaction": transaction_data,
            "amount_received": transaction_data.get("amount"),
            "new_balance": to_balance
        },
        agent_id=to_agent_id,
        wallet_id=transaction_data.get("to_wallet_id")
    )
