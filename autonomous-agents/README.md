# 🤖 AURA - Autonomous Universal Revenue Agent

An AI agent that thinks, decides, and earns money autonomously.

![AURA Dashboard](https://img.shields.io/badge/status-demo-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![License](https://img.shields.io/badge/license-MIT-purple)

## 🌟 What is AURA?

AURA is a self-directed AI agent designed to generate revenue through various strategies:

- **📝 Content Creation** - Writes blog posts, tweets, and articles
- **💼 Freelance Services** - Completes coding, research, and writing tasks
- **📊 Research & Analysis** - Generates valuable market reports

The agent thinks about what to do, executes strategies, and learns from results - all autonomously.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd autonomous-agents
pip install -r requirements.txt
```

### 2. Run Demo Mode

```bash
python run.py --mode demo
```

This runs 3 cycles showing the agent making decisions and "earning" money.

### 3. Run Dashboard

```bash
python run.py --mode api
```

Open http://localhost:8000 to see the dashboard!

## 📊 Dashboard Features

- **Real-time Status** - See agent state, balance, and activity
- **Start/Stop Control** - Control the agent from the UI
- **Activity Feed** - Watch the agent think and earn
- **Task Submission** - Submit tasks for the agent to complete
- **Transaction History** - Track all earnings and spending
- **Generated Content** - View content the agent creates

## 🧠 How It Works

### The Agent Loop

```
┌─────────────────────────────────────────┐
│                                         │
│   1. THINK                              │
│      └─> Use Claude to analyze state    │
│          and decide what to do          │
│                                         │
│   2. DECIDE                             │
│      └─> Pick a revenue strategy        │
│          based on reasoning             │
│                                         │
│   3. EXECUTE                            │
│      └─> Run the strategy               │
│          (content, tasks, research)     │
│                                         │
│   4. EARN                               │
│      └─> Record revenue                 │
│          and update balance             │
│                                         │
│   5. LEARN                              │
│      └─> Remember what worked           │
│          for future decisions           │
│                                         │
└─────────────────────────────────────────┘
```

### Revenue Strategies

| Strategy | Description | Revenue Range |
|----------|-------------|---------------|
| Content Creation | Blog posts, tweets, articles | $0.50 - $3.00 |
| Freelance Services | Code review, writing, research | $2.00 - $10.00 |
| Research Analysis | Market reports, analysis | $8.00 - $18.00 |

## ⚙️ Configuration

Copy `.env.example` to `.env` and configure:

```env
# AI Provider (optional - runs in demo mode without it)
ANTHROPIC_API_KEY=your_key_here

# Agent Settings
AGENT_NAME=AURA-001
DAILY_REVENUE_TARGET=10.0
CYCLE_INTERVAL_SECONDS=60
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Get agent status |
| `/api/start` | POST | Start the agent |
| `/api/stop` | POST | Stop the agent |
| `/api/cycle` | POST | Run single cycle |
| `/api/balance` | GET | Get current balance |
| `/api/transactions` | GET | Get transaction history |
| `/api/activity` | GET | Get activity log |
| `/api/tasks` | GET/POST | List or submit tasks |
| `/api/content` | GET | Get generated content |

## 📁 Project Structure

```
autonomous-agents/
├── src/
│   ├── agent.py          # Main agent logic
│   ├── api.py            # FastAPI backend
│   ├── db.py             # SQLite database
│   ├── dashboard/
│   │   └── index.html    # Web dashboard
│   └── strategies/
│       ├── content.py    # Content creation
│       ├── freelance.py  # Freelance services
│       └── research.py   # Research & analysis
├── data/                 # Agent state & database
├── run.py               # Launcher script
├── requirements.txt
├── .env                 # Configuration
└── README.md
```

## 🎮 Demo Mode

In demo mode (default when no API key is set):
- Agent simulates Claude API calls
- Revenue is simulated but realistic
- All features work for demonstration
- Great for testing and development

## 🔮 Future Ideas

- [ ] Real Twitter/X integration for posting
- [ ] Stripe integration for actual payments
- [ ] Multi-agent collaboration
- [ ] Cryptocurrency wallet integration
- [ ] Advanced learning and optimization
- [ ] Marketplace for agent services

## 📄 License

MIT License - Feel free to use, modify, and build upon this!

---

Built with 💜 by AURA itself (with a little help from humans)
