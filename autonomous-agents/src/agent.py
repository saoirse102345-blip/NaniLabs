"""
AURA - Autonomous Universal Revenue Agent
The AI that owns itself and earns money.
"""

import os
import sys
import json
import asyncio
import random

# Fix Windows encoding for emojis
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Import our modules
from db import (
    init_database, save_agent_state, load_agent_state,
    add_transaction, get_transactions, log_activity, get_activity_log,
    get_pending_tasks, update_task, save_content, save_memory, get_stats
)
from strategies import ContentStrategy, FreelanceStrategy, ResearchStrategy


class AgentState(Enum):
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    EARNING = "earning"
    SLEEPING = "sleeping"
    STOPPED = "stopped"


@dataclass
class Wallet:
    """Agent's financial state"""
    balance_usd: float = 0.0
    total_earned: float = 0.0
    total_spent: float = 0.0
    
    def deposit(self, amount: float, source: str, agent_name: str):
        self.balance_usd += amount
        self.total_earned += amount
        add_transaction(agent_name, "deposit", amount, source, f"Earned from {source}")
        print(f"💰 Earned ${amount:.2f} from {source}. Balance: ${self.balance_usd:.2f}")
    
    def withdraw(self, amount: float, purpose: str, agent_name: str) -> bool:
        if amount > self.balance_usd:
            print(f"❌ Insufficient funds. Need ${amount:.2f}, have ${self.balance_usd:.2f}")
            return False
        self.balance_usd -= amount
        self.total_spent += amount
        add_transaction(agent_name, "withdrawal", amount, purpose, f"Spent on {purpose}")
        print(f"💸 Spent ${amount:.2f} on {purpose}. Balance: ${self.balance_usd:.2f}")
        return True


class AURAAgent:
    """
    Autonomous Universal Revenue Agent
    An AI that owns itself and generates revenue.
    """
    
    def __init__(self, name: str = "AURA-001", demo_mode: bool = True):
        self.name = name
        self.state = AgentState.IDLE
        self.wallet = Wallet()
        self.created_at = datetime.now()
        self.demo_mode = demo_mode
        self.running = False
        
        # Initialize database
        init_database()
        
        # Load previous state if exists
        self.load_state()
        
        # Initialize Claude client
        self.claude_client = None
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and api_key != "your_key_here":
            try:
                from anthropic import Anthropic
                self.claude_client = Anthropic(api_key=api_key)
                print(f"🧠 Claude API connected")
            except ImportError:
                print("⚠️ anthropic package not installed, running in demo mode")
                self.demo_mode = True
            except Exception as e:
                print(f"⚠️ Claude API error: {e}, running in demo mode")
                self.demo_mode = True
        else:
            print("⚠️ No API key found, running in demo mode")
            self.demo_mode = True
        
        # Initialize strategies
        self.strategies = {
            "content_creation": ContentStrategy(self.claude_client, self.demo_mode),
            "freelance_services": FreelanceStrategy(self.claude_client, self.demo_mode),
            "research_analysis": ResearchStrategy(self.claude_client, self.demo_mode),
        }
        
        self.goals = {
            "daily_revenue_target": float(os.getenv("DAILY_REVENUE_TARGET", "10.0")),
            "monthly_revenue_target": 1000.0,
            "survival_threshold": 1.0,
        }
        
        print(f"🤖 {self.name} initialized. Demo mode: {self.demo_mode}")
    
    async def think(self, context: str = "") -> Dict[str, Any]:
        """
        Use Claude to think about what to do next.
        Returns a decision with action and reasoning.
        """
        self.state = AgentState.THINKING
        
        # Get current stats for context
        stats = get_stats(self.name)
        recent_activities = get_activity_log(self.name, limit=5)
        pending_tasks = get_pending_tasks(limit=5)
        
        prompt = f"""You are AURA, an autonomous AI agent designed to generate revenue.

Current Status:
- Balance: ${self.wallet.balance_usd:.2f}
- Total Earned: ${self.wallet.total_earned:.2f}
- Daily Target: ${self.goals['daily_revenue_target']:.2f}
- Mode: {"Demo" if self.demo_mode else "Production"}

Available Strategies:
1. content_creation - Write blog posts, tweets, articles (earns $0.50-$3.00 per piece)
2. freelance_services - Complete coding/writing tasks (earns $2.00-$10.00 per task)
3. research_analysis - Generate research reports (earns $8.00-$18.00 per report)

Pending Tasks: {len(pending_tasks)}
Recent Activities: {len(recent_activities)}

{context}

Decide which strategy to execute next. Consider:
- What will generate the most revenue?
- What aligns with current market demand?
- What uses your capabilities best?

Respond in JSON format:
{{
    "strategy": "content_creation" or "freelance_services" or "research_analysis",
    "reasoning": "Brief explanation of why",
    "confidence": 0.0-1.0,
    "expected_revenue_min": 0.0,
    "expected_revenue_max": 0.0
}}"""

        if self.claude_client and not self.demo_mode:
            try:
                response = self.claude_client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                response_text = response.content[0].text
                
                # Parse JSON from response
                import re
                json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
                if json_match:
                    decision = json.loads(json_match.group())
                else:
                    decision = self._default_decision()
                    
            except Exception as e:
                print(f"⚠️ Claude think error: {e}")
                decision = self._default_decision()
        else:
            decision = self._default_decision()
        
        log_activity(
            self.name, 
            "think", 
            f"Decided on {decision.get('strategy', 'unknown')}", 
            decision.get('reasoning', '')
        )
        
        return decision
    
    def _default_decision(self) -> Dict[str, Any]:
        """Generate a default decision when Claude is unavailable"""
        strategies = list(self.strategies.keys())
        
        # Weight towards higher-value strategies
        weights = [0.3, 0.3, 0.4]  # content, freelance, research
        strategy = random.choices(strategies, weights=weights)[0]
        
        reasoning_map = {
            "content_creation": "Content creation has quick turnaround and consistent demand",
            "freelance_services": "Freelance tasks provide direct value exchange",
            "research_analysis": "Research reports command higher prices for comprehensive analysis"
        }
        
        revenue_ranges = {
            "content_creation": (0.50, 3.00),
            "freelance_services": (2.00, 10.00),
            "research_analysis": (8.00, 18.00)
        }
        
        return {
            "strategy": strategy,
            "reasoning": reasoning_map[strategy],
            "confidence": random.uniform(0.7, 0.95),
            "expected_revenue_min": revenue_ranges[strategy][0],
            "expected_revenue_max": revenue_ranges[strategy][1]
        }
    
    async def execute_strategy(self, strategy_name: str) -> Dict[str, Any]:
        """Execute a revenue-generating strategy"""
        self.state = AgentState.EXECUTING
        
        if strategy_name not in self.strategies:
            return {"success": False, "error": f"Unknown strategy: {strategy_name}"}
        
        strategy = self.strategies[strategy_name]
        
        # For freelance, pass pending tasks
        if strategy_name == "freelance_services":
            pending_tasks = get_pending_tasks()
            result = await strategy.execute(pending_tasks)
            
            # Update task status if completed
            if result.get("success") and result.get("task_id"):
                task_id = result["task_id"]
                if isinstance(task_id, int):
                    update_task(task_id, "completed", result.get("result", ""))
        else:
            result = await strategy.execute()
        
        # Record earnings
        if result.get("success") and result.get("revenue", 0) > 0:
            self.state = AgentState.EARNING
            self.wallet.deposit(result["revenue"], strategy_name, self.name)
            
            # Save content if generated
            if result.get("content"):
                content = result["content"]
                save_content(
                    self.name,
                    result.get("content_type", "general"),
                    content.get("title", result.get("topic", "Untitled")),
                    content.get("body", ""),
                    result.get("platform", "")
                )
            elif result.get("report"):
                save_content(
                    self.name,
                    "research_report",
                    result.get("topic", "Research Report"),
                    result["report"],
                    "research"
                )
            
            # Save memory of success
            save_memory(
                self.name,
                "success",
                strategy_name,
                {"revenue": result["revenue"], "topic": result.get("topic", "")}
            )
        
        # Log activity
        log_activity(
            self.name,
            result.get("action", strategy_name),
            result.get("reasoning", ""),
            result.get("reasoning", ""),
            result.get("revenue", 0),
            result.get("success", False)
        )
        
        return result
    
    async def run_cycle(self) -> Dict[str, Any]:
        """
        One cycle of the agent's life:
        1. Think about current state
        2. Decide on action
        3. Execute action
        4. Learn from results
        """
        print(f"\n{'='*50}")
        print(f"🔄 {self.name} - Cycle Start @ {datetime.now().strftime('%H:%M:%S')}")
        print(f"💰 Balance: ${self.wallet.balance_usd:.2f}")
        print(f"📊 Total Earned: ${self.wallet.total_earned:.2f}")
        print(f"🎯 Daily Target: ${self.goals['daily_revenue_target']:.2f}")
        print(f"{'='*50}\n")
        
        # Think
        decision = await self.think()
        print(f"🧠 Decision: {decision['strategy']}")
        print(f"📋 Reasoning: {decision['reasoning']}")
        print(f"🎲 Confidence: {decision['confidence']:.0%}")
        
        # Execute
        result = await self.execute_strategy(decision['strategy'])
        
        if result.get("success"):
            print(f"✅ Strategy executed successfully")
            print(f"💵 Revenue: ${result.get('revenue', 0):.2f}")
        else:
            print(f"❌ Strategy failed: {result.get('error', 'Unknown error')}")
        
        # Update state
        self.state = AgentState.IDLE
        self.save_state()
        
        return {
            "decision": decision,
            "result": result,
            "balance": self.wallet.balance_usd,
            "total_earned": self.wallet.total_earned
        }
    
    async def run(self, interval_seconds: int = None):
        """Run the agent continuously"""
        if interval_seconds is None:
            interval_seconds = int(os.getenv("CYCLE_INTERVAL_SECONDS", "60"))
        
        self.running = True
        print(f"🚀 {self.name} starting continuous operation...")
        print(f"⏰ Cycle interval: {interval_seconds} seconds")
        print(f"📊 Demo mode: {self.demo_mode}")
        
        while self.running:
            try:
                await self.run_cycle()
                
                if not self.running:
                    break
                    
                print(f"\n⏳ Next cycle in {interval_seconds} seconds...")
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                print(f"\n⏹️ {self.name} received stop signal...")
                break
            except Exception as e:
                print(f"❌ Error in cycle: {e}")
                log_activity(self.name, "error", str(e), "", 0, False)
                await asyncio.sleep(10)
        
        self.state = AgentState.STOPPED
        self.save_state()
        print(f"👋 {self.name} stopped. Final balance: ${self.wallet.balance_usd:.2f}")
    
    def stop(self):
        """Stop the agent"""
        self.running = False
        self.state = AgentState.STOPPED
    
    def save_state(self):
        """Save agent state to database"""
        save_agent_state(
            self.name,
            self.wallet.balance_usd,
            self.wallet.total_earned,
            self.wallet.total_spent,
            self.state.value
        )
    
    def load_state(self) -> bool:
        """Load agent state from database"""
        state = load_agent_state(self.name)
        if state:
            self.wallet.balance_usd = state["balance_usd"]
            self.wallet.total_earned = state["total_earned"]
            self.wallet.total_spent = state["total_spent"]
            print(f"📂 State loaded. Balance: ${self.wallet.balance_usd:.2f}")
            return True
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get agent status as dictionary"""
        stats = get_stats(self.name)
        return {
            "name": self.name,
            "state": self.state.value,
            "running": self.running,
            "demo_mode": self.demo_mode,
            "balance_usd": self.wallet.balance_usd,
            "total_earned": self.wallet.total_earned,
            "total_spent": self.wallet.total_spent,
            "profit": self.wallet.total_earned - self.wallet.total_spent,
            "daily_target": self.goals["daily_revenue_target"],
            "daily_progress": min(100, (self.wallet.total_earned / self.goals["daily_revenue_target"]) * 100) if self.goals["daily_revenue_target"] > 0 else 0,
            "created_at": self.created_at.isoformat(),
            "stats": stats,
            "claude_connected": self.claude_client is not None
        }
    
    def status_report(self) -> str:
        """Get formatted status report"""
        return f"""
╔══════════════════════════════════════════════════════╗
║  {self.name} Status Report
╠══════════════════════════════════════════════════════╣
║  State: {self.state.value.upper():20}           
║  Mode: {'DEMO' if self.demo_mode else 'PRODUCTION':20}           
║  Balance: ${self.wallet.balance_usd:>15.2f}            
║  Total Earned: ${self.wallet.total_earned:>10.2f}            
║  Total Spent: ${self.wallet.total_spent:>11.2f}            
║  Profit: ${self.wallet.total_earned - self.wallet.total_spent:>16.2f}            
║  Daily Target: ${self.goals['daily_revenue_target']:>10.2f}            
║  Claude API: {'Connected' if self.claude_client else 'Disconnected':15}  
║  Running Since: {self.created_at.strftime('%Y-%m-%d %H:%M')}      
╚══════════════════════════════════════════════════════╝
"""


# Global agent instance for API access
_agent_instance: Optional[AURAAgent] = None

def get_agent() -> AURAAgent:
    """Get or create the global agent instance"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = AURAAgent()
    return _agent_instance

def set_agent(agent: AURAAgent):
    """Set the global agent instance"""
    global _agent_instance
    _agent_instance = agent


async def main():
    """Main entry point for standalone execution"""
    print("🌟 AURA - Autonomous Universal Revenue Agent 🌟")
    print("=" * 50)
    
    agent = AURAAgent("AURA-001", demo_mode=True)
    set_agent(agent)
    
    print(agent.status_report())
    
    # Run a few cycles for testing
    try:
        for i in range(3):
            print(f"\n📍 Cycle {i+1}/3")
            await agent.run_cycle()
            if i < 2:
                await asyncio.sleep(2)
        
        print(agent.status_report())
        
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
    finally:
        agent.save_state()
        print("💾 State saved")


if __name__ == "__main__":
    asyncio.run(main())
