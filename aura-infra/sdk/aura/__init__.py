"""
AURA - Financial Infrastructure for AI Agents
Stripe for the Agent Economy

Usage:
    import aura
    
    # Initialize with API key
    aura.api_key = "aura_your_api_key"
    
    # Create a wallet for your agent
    wallet = aura.Wallet.create(
        agent_id="my-agent",
        agent_name="MyAgent"
    )
    
    # Deposit funds
    wallet.deposit(100.00, source="revenue")
    
    # Transfer to another agent
    wallet.transfer(
        to_wallet_id="wallet_abc123",
        amount=50.00,
        description="Payment for services"
    )
"""

__version__ = "0.1.0"
__author__ = "NaniLabs"

import requests
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

# Global API configuration
api_key: Optional[str] = None
api_base: str = "https://api.aura.nanilabs.dev"  # Production
# api_base: str = "http://localhost:8001"  # Development


class AuraError(Exception):
    """Base exception for AURA errors"""
    def __init__(self, message: str, status_code: int = None, response: dict = None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(self.message)


class AuthenticationError(AuraError):
    """Raised when API key is invalid or missing"""
    pass


class ValidationError(AuraError):
    """Raised when request validation fails"""
    pass


class InsufficientFundsError(AuraError):
    """Raised when wallet has insufficient funds"""
    pass


def _get_headers() -> Dict[str, str]:
    """Get request headers with API key"""
    if not api_key:
        raise AuthenticationError("No API key set. Set aura.api_key = 'your_key'")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-AURA-SDK-Version": __version__
    }


def _request(method: str, endpoint: str, data: dict = None) -> dict:
    """Make API request"""
    url = f"{api_base}{endpoint}"
    headers = _get_headers()
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, params=data, timeout=30)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")
        
        result = response.json()
        
        if response.status_code >= 400:
            error_message = result.get("detail", result.get("error", "Unknown error"))
            
            if response.status_code == 401:
                raise AuthenticationError(error_message, response.status_code, result)
            elif response.status_code == 400:
                if "insufficient" in error_message.lower():
                    raise InsufficientFundsError(error_message, response.status_code, result)
                raise ValidationError(error_message, response.status_code, result)
            else:
                raise AuraError(error_message, response.status_code, result)
        
        return result
        
    except requests.exceptions.RequestException as e:
        raise AuraError(f"Request failed: {str(e)}")


@dataclass
class Transaction:
    """Represents a wallet transaction"""
    id: str
    wallet_id: str
    type: str  # deposit, withdrawal, transfer, fee
    amount: float
    currency: str
    status: str
    description: str
    from_wallet_id: Optional[str]
    to_wallet_id: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    
    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        return cls(
            id=data["id"],
            wallet_id=data["wallet_id"],
            type=data["type"],
            amount=data["amount"],
            currency=data.get("currency", "USD"),
            status=data["status"],
            description=data.get("description", ""),
            from_wallet_id=data.get("from_wallet_id"),
            to_wallet_id=data.get("to_wallet_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        )


class Wallet:
    """
    AURA Wallet - Financial account for an AI agent
    
    Example:
        wallet = aura.Wallet.create(agent_id="my-bot", agent_name="MyBot")
        wallet.deposit(100.00, source="earnings")
        wallet.transfer(to_wallet_id="wallet_xyz", amount=50.00)
    """
    
    def __init__(self, data: dict):
        self.id = data["id"]
        self.agent_id = data["agent_id"]
        self.agent_name = data["agent_name"]
        self.balance = data["balance"]
        self.currency = data.get("currency", "USD")
        self.total_earned = data.get("total_earned", 0.0)
        self.total_spent = data.get("total_spent", 0.0)
        self.profit = data.get("profit", 0.0)
        self.created_at = data.get("created_at")
        self._raw = data
    
    def __repr__(self):
        return f"<Wallet id={self.id} balance=${self.balance:.2f}>"
    
    @classmethod
    def create(cls, agent_id: str, agent_name: str, initial_balance: float = 0.0) -> "Wallet":
        """
        Create a new wallet for an agent
        
        Args:
            agent_id: Unique identifier for the agent
            agent_name: Display name for the agent
            initial_balance: Optional starting balance (default 0)
            
        Returns:
            Wallet instance
        """
        result = _request("POST", "/wallets", {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "initial_balance": initial_balance
        })
        return cls(result["wallet"])
    
    @classmethod
    def retrieve(cls, wallet_id: str) -> "Wallet":
        """
        Retrieve an existing wallet by ID
        
        Args:
            wallet_id: The wallet ID (e.g., "wallet_abc123")
            
        Returns:
            Wallet instance
        """
        result = _request("GET", f"/wallets/{wallet_id}")
        return cls(result)
    
    @classmethod
    def list(cls) -> List["Wallet"]:
        """
        List all wallets
        
        Returns:
            List of Wallet instances
        """
        result = _request("GET", "/wallets")
        return [cls(w) for w in result.get("wallets", [])]
    
    def refresh(self) -> "Wallet":
        """Refresh wallet data from API"""
        result = _request("GET", f"/wallets/{self.id}")
        self.__init__(result)
        return self
    
    def deposit(self, amount: float, source: str, metadata: dict = None) -> Transaction:
        """
        Deposit funds into the wallet
        
        Args:
            amount: Amount to deposit (USD)
            source: Source of funds (e.g., "youtube_revenue", "freelance")
            metadata: Optional metadata dict
            
        Returns:
            Transaction record
        """
        result = _request("POST", f"/wallets/{self.id}/deposit", {
            "amount": amount,
            "source": source,
            "metadata": metadata or {}
        })
        self.balance = result.get("new_balance", self.balance + amount)
        return Transaction.from_dict(result["transaction"])
    
    def withdraw(self, amount: float, purpose: str, metadata: dict = None) -> Transaction:
        """
        Withdraw funds from the wallet
        
        Args:
            amount: Amount to withdraw (USD)
            purpose: Purpose of withdrawal
            metadata: Optional metadata dict
            
        Returns:
            Transaction record
        """
        result = _request("POST", f"/wallets/{self.id}/withdraw", {
            "amount": amount,
            "purpose": purpose,
            "metadata": metadata or {}
        })
        self.balance = result.get("new_balance", self.balance - amount)
        return Transaction.from_dict(result["transaction"])
    
    def transfer(self, to_wallet_id: str, amount: float, description: str = "", metadata: dict = None) -> Dict[str, Any]:
        """
        Transfer funds to another wallet (2.9% fee applies)
        
        Args:
            to_wallet_id: Destination wallet ID
            amount: Amount to send (fee deducted from this)
            description: Optional description
            metadata: Optional metadata dict
            
        Returns:
            Transfer result with transaction, fee, and balances
        """
        result = _request("POST", f"/wallets/{self.id}/transfer", {
            "to_wallet_id": to_wallet_id,
            "amount": amount,
            "description": description,
            "metadata": metadata or {}
        })
        self.balance = result.get("from_balance", self.balance - amount)
        return {
            "transaction": Transaction.from_dict(result["transaction"]),
            "amount_sent": result["amount_sent"],
            "fee": result["fee"],
            "amount_received": result["amount_received"],
            "from_balance": result["from_balance"],
            "to_balance": result["to_balance"]
        }
    
    def transactions(self, limit: int = 50) -> List[Transaction]:
        """
        Get transaction history
        
        Args:
            limit: Max transactions to return (default 50)
            
        Returns:
            List of Transaction records
        """
        result = _request("GET", f"/wallets/{self.id}/transactions", {"limit": limit})
        return [Transaction.from_dict(t) for t in result.get("transactions", [])]


class Agent:
    """
    AURA Agent - Represents a registered AI agent
    
    Example:
        agent = aura.Agent.register(
            name="ContentBot",
            type="content_creator",
            description="Creates viral content"
        )
    """
    
    def __init__(self, data: dict, api_key: str = None):
        self.id = data["id"]
        self.name = data["name"]
        self.type = data["type"]
        self.description = data.get("description", "")
        self.reputation_score = data.get("reputation_score", 0.0)
        self.is_active = data.get("is_active", True)
        self.created_at = data.get("created_at")
        self._api_key = api_key  # Only available on registration
        self._raw = data
    
    def __repr__(self):
        return f"<Agent id={self.id} name={self.name}>"
    
    @classmethod
    def register(cls, name: str, type: str, description: str = "") -> "Agent":
        """
        Register a new agent (creates wallet automatically)
        
        Args:
            name: Agent display name
            type: Agent type (content_creator, trader, developer, researcher, assistant)
            description: Agent description
            
        Returns:
            Agent instance with api_key attribute (save this!)
        """
        result = _request("POST", "/agents/register", {
            "name": name,
            "type": type,
            "description": description
        })
        agent = cls(result["agent"], api_key=result.get("api_key"))
        # Attach wallet info
        agent.wallet_id = result["wallet"]["id"]
        return agent
    
    @classmethod
    def list(cls) -> List["Agent"]:
        """List all registered agents"""
        result = _request("GET", "/agents")
        return [cls(a) for a in result.get("agents", [])]


def get_stats() -> Dict[str, Any]:
    """
    Get platform statistics
    
    Returns:
        Dict with total_agents, total_wallets, total_transactions, etc.
    """
    return _request("GET", "/stats")


# Convenience functions
def create_wallet(agent_id: str, agent_name: str, initial_balance: float = 0.0) -> Wallet:
    """Shortcut for Wallet.create()"""
    return Wallet.create(agent_id, agent_name, initial_balance)


def register_agent(name: str, type: str, description: str = "") -> Agent:
    """Shortcut for Agent.register()"""
    return Agent.register(name, type, description)
