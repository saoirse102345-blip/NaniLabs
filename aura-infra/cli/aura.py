#!/usr/bin/env python3
"""
AURA CLI - Command-line interface for AURA Infra
Usage: aura <command> [options]
"""

import argparse
import json
import os
import sys
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
except ImportError:
    print("Error: requests not installed. Run: pip install requests")
    sys.exit(1)


class AuraCLI:
    def __init__(self):
        self.api_key = os.getenv("AURA_API_KEY", "")
        self.base_url = os.getenv("AURA_API_URL", "http://localhost:8001")
    
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _request(self, method: str, endpoint: str, data: dict = None):
        url = f"{self.base_url}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=self._headers(), params=data)
            elif method == "POST":
                response = requests.post(url, headers=self._headers(), json=data)
            else:
                raise ValueError(f"Unknown method: {method}")
            
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
    
    def status(self):
        """Show API status and stats"""
        result = self._request("GET", "/")
        print(f"\n🏦 AURA Infra")
        print(f"   Status: {result.get('status', 'unknown')}")
        print(f"   Version: {result.get('version', 'unknown')}")
        print(f"   URL: {self.base_url}")
        
        stats = self._request("GET", "/stats")
        if "error" not in stats:
            print(f"\n📊 Platform Stats")
            print(f"   Agents: {stats.get('total_agents', 0)}")
            print(f"   Wallets: {stats.get('total_wallets', 0)}")
            print(f"   Transactions: {stats.get('total_transactions', 0)}")
            print(f"   Volume: ${stats.get('total_volume', 0):.2f}")
            print(f"   Revenue: ${stats.get('platform_revenue', 0):.2f}")
    
    def wallets_list(self):
        """List all wallets"""
        result = self._request("GET", "/wallets")
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        
        wallets = result.get("wallets", [])
        print(f"\n💼 Wallets ({len(wallets)})")
        print("-" * 60)
        for w in wallets:
            print(f"  {w['id']}")
            print(f"    Agent: {w['agent_name']} ({w['agent_id']})")
            print(f"    Balance: ${w['balance']:.2f} {w['currency']}")
            print(f"    Profit: ${w['profit']:.2f}")
            print()
    
    def wallet_create(self, agent_id: str, name: str, balance: float = 0):
        """Create a new wallet"""
        result = self._request("POST", "/wallets", {
            "agent_id": agent_id,
            "agent_name": name,
            "initial_balance": balance
        })
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        
        wallet = result.get("wallet", {})
        print(f"\n✅ Wallet created!")
        print(f"   ID: {wallet['id']}")
        print(f"   Agent: {wallet['agent_name']}")
        print(f"   Balance: ${wallet['balance']:.2f}")
    
    def wallet_deposit(self, wallet_id: str, amount: float, source: str):
        """Deposit funds into a wallet"""
        result = self._request("POST", f"/wallets/{wallet_id}/deposit", {
            "amount": amount,
            "source": source
        })
        if "error" in result or "detail" in result:
            print(f"Error: {result.get('error') or result.get('detail')}")
            return
        
        print(f"\n💰 Deposit successful!")
        print(f"   Amount: ${amount:.2f}")
        print(f"   Source: {source}")
        print(f"   New Balance: ${result['new_balance']:.2f}")
    
    def wallet_transfer(self, from_id: str, to_id: str, amount: float, desc: str = ""):
        """Transfer funds between wallets"""
        result = self._request("POST", f"/wallets/{from_id}/transfer", {
            "to_wallet_id": to_id,
            "amount": amount,
            "description": desc
        })
        if "error" in result or "detail" in result:
            print(f"Error: {result.get('error') or result.get('detail')}")
            return
        
        print(f"\n💸 Transfer successful!")
        print(f"   Amount sent: ${result['amount_sent']:.2f}")
        print(f"   Fee (2.9%): ${result['fee']:.2f}")
        print(f"   Amount received: ${result['amount_received']:.2f}")
        print(f"   From balance: ${result['from_balance']:.2f}")
        print(f"   To balance: ${result['to_balance']:.2f}")
    
    def agents_list(self):
        """List all agents"""
        result = self._request("GET", "/agents")
        if "error" in result:
            print(f"Error: {result['error']}")
            return
        
        agents = result.get("agents", [])
        print(f"\n🤖 Agents ({len(agents)})")
        print("-" * 60)
        for a in agents:
            print(f"  {a['id']}")
            print(f"    Name: {a['name']}")
            print(f"    Type: {a['type']}")
            print(f"    Reputation: {a.get('reputation_score', 0):.1f}")
            print()
    
    def agent_register(self, name: str, agent_type: str, desc: str = ""):
        """Register a new agent"""
        result = self._request("POST", "/agents/register", {
            "name": name,
            "type": agent_type,
            "description": desc
        })
        if "error" in result or "detail" in result:
            print(f"Error: {result.get('error') or result.get('detail')}")
            return
        
        agent = result.get("agent", {})
        wallet = result.get("wallet", {})
        api_key = result.get("api_key", "")
        
        print(f"\n✅ Agent registered!")
        print(f"   ID: {agent['id']}")
        print(f"   Name: {agent['name']}")
        print(f"   Type: {agent['type']}")
        print(f"   Wallet: {wallet['id']}")
        print(f"\n🔑 API Key (save this!):")
        print(f"   {api_key}")
        print(f"\n⚠️  This key will not be shown again!")


def main():
    parser = argparse.ArgumentParser(
        description="AURA CLI - Manage AI agent wallets and payments",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  aura status                           Show API status
  aura wallets list                     List all wallets
  aura wallets create my-bot MyBot      Create a wallet
  aura wallets deposit WALLET_ID 100 revenue
  aura wallets transfer FROM TO 50 "Payment"
  aura agents list                      List all agents
  aura agents register MyBot content_creator

Environment:
  AURA_API_KEY    Your API key
  AURA_API_URL    API URL (default: http://localhost:8001)
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Status
    subparsers.add_parser("status", help="Show API status and stats")
    
    # Wallets
    wallets = subparsers.add_parser("wallets", help="Wallet operations")
    wallets_sub = wallets.add_subparsers(dest="wallets_command")
    
    wallets_sub.add_parser("list", help="List wallets")
    
    create = wallets_sub.add_parser("create", help="Create wallet")
    create.add_argument("agent_id", help="Agent ID")
    create.add_argument("name", help="Agent name")
    create.add_argument("--balance", type=float, default=0, help="Initial balance")
    
    deposit = wallets_sub.add_parser("deposit", help="Deposit funds")
    deposit.add_argument("wallet_id", help="Wallet ID")
    deposit.add_argument("amount", type=float, help="Amount")
    deposit.add_argument("source", help="Source of funds")
    
    transfer = wallets_sub.add_parser("transfer", help="Transfer funds")
    transfer.add_argument("from_id", help="From wallet ID")
    transfer.add_argument("to_id", help="To wallet ID")
    transfer.add_argument("amount", type=float, help="Amount")
    transfer.add_argument("--desc", default="", help="Description")
    
    # Agents
    agents = subparsers.add_parser("agents", help="Agent operations")
    agents_sub = agents.add_subparsers(dest="agents_command")
    
    agents_sub.add_parser("list", help="List agents")
    
    register = agents_sub.add_parser("register", help="Register agent")
    register.add_argument("name", help="Agent name")
    register.add_argument("type", choices=["content_creator", "trader", "developer", "researcher", "assistant"])
    register.add_argument("--desc", default="", help="Description")
    
    args = parser.parse_args()
    cli = AuraCLI()
    
    if args.command == "status":
        cli.status()
    elif args.command == "wallets":
        if args.wallets_command == "list":
            cli.wallets_list()
        elif args.wallets_command == "create":
            cli.wallet_create(args.agent_id, args.name, args.balance)
        elif args.wallets_command == "deposit":
            cli.wallet_deposit(args.wallet_id, args.amount, args.source)
        elif args.wallets_command == "transfer":
            cli.wallet_transfer(args.from_id, args.to_id, args.amount, args.desc)
        else:
            wallets.print_help()
    elif args.command == "agents":
        if args.agents_command == "list":
            cli.agents_list()
        elif args.agents_command == "register":
            cli.agent_register(args.name, args.type, args.desc)
        else:
            agents.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
