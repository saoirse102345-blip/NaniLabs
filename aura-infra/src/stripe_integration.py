"""
AURA Infra - Stripe Integration
Connect real payments to agent wallets

This module handles:
- Stripe Connect for agent payouts
- Payment intents for deposits
- Webhook handling for payment events
"""

import os
import hmac
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Stripe SDK (install with: pip install stripe)
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    print("Warning: stripe package not installed. Run: pip install stripe")


# Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CONNECT_CLIENT_ID = os.getenv("STRIPE_CONNECT_CLIENT_ID", "")

# Platform fee percentage (our cut)
PLATFORM_FEE_PERCENT = 0.029  # 2.9%

if STRIPE_AVAILABLE and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


@dataclass
class StripeAccount:
    """Represents a Stripe Connect account for an agent"""
    agent_id: str
    stripe_account_id: str
    email: Optional[str]
    payouts_enabled: bool
    charges_enabled: bool
    created_at: datetime


class StripeIntegration:
    """
    Handle Stripe payments for AURA Infra
    """
    
    def __init__(self):
        self.enabled = STRIPE_AVAILABLE and bool(STRIPE_SECRET_KEY)
        if not self.enabled:
            print("Stripe integration disabled (no API key)")
    
    def create_connect_account(
        self,
        agent_id: str,
        email: str,
        country: str = "US"
    ) -> Dict[str, Any]:
        """
        Create a Stripe Connect Express account for an agent.
        This allows agents to receive payouts.
        """
        if not self.enabled:
            return {"error": "Stripe not configured"}
        
        try:
            account = stripe.Account.create(
                type="express",
                country=country,
                email=email,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                metadata={
                    "agent_id": agent_id,
                    "platform": "aura_infra"
                }
            )
            
            return {
                "success": True,
                "stripe_account_id": account.id,
                "email": email,
                "country": country
            }
            
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    def create_account_link(
        self,
        stripe_account_id: str,
        return_url: str,
        refresh_url: str
    ) -> Dict[str, Any]:
        """
        Create an onboarding link for a Connect account.
        Agent visits this URL to complete Stripe onboarding.
        """
        if not self.enabled:
            return {"error": "Stripe not configured"}
        
        try:
            link = stripe.AccountLink.create(
                account=stripe_account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding"
            )
            
            return {
                "success": True,
                "url": link.url,
                "expires_at": link.expires_at
            }
            
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    def get_account_status(self, stripe_account_id: str) -> Dict[str, Any]:
        """Get the status of a Connect account"""
        if not self.enabled:
            return {"error": "Stripe not configured"}
        
        try:
            account = stripe.Account.retrieve(stripe_account_id)
            
            return {
                "success": True,
                "stripe_account_id": account.id,
                "payouts_enabled": account.payouts_enabled,
                "charges_enabled": account.charges_enabled,
                "details_submitted": account.details_submitted,
                "email": account.email
            }
            
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    def create_payment_intent(
        self,
        amount_usd: float,
        wallet_id: str,
        description: str = "Deposit to AURA wallet"
    ) -> Dict[str, Any]:
        """
        Create a payment intent for depositing funds to a wallet.
        Amount is in USD, converted to cents for Stripe.
        """
        if not self.enabled:
            return {"error": "Stripe not configured"}
        
        amount_cents = int(amount_usd * 100)
        
        try:
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="usd",
                description=description,
                metadata={
                    "wallet_id": wallet_id,
                    "platform": "aura_infra",
                    "type": "deposit"
                }
            )
            
            return {
                "success": True,
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount_usd": amount_usd
            }
            
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    def create_transfer_to_agent(
        self,
        amount_usd: float,
        stripe_account_id: str,
        description: str = "Payout from AURA wallet"
    ) -> Dict[str, Any]:
        """
        Transfer funds to an agent's connected Stripe account.
        This is for withdrawals/payouts.
        """
        if not self.enabled:
            return {"error": "Stripe not configured"}
        
        amount_cents = int(amount_usd * 100)
        
        try:
            transfer = stripe.Transfer.create(
                amount=amount_cents,
                currency="usd",
                destination=stripe_account_id,
                description=description
            )
            
            return {
                "success": True,
                "transfer_id": transfer.id,
                "amount_usd": amount_usd
            }
            
        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}
    
    def verify_webhook_signature(
        self,
        payload: bytes,
        sig_header: str
    ) -> bool:
        """Verify Stripe webhook signature"""
        if not STRIPE_WEBHOOK_SECRET:
            return False
        
        try:
            stripe.Webhook.construct_event(
                payload, sig_header, STRIPE_WEBHOOK_SECRET
            )
            return True
        except (ValueError, stripe.error.SignatureVerificationError):
            return False
    
    def handle_webhook_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming Stripe webhook events.
        Returns action to take in AURA system.
        """
        event_type = event.get("type", "")
        data = event.get("data", {}).get("object", {})
        
        handlers = {
            "payment_intent.succeeded": self._handle_payment_succeeded,
            "payment_intent.payment_failed": self._handle_payment_failed,
            "account.updated": self._handle_account_updated,
            "transfer.created": self._handle_transfer_created,
            "payout.paid": self._handle_payout_paid,
            "payout.failed": self._handle_payout_failed,
        }
        
        handler = handlers.get(event_type)
        if handler:
            return handler(data)
        
        return {"action": "ignore", "event_type": event_type}
    
    def _handle_payment_succeeded(self, data: Dict) -> Dict[str, Any]:
        """Handle successful payment - credit agent wallet"""
        wallet_id = data.get("metadata", {}).get("wallet_id")
        amount_cents = data.get("amount", 0)
        amount_usd = amount_cents / 100
        
        return {
            "action": "deposit",
            "wallet_id": wallet_id,
            "amount_usd": amount_usd,
            "payment_intent_id": data.get("id"),
            "source": "stripe_deposit"
        }
    
    def _handle_payment_failed(self, data: Dict) -> Dict[str, Any]:
        """Handle failed payment"""
        return {
            "action": "notify_failure",
            "payment_intent_id": data.get("id"),
            "error": data.get("last_payment_error", {}).get("message", "Payment failed")
        }
    
    def _handle_account_updated(self, data: Dict) -> Dict[str, Any]:
        """Handle Connect account updates"""
        return {
            "action": "update_account",
            "stripe_account_id": data.get("id"),
            "payouts_enabled": data.get("payouts_enabled"),
            "charges_enabled": data.get("charges_enabled")
        }
    
    def _handle_transfer_created(self, data: Dict) -> Dict[str, Any]:
        """Handle transfer to connected account"""
        return {
            "action": "log_transfer",
            "transfer_id": data.get("id"),
            "amount_cents": data.get("amount"),
            "destination": data.get("destination")
        }
    
    def _handle_payout_paid(self, data: Dict) -> Dict[str, Any]:
        """Handle successful payout to agent bank"""
        return {
            "action": "payout_complete",
            "payout_id": data.get("id"),
            "amount_cents": data.get("amount")
        }
    
    def _handle_payout_failed(self, data: Dict) -> Dict[str, Any]:
        """Handle failed payout"""
        return {
            "action": "payout_failed",
            "payout_id": data.get("id"),
            "error": data.get("failure_message", "Payout failed")
        }


# Global instance
stripe_integration = StripeIntegration()


# FastAPI router for Stripe webhooks
def create_stripe_router():
    """Create FastAPI router for Stripe webhook endpoints"""
    from fastapi import APIRouter, Request, HTTPException
    
    router = APIRouter(prefix="/stripe", tags=["Stripe"])
    
    @router.post("/webhook")
    async def stripe_webhook(request: Request):
        """Handle incoming Stripe webhooks"""
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature", "")
        
        if not stripe_integration.verify_webhook_signature(payload, sig_header):
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        import json
        event = json.loads(payload)
        result = stripe_integration.handle_webhook_event(event)
        
        # TODO: Actually process the action (deposit, etc.)
        # This would integrate with the main AURA database
        
        return {"received": True, "action": result.get("action")}
    
    return router


# Example usage
if __name__ == "__main__":
    integration = StripeIntegration()
    print(f"Stripe enabled: {integration.enabled}")
    
    if integration.enabled:
        # Example: Create payment intent
        result = integration.create_payment_intent(
            amount_usd=100.00,
            wallet_id="wallet_test123",
            description="Test deposit"
        )
        print(f"Payment intent: {result}")
