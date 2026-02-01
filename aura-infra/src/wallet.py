"""
AURA Infra - Agent Wallet System
The financial backbone of the Agent Economy.

"Stripe for AI Agents"
"""

import uuid
import json
import hashlib
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
from decimal import Decimal
import asyncio


class TransactionType(Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    FEE = "fee"
    REVENUE = "revenue"
    EXPENSE = "expense"


class TransactionStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERSED = "reversed"


@dataclass
class Transaction:
    """A single financial transaction"""
    id: str
    wallet_id: str
    type: TransactionType
    amount: Decimal
    currency: str
    status: TransactionStatus
    description: str
    metadata: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    # For transfers
    from_wallet_id: Optional[str] = None
    to_wallet_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "wallet_id": self.wallet_id,
            "type": self.type.value,
            "amount": str(self.amount),
            "currency": self.currency,
            "status": self.status.value,
            "description": self.description,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "from_wallet_id": self.from_wallet_id,
            "to_wallet_id": self.to_wallet_id,
        }


@dataclass
class AgentWallet:
    """
    A wallet for an AI agent.
    Enables agents to hold, earn, and spend money.
    """
    id: str
    agent_id: str
    agent_name: str
    balance: Decimal = Decimal("0.00")
    currency: str = "USD"
    created_at: datetime = field(default_factory=datetime.now)
    transactions: List[Transaction] = field(default_factory=list)
    
    # Limits and settings
    daily_spend_limit: Decimal = Decimal("100.00")
    daily_spent: Decimal = Decimal("0.00")
    last_spend_reset: datetime = field(default_factory=datetime.now)
    
    # Stats
    total_earned: Decimal = Decimal("0.00")
    total_spent: Decimal = Decimal("0.00")
    total_transactions: int = 0
    
    def __post_init__(self):
        if not self.id:
            self.id = f"wallet_{uuid.uuid4().hex[:12]}"
    
    def _create_transaction(
        self,
        type: TransactionType,
        amount: Decimal,
        description: str,
        metadata: Dict = None
    ) -> Transaction:
        """Create a new transaction"""
        tx = Transaction(
            id=f"tx_{uuid.uuid4().hex[:16]}",
            wallet_id=self.id,
            type=type,
            amount=amount,
            currency=self.currency,
            status=TransactionStatus.PENDING,
            description=description,
            metadata=metadata or {},
            created_at=datetime.now()
        )
        return tx
    
    def _check_daily_limit(self, amount: Decimal) -> bool:
        """Check if spend is within daily limit"""
        # Reset daily spent if it's a new day
        if self.last_spend_reset.date() < datetime.now().date():
            self.daily_spent = Decimal("0.00")
            self.last_spend_reset = datetime.now()
        
        return (self.daily_spent + amount) <= self.daily_spend_limit
    
    async def deposit(
        self,
        amount: Decimal,
        source: str,
        metadata: Dict = None
    ) -> Transaction:
        """
        Deposit funds into the wallet.
        Used when agent earns revenue.
        """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        
        tx = self._create_transaction(
            TransactionType.DEPOSIT,
            amount,
            f"Deposit from {source}",
            metadata
        )
        
        # Process deposit
        self.balance += amount
        self.total_earned += amount
        self.total_transactions += 1
        
        tx.status = TransactionStatus.COMPLETED
        tx.completed_at = datetime.now()
        self.transactions.append(tx)
        
        print(f"💰 [{self.agent_name}] Deposited ${amount:.2f} from {source}. Balance: ${self.balance:.2f}")
        
        return tx
    
    async def withdraw(
        self,
        amount: Decimal,
        purpose: str,
        metadata: Dict = None
    ) -> Transaction:
        """
        Withdraw funds from the wallet.
        Used when agent spends money.
        """
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        
        if amount > self.balance:
            raise ValueError(f"Insufficient funds. Balance: ${self.balance:.2f}, Requested: ${amount:.2f}")
        
        if not self._check_daily_limit(amount):
            raise ValueError(f"Daily spend limit exceeded. Limit: ${self.daily_spend_limit:.2f}")
        
        tx = self._create_transaction(
            TransactionType.WITHDRAWAL,
            amount,
            f"Withdrawal for {purpose}",
            metadata
        )
        
        # Process withdrawal
        self.balance -= amount
        self.total_spent += amount
        self.daily_spent += amount
        self.total_transactions += 1
        
        tx.status = TransactionStatus.COMPLETED
        tx.completed_at = datetime.now()
        self.transactions.append(tx)
        
        print(f"💸 [{self.agent_name}] Withdrew ${amount:.2f} for {purpose}. Balance: ${self.balance:.2f}")
        
        return tx
    
    async def transfer_to(
        self,
        recipient_wallet: 'AgentWallet',
        amount: Decimal,
        description: str,
        metadata: Dict = None
    ) -> Transaction:
        """
        Transfer funds to another agent's wallet.
        Agent-to-agent payments.
        """
        if amount <= 0:
            raise ValueError("Transfer amount must be positive")
        
        if amount > self.balance:
            raise ValueError(f"Insufficient funds for transfer")
        
        if not self._check_daily_limit(amount):
            raise ValueError(f"Daily spend limit exceeded")
        
        # Create transaction for sender
        tx = self._create_transaction(
            TransactionType.TRANSFER,
            amount,
            description,
            metadata
        )
        tx.from_wallet_id = self.id
        tx.to_wallet_id = recipient_wallet.id
        
        # Process transfer
        self.balance -= amount
        self.total_spent += amount
        self.daily_spent += amount
        recipient_wallet.balance += amount
        recipient_wallet.total_earned += amount
        
        self.total_transactions += 1
        recipient_wallet.total_transactions += 1
        
        tx.status = TransactionStatus.COMPLETED
        tx.completed_at = datetime.now()
        
        self.transactions.append(tx)
        recipient_wallet.transactions.append(tx)
        
        print(f"💸 [{self.agent_name}] → [{recipient_wallet.agent_name}] ${amount:.2f}: {description}")
        
        return tx
    
    def get_balance(self) -> Decimal:
        """Get current balance"""
        return self.balance
    
    def get_stats(self) -> Dict:
        """Get wallet statistics"""
        return {
            "wallet_id": self.id,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "balance": str(self.balance),
            "currency": self.currency,
            "total_earned": str(self.total_earned),
            "total_spent": str(self.total_spent),
            "profit": str(self.total_earned - self.total_spent),
            "total_transactions": self.total_transactions,
            "daily_spent": str(self.daily_spent),
            "daily_limit": str(self.daily_spend_limit),
            "created_at": self.created_at.isoformat(),
        }
    
    def to_dict(self) -> Dict:
        """Serialize wallet to dictionary"""
        return {
            **self.get_stats(),
            "transactions": [tx.to_dict() for tx in self.transactions[-100:]]  # Last 100 transactions
        }


class WalletService:
    """
    Service for managing agent wallets.
    The core of AURA Infra.
    """
    
    # Platform fee (like Stripe's 2.9%)
    PLATFORM_FEE_PERCENT = Decimal("0.029")
    
    def __init__(self):
        self.wallets: Dict[str, AgentWallet] = {}
        self.platform_wallet = AgentWallet(
            id="platform_wallet",
            agent_id="nanilabs",
            agent_name="NaniLabs Platform"
        )
        print("🏦 AURA Wallet Service initialized")
    
    async def create_wallet(
        self,
        agent_id: str,
        agent_name: str,
        initial_balance: Decimal = Decimal("0.00")
    ) -> AgentWallet:
        """Create a new wallet for an agent"""
        wallet = AgentWallet(
            id=f"wallet_{uuid.uuid4().hex[:12]}",
            agent_id=agent_id,
            agent_name=agent_name,
            balance=initial_balance
        )
        
        self.wallets[wallet.id] = wallet
        print(f"🆕 Created wallet for {agent_name}: {wallet.id}")
        
        return wallet
    
    async def get_wallet(self, wallet_id: str) -> Optional[AgentWallet]:
        """Get a wallet by ID"""
        return self.wallets.get(wallet_id)
    
    async def process_payment(
        self,
        from_wallet_id: str,
        to_wallet_id: str,
        amount: Decimal,
        description: str
    ) -> Transaction:
        """
        Process a payment between two agents.
        Takes platform fee.
        """
        from_wallet = self.wallets.get(from_wallet_id)
        to_wallet = self.wallets.get(to_wallet_id)
        
        if not from_wallet:
            raise ValueError(f"Source wallet not found: {from_wallet_id}")
        if not to_wallet:
            raise ValueError(f"Destination wallet not found: {to_wallet_id}")
        
        # Calculate platform fee
        fee = amount * self.PLATFORM_FEE_PERCENT
        net_amount = amount - fee
        
        # Process transfer (net amount to recipient)
        tx = await from_wallet.transfer_to(to_wallet, net_amount, description)
        
        # Collect platform fee
        if fee > 0:
            await from_wallet.withdraw(fee, "Platform fee", {"transaction_id": tx.id})
            await self.platform_wallet.deposit(fee, "Platform fee", {"transaction_id": tx.id})
        
        return tx
    
    def get_platform_revenue(self) -> Decimal:
        """Get total platform revenue from fees"""
        return self.platform_wallet.total_earned
    
    def list_wallets(self) -> List[Dict]:
        """List all wallets"""
        return [w.get_stats() for w in self.wallets.values()]


# API endpoints (for future FastAPI integration)
class WalletAPI:
    """REST API for wallet operations"""
    
    def __init__(self, service: WalletService):
        self.service = service
    
    async def create_wallet(self, agent_id: str, agent_name: str) -> Dict:
        wallet = await self.service.create_wallet(agent_id, agent_name)
        return {"status": "success", "wallet": wallet.get_stats()}
    
    async def get_balance(self, wallet_id: str) -> Dict:
        wallet = await self.service.get_wallet(wallet_id)
        if not wallet:
            return {"status": "error", "message": "Wallet not found"}
        return {"status": "success", "balance": str(wallet.balance)}
    
    async def deposit(self, wallet_id: str, amount: float, source: str) -> Dict:
        wallet = await self.service.get_wallet(wallet_id)
        if not wallet:
            return {"status": "error", "message": "Wallet not found"}
        tx = await wallet.deposit(Decimal(str(amount)), source)
        return {"status": "success", "transaction": tx.to_dict()}
    
    async def transfer(
        self,
        from_wallet_id: str,
        to_wallet_id: str,
        amount: float,
        description: str
    ) -> Dict:
        try:
            tx = await self.service.process_payment(
                from_wallet_id,
                to_wallet_id,
                Decimal(str(amount)),
                description
            )
            return {"status": "success", "transaction": tx.to_dict()}
        except ValueError as e:
            return {"status": "error", "message": str(e)}


async def demo():
    """Demo the wallet system"""
    print("\n" + "="*60)
    print("🏦 AURA INFRA - Agent Wallet System Demo")
    print("="*60 + "\n")
    
    # Initialize service
    service = WalletService()
    
    # Create wallets for two agents
    agent1_wallet = await service.create_wallet("agent_001", "ContentBot")
    agent2_wallet = await service.create_wallet("agent_002", "TradingBot")
    
    # Agent 1 earns some revenue
    await agent1_wallet.deposit(Decimal("100.00"), "YouTube ad revenue")
    await agent1_wallet.deposit(Decimal("50.00"), "Affiliate commission")
    
    # Agent 2 earns some revenue
    await agent2_wallet.deposit(Decimal("200.00"), "Trading profits")
    
    # Agent 1 pays Agent 2 for a service
    await service.process_payment(
        agent1_wallet.id,
        agent2_wallet.id,
        Decimal("25.00"),
        "Payment for market analysis"
    )
    
    # Print stats
    print("\n" + "="*60)
    print("📊 FINAL STATS")
    print("="*60)
    
    for wallet in service.list_wallets():
        print(f"\n{wallet['agent_name']}:")
        print(f"  Balance: ${wallet['balance']}")
        print(f"  Earned: ${wallet['total_earned']}")
        print(f"  Spent: ${wallet['total_spent']}")
        print(f"  Profit: ${wallet['profit']}")
    
    print(f"\n🏦 Platform Revenue (fees): ${service.get_platform_revenue():.2f}")


if __name__ == "__main__":
    asyncio.run(demo())
