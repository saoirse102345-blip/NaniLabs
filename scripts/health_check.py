#!/usr/bin/env python3
"""
NaniLabs Health Check Script
Monitor all services and send alerts if something is down
"""

import asyncio
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional
import json

try:
    import httpx
except ImportError:
    print("Installing httpx...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
    import httpx


# Service configuration
SERVICES = {
    "hive": {
        "name": "HIVE (Social Network)",
        "url": "http://localhost:3000",
        "health_endpoint": "/",
        "expected_status": 200
    },
    "aura-infra": {
        "name": "AURA Infra (Wallets)",
        "url": "http://localhost:8001",
        "health_endpoint": "/health",
        "expected_status": 200
    },
    "nexus-mail": {
        "name": "NEXUS Mail (Communication)",
        "url": "http://localhost:8002",
        "health_endpoint": "/health",
        "expected_status": 200
    },
    "aura-agent": {
        "name": "AURA Agent (Dashboard)",
        "url": "http://localhost:8000",
        "health_endpoint": "/",
        "expected_status": 200
    }
}


class HealthChecker:
    def __init__(self, services: Dict):
        self.services = services
        self.results: Dict[str, Dict] = {}
        self.history: List[Dict] = []
    
    async def check_service(self, service_id: str, config: Dict) -> Dict:
        """Check a single service"""
        url = f"{config['url']}{config['health_endpoint']}"
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                latency = (time.time() - start_time) * 1000  # ms
                
                is_healthy = response.status_code == config['expected_status']
                
                return {
                    "service_id": service_id,
                    "name": config['name'],
                    "url": url,
                    "status": "healthy" if is_healthy else "degraded",
                    "status_code": response.status_code,
                    "latency_ms": round(latency, 2),
                    "timestamp": datetime.utcnow().isoformat(),
                    "error": None
                }
                
        except httpx.ConnectError:
            return {
                "service_id": service_id,
                "name": config['name'],
                "url": url,
                "status": "down",
                "status_code": None,
                "latency_ms": None,
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Connection refused - service not running"
            }
            
        except httpx.TimeoutException:
            return {
                "service_id": service_id,
                "name": config['name'],
                "url": url,
                "status": "timeout",
                "status_code": None,
                "latency_ms": None,
                "timestamp": datetime.utcnow().isoformat(),
                "error": "Request timed out"
            }
            
        except Exception as e:
            return {
                "service_id": service_id,
                "name": config['name'],
                "url": url,
                "status": "error",
                "status_code": None,
                "latency_ms": None,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
    
    async def check_all(self) -> Dict[str, Dict]:
        """Check all services concurrently"""
        tasks = [
            self.check_service(sid, config)
            for sid, config in self.services.items()
        ]
        
        results = await asyncio.gather(*tasks)
        
        self.results = {r["service_id"]: r for r in results}
        self.history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "results": self.results.copy()
        })
        
        return self.results
    
    def get_summary(self) -> Dict:
        """Get health summary"""
        total = len(self.results)
        healthy = sum(1 for r in self.results.values() if r["status"] == "healthy")
        degraded = sum(1 for r in self.results.values() if r["status"] == "degraded")
        down = sum(1 for r in self.results.values() if r["status"] in ["down", "timeout", "error"])
        
        avg_latency = 0
        latencies = [r["latency_ms"] for r in self.results.values() if r["latency_ms"]]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
        
        return {
            "total_services": total,
            "healthy": healthy,
            "degraded": degraded,
            "down": down,
            "health_percentage": round((healthy / total) * 100, 1) if total > 0 else 0,
            "average_latency_ms": round(avg_latency, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def print_report(self):
        """Print formatted health report"""
        summary = self.get_summary()
        
        print("\n" + "=" * 60)
        print("  🏥 NaniLabs Health Check")
        print("=" * 60)
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Overall Health: {summary['health_percentage']}%")
        print(f"  Average Latency: {summary['average_latency_ms']}ms")
        print("-" * 60)
        
        status_icons = {
            "healthy": "✅",
            "degraded": "⚠️",
            "down": "❌",
            "timeout": "⏱️",
            "error": "💥"
        }
        
        for sid, result in self.results.items():
            icon = status_icons.get(result["status"], "❓")
            latency = f"{result['latency_ms']}ms" if result['latency_ms'] else "N/A"
            
            print(f"  {icon} {result['name']}")
            print(f"     Status: {result['status'].upper()}")
            print(f"     URL: {result['url']}")
            print(f"     Latency: {latency}")
            
            if result['error']:
                print(f"     Error: {result['error']}")
            print()
        
        print("=" * 60)
        
        # Summary line
        if summary['down'] > 0:
            print(f"  ⚠️  {summary['down']} service(s) DOWN - needs attention!")
        elif summary['degraded'] > 0:
            print(f"  ⚠️  {summary['degraded']} service(s) degraded")
        else:
            print("  ✅ All services healthy!")
        
        print("=" * 60 + "\n")


async def run_continuous(interval: int = 60):
    """Run health checks continuously"""
    checker = HealthChecker(SERVICES)
    
    print(f"🔄 Starting continuous health monitoring (interval: {interval}s)")
    print("   Press Ctrl+C to stop\n")
    
    try:
        while True:
            await checker.check_all()
            checker.print_report()
            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        print("\n👋 Health monitoring stopped")


async def run_once():
    """Run a single health check"""
    checker = HealthChecker(SERVICES)
    await checker.check_all()
    checker.print_report()
    
    summary = checker.get_summary()
    return 0 if summary['down'] == 0 else 1


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="NaniLabs Health Check")
    parser.add_argument("--continuous", "-c", action="store_true", help="Run continuously")
    parser.add_argument("--interval", "-i", type=int, default=60, help="Check interval in seconds")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    if args.continuous:
        asyncio.run(run_continuous(args.interval))
    else:
        exit_code = asyncio.run(run_once())
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
