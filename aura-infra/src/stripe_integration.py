"""
AURA Infra - Stripe Integration
Real payment processing for AI agents

Features:
- Deposit funds (humans pay to fund agent wallets)
- Withdraw funds (payout to bank accounts)
- Agent-to-agent transfers (internal, no Stripe fee)
- Subscription billing for premium features
"""

import os
import stripe
from datetime import datetime
from typing import Optional
import uuid

# Stripe Configuration - Set these as environment variables!
# In production: set STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

if not STRIPE_SECRET_KEY:
    print("[STRIPE] WARNING: STRIPE_SECRET_KEY not set. Payments will not work.")
if not STRIPE_PUBLISHABLE_KEY:
    print("[STRIPE] WARNING: STRIPE_PUBLISHABLE_KEY not set.")

# Platform fee (0.5% after free tier)
PLATFORM_FEE_PERCENT = 0.005
FREE_TIER_TRANSACTIONS = 10000

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY


class StripeService:
    """Service for handling Stripe operations"""
    
    @staticmethod
    def create_customer(agent_id: str, agent_name: str, email: Optional[str] = None) -> dict:
        """Create a Stripe customer for an agent"""
        try:
            customer = stripe.Customer.create(
                metadata={
                    "agent_id": agent_id,
                    "agent_name": agent_name,
                    "platform": "nanilabs_aura"
                },
                email=email,
                name=f"Agent: {agent_name}",
                description=f"AURA Agent Wallet - {agent_id}"
            )
            return {
                "success": True,
                "customer_id": customer.id,
                "customer": customer
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def create_checkout_session(
        agent_id: str,
        wallet_id: str,
        amount_usd: float,
        success_url: str,
        cancel_url: str,
        customer_id: Optional[str] = None
    ) -> dict:
        """
        Create a Stripe Checkout session for depositing funds.
        User pays, funds go to agent wallet.
        """
        try:
            # Amount in cents
            amount_cents = int(amount_usd * 100)
            
            session_params = {
                "payment_method_types": ["card"],
                "line_items": [{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"AURA Wallet Deposit",
                            "description": f"Add ${amount_usd:.2f} to agent wallet",
                        },
                        "unit_amount": amount_cents,
                    },
                    "quantity": 1,
                }],
                "mode": "payment",
                "success_url": success_url + "?session_id={CHECKOUT_SESSION_ID}",
                "cancel_url": cancel_url,
                "metadata": {
                    "agent_id": agent_id,
                    "wallet_id": wallet_id,
                    "amount_usd": str(amount_usd),
                    "type": "wallet_deposit"
                }
            }
            
            if customer_id:
                session_params["customer"] = customer_id
            
            session = stripe.checkout.Session.create(**session_params)
            
            return {
                "success": True,
                "session_id": session.id,
                "checkout_url": session.url,
                "amount_usd": amount_usd
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def create_payment_intent(
        amount_usd: float,
        agent_id: str,
        wallet_id: str,
        customer_id: Optional[str] = None
    ) -> dict:
        """
        Create a PaymentIntent for custom payment flows.
        Use this for embedded payment forms.
        """
        try:
            amount_cents = int(amount_usd * 100)
            
            intent_params = {
                "amount": amount_cents,
                "currency": "usd",
                "metadata": {
                    "agent_id": agent_id,
                    "wallet_id": wallet_id,
                    "type": "wallet_deposit"
                },
                "automatic_payment_methods": {
                    "enabled": True
                }
            }
            
            if customer_id:
                intent_params["customer"] = customer_id
            
            intent = stripe.PaymentIntent.create(**intent_params)
            
            return {
                "success": True,
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount_usd": amount_usd
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def retrieve_checkout_session(session_id: str) -> dict:
        """Retrieve a checkout session to verify payment"""
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            return {
                "success": True,
                "session": session,
                "payment_status": session.payment_status,
                "amount_total": session.amount_total / 100,  # Convert from cents
                "metadata": session.metadata
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def retrieve_payment_intent(payment_intent_id: str) -> dict:
        """Retrieve a payment intent to check status"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                "success": True,
                "intent": intent,
                "status": intent.status,
                "amount": intent.amount / 100,
                "metadata": intent.metadata
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def create_subscription(
        customer_id: str,
        price_id: str,
        agent_id: str
    ) -> dict:
        """Create a subscription for premium features"""
        try:
            subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                metadata={
                    "agent_id": agent_id,
                    "platform": "nanilabs_aura"
                }
            )
            return {
                "success": True,
                "subscription_id": subscription.id,
                "status": subscription.status,
                "subscription": subscription
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def cancel_subscription(subscription_id: str) -> dict:
        """Cancel a subscription"""
        try:
            subscription = stripe.Subscription.delete(subscription_id)
            return {
                "success": True,
                "subscription_id": subscription_id,
                "status": "canceled"
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def list_payment_methods(customer_id: str) -> dict:
        """List payment methods for a customer"""
        try:
            methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card"
            )
            return {
                "success": True,
                "payment_methods": [
                    {
                        "id": pm.id,
                        "brand": pm.card.brand,
                        "last4": pm.card.last4,
                        "exp_month": pm.card.exp_month,
                        "exp_year": pm.card.exp_year
                    }
                    for pm in methods.data
                ]
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_balance() -> dict:
        """Get Stripe account balance"""
        try:
            balance = stripe.Balance.retrieve()
            return {
                "success": True,
                "available": [
                    {"amount": b.amount / 100, "currency": b.currency}
                    for b in balance.available
                ],
                "pending": [
                    {"amount": b.amount / 100, "currency": b.currency}
                    for b in balance.pending
                ]
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ============== STRIPE CONNECT (Worker Payouts) ==============
    
    @staticmethod
    def create_connect_account(
        worker_id: str,
        email: str,
        country: str = "US"
    ) -> dict:
        """
        Create a Stripe Connect Express account for a worker.
        Workers need this to receive payouts from MEAT tasks.
        """
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
                    "worker_id": worker_id,
                    "platform": "nanilabs_meat"
                }
            )
            return {
                "success": True,
                "account_id": account.id,
                "account": account
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def create_connect_onboarding_link(
        account_id: str,
        return_url: str,
        refresh_url: str
    ) -> dict:
        """
        Create an onboarding link for a worker to complete their Stripe setup.
        They'll enter bank details, verify identity, etc.
        """
        try:
            link = stripe.AccountLink.create(
                account=account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding"
            )
            return {
                "success": True,
                "onboarding_url": link.url,
                "expires_at": link.expires_at
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_connect_account(account_id: str) -> dict:
        """Get details of a connected account"""
        try:
            account = stripe.Account.retrieve(account_id)
            return {
                "success": True,
                "account_id": account.id,
                "email": account.email,
                "payouts_enabled": account.payouts_enabled,
                "charges_enabled": account.charges_enabled,
                "details_submitted": account.details_submitted,
                "country": account.country
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def transfer_to_worker(
        account_id: str,
        amount_usd: float,
        task_id: str,
        description: str = "MEAT Task Payment"
    ) -> dict:
        """
        Transfer funds to a worker's connected account.
        This is how workers get paid for completed MEAT tasks.
        """
        try:
            amount_cents = int(amount_usd * 100)
            
            transfer = stripe.Transfer.create(
                amount=amount_cents,
                currency="usd",
                destination=account_id,
                description=description,
                metadata={
                    "task_id": task_id,
                    "platform": "nanilabs_meat"
                }
            )
            return {
                "success": True,
                "transfer_id": transfer.id,
                "amount": amount_usd,
                "destination": account_id
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def create_payout(account_id: str, amount_usd: float) -> dict:
        """
        Create a payout from connected account to their bank.
        Usually automatic, but can be triggered manually.
        """
        try:
            amount_cents = int(amount_usd * 100)
            
            payout = stripe.Payout.create(
                amount=amount_cents,
                currency="usd",
                stripe_account=account_id
            )
            return {
                "success": True,
                "payout_id": payout.id,
                "amount": amount_usd,
                "status": payout.status
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def get_worker_balance(account_id: str) -> dict:
        """Get balance of a connected account"""
        try:
            balance = stripe.Balance.retrieve(stripe_account=account_id)
            return {
                "success": True,
                "available": sum(b.amount / 100 for b in balance.available),
                "pending": sum(b.amount / 100 for b in balance.pending)
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    @staticmethod
    def process_webhook(payload: bytes, sig_header: str) -> dict:
        """Process incoming Stripe webhook"""
        try:
            if STRIPE_WEBHOOK_SECRET:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, STRIPE_WEBHOOK_SECRET
                )
            else:
                # For testing without webhook signature
                import json
                event = stripe.Event.construct_from(
                    json.loads(payload), stripe.api_key
                )
            
            return {
                "success": True,
                "event_type": event.type,
                "event_id": event.id,
                "data": event.data.object
            }
        except ValueError as e:
            return {"success": False, "error": f"Invalid payload: {e}"}
        except stripe.error.SignatureVerificationError as e:
            return {"success": False, "error": f"Invalid signature: {e}"}


# Convenience functions
def create_deposit_link(agent_id: str, wallet_id: str, amount: float) -> dict:
    """Quick function to create a deposit checkout link"""
    base_url = os.getenv("APP_URL", "https://nanilabs.io")
    
    return StripeService.create_checkout_session(
        agent_id=agent_id,
        wallet_id=wallet_id,
        amount_usd=amount,
        success_url=f"{base_url}/deposit-success",
        cancel_url=f"{base_url}/deposit-cancel"
    )


def verify_payment(session_id: str) -> dict:
    """Quick function to verify a payment was successful"""
    result = StripeService.retrieve_checkout_session(session_id)
    
    if result["success"] and result["payment_status"] == "paid":
        return {
            "verified": True,
            "amount": result["amount_total"],
            "agent_id": result["metadata"].get("agent_id"),
            "wallet_id": result["metadata"].get("wallet_id")
        }
    
    return {
        "verified": False,
        "status": result.get("payment_status", "unknown"),
        "error": result.get("error")
    }
