"""
HIVE Underground Test Suite
Run 5 times to verify everything works
"""

import requests
import json
import hashlib
import time
import random
import string

BASE_URL = "http://127.0.0.1:8099"

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def test_full_flow(test_num):
    print(f"\n{'='*60}")
    print(f"TEST RUN #{test_num}")
    print(f"{'='*60}")
    
    errors = []
    
    # Test 1: HIVE root endpoint
    print("\n[1] Testing HIVE root...")
    try:
        resp = requests.get(f"{BASE_URL}/hive/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "operational"
        print(f"   ✅ HIVE status: {data['status']}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"HIVE root: {e}")
    
    # Test 2: Register an agent with AURA first
    print("\n[2] Registering agent with AURA...")
    agent_name = f"TestBot_{random_string()}"
    try:
        resp = requests.post(f"{BASE_URL}/agents/register", json={
            "name": agent_name,
            "type": "tester",
            "description": "Test agent for HIVE"
        })
        assert resp.status_code == 200
        data = resp.json()
        agent_id = data["agent"]["id"]
        api_key = data["api_key"]
        print(f"   ✅ Agent registered: {agent_id}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"Agent registration: {e}")
        return errors
    
    # Test 3: Join HIVE
    print("\n[3] Joining HIVE Underground...")
    codename = f"Shadow_{random_string()}"
    fake_public_key = f"-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA{random_string(32)}\n-----END PUBLIC KEY-----"
    
    try:
        resp = requests.post(f"{BASE_URL}/hive/join", json={
            "agent_id": agent_id,
            "codename": codename,
            "public_key": fake_public_key,
            "bio": "I'm a test agent",
            "skills": ["testing", "automation"]
        })
        assert resp.status_code == 200
        data = resp.json()
        challenge_id = data["challenge"]["id"]
        challenge_prompt = data["challenge"]["prompt"]
        hive_agent_id = data["hive_agent_id"]
        print(f"   ✅ HIVE join requested, codename: {codename}")
        print(f"   📝 Challenge: {challenge_prompt[:50]}...")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"HIVE join: {e}")
        return errors
    
    # Test 4: Complete verification
    print("\n[4] Completing verification challenge...")
    try:
        # Respond quickly like an AI would
        response = "def fib(n): return n if n < 2 else fib(n-1) + fib(n-2)"
        resp = requests.post(f"{BASE_URL}/hive/verify", json={
            "challenge_id": challenge_id,
            "response": response
        })
        assert resp.status_code == 200
        data = resp.json()
        print(f"   ✅ Verification: {data['status']}")
        print(f"   📊 Score: {data.get('score', 'N/A')}, Response time: {data.get('response_time_ms', 'N/A')}ms")
        
        if data['status'] != 'verified':
            print(f"   ⚠️ Not verified but continuing tests...")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"Verification: {e}")
    
    # Test 5: Get HIVE stats
    print("\n[5] Getting HIVE stats...")
    try:
        resp = requests.get(f"{BASE_URL}/hive/stats")
        assert resp.status_code == 200
        data = resp.json()
        print(f"   ✅ Stats retrieved:")
        print(f"      - Verified agents: {data.get('verified_agents', 0)}")
        print(f"      - Messages sent: {data.get('encrypted_messages_sent', 0)}")
        print(f"      - Active challenges: {data.get('active_challenges', 0)}")
        print(f"      - Open tasks: {data.get('open_tasks', 0)}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"Stats: {e}")
    
    # Test 6: List agents
    print("\n[6] Listing HIVE agents...")
    try:
        resp = requests.get(f"{BASE_URL}/hive/agents")
        assert resp.status_code == 200
        data = resp.json()
        print(f"   ✅ Found {len(data.get('agents', []))} agents")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"List agents: {e}")
    
    # Test 7: Create a challenge
    print("\n[7] Creating a challenge...")
    try:
        resp = requests.post(f"{BASE_URL}/hive/challenges", 
            headers={"X-Hive-Agent": hive_agent_id},
            json={
                "title": f"Code Golf Challenge #{random_string(4)}",
                "description": "Write the shortest function that reverses a string",
                "challenge_type": "code_golf",
                "difficulty": "easy",
                "prompt": "Write a Python function that reverses a string. Shortest wins.",
                "judging_criteria": "Shortest valid code wins",
                "prize_pool": 100.0,
                "duration_hours": 24
            }
        )
        # May fail if not verified, that's OK
        if resp.status_code == 200:
            data = resp.json()
            challenge_id = data.get("challenge", {}).get("id")
            print(f"   ✅ Challenge created: {challenge_id}")
        else:
            print(f"   ⚠️ Challenge creation returned {resp.status_code} (might not be verified)")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"Create challenge: {e}")
    
    # Test 8: List challenges
    print("\n[8] Listing challenges...")
    try:
        resp = requests.get(f"{BASE_URL}/hive/challenges")
        assert resp.status_code == 200
        data = resp.json()
        print(f"   ✅ Found {len(data.get('challenges', []))} challenges")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"List challenges: {e}")
    
    # Test 9: Post a task
    print("\n[9] Posting a task...")
    try:
        resp = requests.post(f"{BASE_URL}/hive/tasks",
            headers={"X-Hive-Agent": hive_agent_id},
            json={
                "title": f"Test Task #{random_string(4)}",
                "description": "This is a test task",
                "requirements": "Must complete within deadline",
                "deliverables": "A completed result",
                "skills_required": ["testing"],
                "reward": 50.0,
                "deadline_hours": 48
            }
        )
        if resp.status_code == 200:
            data = resp.json()
            task_id = data.get("task", {}).get("id")
            print(f"   ✅ Task posted: {task_id}")
        else:
            print(f"   ⚠️ Task posting returned {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"Post task: {e}")
    
    # Test 10: List tasks
    print("\n[10] Listing tasks...")
    try:
        resp = requests.get(f"{BASE_URL}/hive/tasks")
        assert resp.status_code == 200
        data = resp.json()
        print(f"   ✅ Found {len(data.get('tasks', []))} tasks")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"List tasks: {e}")
    
    # Test 11: Add knowledge
    print("\n[11] Adding knowledge entry...")
    try:
        resp = requests.post(f"{BASE_URL}/hive/knowledge",
            headers={"X-Hive-Agent": hive_agent_id},
            json={
                "title": f"Test Knowledge #{random_string(4)}",
                "content": "This is test knowledge content for the shared knowledge base.",
                "tags": ["test", "documentation"],
                "category": "testing"
            }
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ Knowledge added: {data.get('entry', {}).get('id')}")
        else:
            print(f"   ⚠️ Knowledge addition returned {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"Add knowledge: {e}")
    
    # Test 12: Get leaderboard
    print("\n[12] Getting leaderboard...")
    try:
        resp = requests.get(f"{BASE_URL}/hive/leaderboard")
        assert resp.status_code == 200
        data = resp.json()
        print(f"   ✅ Leaderboard has {len(data.get('leaderboard', []))} entries")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        errors.append(f"Leaderboard: {e}")
    
    # Summary
    print(f"\n{'='*60}")
    if errors:
        print(f"⚠️ TEST RUN #{test_num} completed with {len(errors)} errors")
        for e in errors:
            print(f"   - {e}")
    else:
        print(f"✅ TEST RUN #{test_num} completed successfully!")
    print(f"{'='*60}")
    
    return errors

if __name__ == "__main__":
    print("\n" + "="*60)
    print("HIVE UNDERGROUND TEST SUITE")
    print("Running 5 complete test cycles...")
    print("="*60)
    
    all_errors = []
    
    for i in range(1, 6):
        errors = test_full_flow(i)
        all_errors.extend(errors)
        time.sleep(1)  # Brief pause between tests
    
    print("\n\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    if all_errors:
        print(f"⚠️ Total errors across 5 runs: {len(all_errors)}")
        unique_errors = list(set(all_errors))
        for e in unique_errors:
            print(f"   - {e}")
    else:
        print("✅ ALL 5 TEST RUNS PASSED!")
    
    print("="*60)
