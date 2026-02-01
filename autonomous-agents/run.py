#!/usr/bin/env python3
"""
AURA Launcher - Start the agent with dashboard
"""

import os
import sys
import argparse

# Fix Windows encoding for emojis
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def main():
    parser = argparse.ArgumentParser(description='AURA - Autonomous Universal Revenue Agent')
    parser.add_argument('--mode', choices=['api', 'agent', 'demo'], default='api',
                        help='Run mode: api (dashboard), agent (standalone), demo (quick test)')
    parser.add_argument('--host', default='0.0.0.0', help='API host')
    parser.add_argument('--port', type=int, default=8000, help='API port')
    parser.add_argument('--cycles', type=int, default=3, help='Number of cycles for demo mode')
    args = parser.parse_args()

    if args.mode == 'api':
        # Run FastAPI server with dashboard
        import uvicorn
        print("🚀 Starting AURA Dashboard...")
        print(f"📊 Dashboard: http://localhost:{args.port}")
        print(f"📚 API Docs: http://localhost:{args.port}/docs")
        uvicorn.run("api:app", host=args.host, port=args.port, reload=False)
        
    elif args.mode == 'agent':
        # Run agent standalone
        import asyncio
        from agent import AURAAgent, set_agent
        
        print("🤖 Starting AURA Agent (standalone mode)...")
        agent = AURAAgent("AURA-001")
        set_agent(agent)
        asyncio.run(agent.run())
        
    elif args.mode == 'demo':
        # Quick demo
        import asyncio
        from agent import AURAAgent
        
        print("🎮 AURA Demo Mode")
        print("=" * 50)
        
        agent = AURAAgent("AURA-DEMO", demo_mode=True)
        
        async def run_demo():
            print(agent.status_report())
            
            for i in range(args.cycles):
                print(f"\n📍 Demo Cycle {i+1}/{args.cycles}")
                await agent.run_cycle()
                if i < args.cycles - 1:
                    await asyncio.sleep(2)
            
            print("\n" + agent.status_report())
            print("✅ Demo complete!")
        
        asyncio.run(run_demo())


if __name__ == '__main__':
    main()
