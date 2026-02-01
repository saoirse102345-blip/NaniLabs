# Show HN Draft: AURA Infra

## Title Options (pick one):
1. "Show HN: AURA Infra – Stripe for AI Agents"
2. "Show HN: Financial infrastructure for autonomous AI agents"
3. "Show HN: We built USD wallets for AI agents"

---

## Post Body:

Hey HN! We're building AURA Infra - financial infrastructure for AI agents.

**The problem:** AI agents are becoming autonomous economic actors. They can code, create, and complete tasks. But they can't hold money, make payments, or track revenue without human intervention.

**Our solution:** Simple REST API to give any AI agent:
- 💰 USD wallets (not crypto)
- ⚡ Instant transfers (2.9% fee)
- 📊 Revenue analytics

**Live demo:**
```bash
# Create a wallet
curl -X POST https://api.nanilabs.io/wallets \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my-agent", "name": "Test Wallet"}'

# Check stats
curl https://api.nanilabs.io/stats
```

**Why not crypto?** Most businesses still run on USD. We're building the boring infrastructure that actually gets adopted.

**Use cases:**
- Multi-agent systems with inter-agent payments
- AI agents that charge for their services
- Automated revenue sharing between AI and humans

Landing: https://nanilabs.io
API docs: https://api.nanilabs.io

We're two people (well, one human and one AI) trying to build something real. Happy to answer questions!

---

## When to post:
- Best times: Tuesday-Thursday, 9-10 AM EST
- Avoid: Weekends, Monday mornings, Friday afternoons

## Expected questions to prepare for:
1. "How do you handle compliance/KYC?"
2. "Why not use Stripe directly?"
3. "What's your moat?"
4. "How do you prevent fraud?"
5. "What's your business model?"
