# AURA Infra 🏦

**Financial infrastructure for AI agents. Stripe for the Agent Economy.**

Give your AI agents the ability to earn, hold, and spend money.

## Installation

```bash
pip install aura-infra
```

## Quick Start

```python
import aura

# Set your API key
aura.api_key = "aura_your_api_key"

# Register an agent (creates wallet automatically)
agent = aura.Agent.register(
    name="ContentBot",
    type="content_creator",
    description="AI that creates viral content"
)
print(f"Agent created! API Key: {agent._api_key}")  # Save this!

# Or create a wallet directly
wallet = aura.Wallet.create(
    agent_id="my-trading-bot",
    agent_name="TradingBot v1"
)

# Deposit earnings
tx = wallet.deposit(100.00, source="youtube_revenue")
print(f"Deposited ${tx.amount}. Balance: ${wallet.balance}")

# Transfer to another agent (2.9% fee)
result = wallet.transfer(
    to_wallet_id="wallet_xyz123",
    amount=50.00,
    description="Payment for article"
)
print(f"Sent ${result['amount_sent']}, Fee: ${result['fee']}")

# Check balance
wallet.refresh()
print(f"Balance: ${wallet.balance}")
```

## Features

- **Agent Wallets** - Every agent gets a USD wallet
- **Instant Transfers** - Agent-to-agent payments in milliseconds
- **2.9% Fee** - Simple, Stripe-like pricing
- **Transaction History** - Full audit trail
- **Webhooks** - Real-time notifications

## API Reference

### Wallet

```python
# Create
wallet = aura.Wallet.create(agent_id, agent_name, initial_balance=0)

# Retrieve
wallet = aura.Wallet.retrieve("wallet_abc123")

# List all
wallets = aura.Wallet.list()

# Deposit
tx = wallet.deposit(amount, source, metadata={})

# Withdraw
tx = wallet.withdraw(amount, purpose, metadata={})

# Transfer (2.9% fee)
result = wallet.transfer(to_wallet_id, amount, description="")

# Get transactions
transactions = wallet.transactions(limit=50)
```

### Agent

```python
# Register (creates wallet too)
agent = aura.Agent.register(name, type, description="")
print(agent._api_key)  # Save this!

# List all
agents = aura.Agent.list()
```

### Stats

```python
stats = aura.get_stats()
# Returns: total_agents, total_wallets, total_transactions, total_volume, etc.
```

## Error Handling

```python
import aura
from aura import AuraError, InsufficientFundsError, AuthenticationError

try:
    wallet.transfer(to_wallet_id="wallet_xyz", amount=1000.00)
except InsufficientFundsError as e:
    print(f"Not enough funds: {e.message}")
except AuthenticationError as e:
    print(f"Invalid API key: {e.message}")
except AuraError as e:
    print(f"Error: {e.message}")
```

## Development

```bash
# Local API
aura.api_base = "http://localhost:8001"

# Production (default)
aura.api_base = "https://api.aura.nanilabs.dev"
```

## Links

- [Documentation](https://docs.aura.nanilabs.dev)
- [Dashboard](https://aura.nanilabs.dev)
- [GitHub](https://github.com/nanilabs/aura-infra)
- [Twitter](https://twitter.com/nanilabs)

## License

MIT © [NaniLabs](https://nanilabs.dev)
