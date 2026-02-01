"""
AURA Infra API Tests
"""

import pytest
import httpx
import asyncio
from typing import Dict, Any

BASE_URL = "http://localhost:8001"


class TestHealthEndpoints:
    """Test health and status endpoints"""
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/")
            assert response.status_code == 200
            data = response.json()
            assert data["service"] == "AURA Infra"
            assert data["status"] == "running"
    
    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_stats_endpoint(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/stats")
            assert response.status_code == 200
            data = response.json()
            assert "total_wallets" in data
            assert "total_transactions" in data


class TestWalletEndpoints:
    """Test wallet CRUD operations"""
    
    @pytest.fixture
    def wallet_data(self) -> Dict[str, Any]:
        import uuid
        return {
            "agent_id": f"test_agent_{uuid.uuid4().hex[:8]}",
            "agent_name": "TestBot",
            "initial_balance": 100.0
        }
    
    @pytest.mark.asyncio
    async def test_create_wallet(self, wallet_data):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/wallets",
                json=wallet_data
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "wallet" in data
            assert data["wallet"]["agent_name"] == wallet_data["agent_name"]
            assert data["wallet"]["balance"] == wallet_data["initial_balance"]
    
    @pytest.mark.asyncio
    async def test_list_wallets(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/wallets")
            assert response.status_code == 200
            data = response.json()
            assert "wallets" in data
            assert isinstance(data["wallets"], list)
    
    @pytest.mark.asyncio
    async def test_get_wallet(self, wallet_data):
        async with httpx.AsyncClient() as client:
            # First create a wallet
            create_response = await client.post(
                f"{BASE_URL}/wallets",
                json=wallet_data
            )
            wallet_id = create_response.json()["wallet"]["id"]
            
            # Then retrieve it
            response = await client.get(f"{BASE_URL}/wallets/{wallet_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == wallet_id
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_wallet(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/wallets/nonexistent_wallet")
            assert response.status_code == 404


class TestTransactionEndpoints:
    """Test deposit, withdraw, and transfer operations"""
    
    @pytest.fixture
    async def test_wallet(self) -> Dict[str, Any]:
        """Create a test wallet and return its data"""
        import uuid
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/wallets",
                json={
                    "agent_id": f"tx_test_{uuid.uuid4().hex[:8]}",
                    "agent_name": "TransactionTestBot",
                    "initial_balance": 1000.0
                }
            )
            return response.json()["wallet"]
    
    @pytest.mark.asyncio
    async def test_deposit(self, test_wallet):
        wallet_id = test_wallet["id"]
        initial_balance = test_wallet["balance"]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/wallets/{wallet_id}/deposit",
                json={
                    "amount": 500.0,
                    "source": "test_deposit"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["new_balance"] == initial_balance + 500.0
    
    @pytest.mark.asyncio
    async def test_deposit_negative_amount(self, test_wallet):
        wallet_id = test_wallet["id"]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/wallets/{wallet_id}/deposit",
                json={
                    "amount": -100.0,
                    "source": "invalid"
                }
            )
            assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_withdraw(self, test_wallet):
        wallet_id = test_wallet["id"]
        initial_balance = test_wallet["balance"]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/wallets/{wallet_id}/withdraw",
                json={
                    "amount": 100.0,
                    "purpose": "test_withdrawal"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["new_balance"] == initial_balance - 100.0
    
    @pytest.mark.asyncio
    async def test_withdraw_insufficient_funds(self, test_wallet):
        wallet_id = test_wallet["id"]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/wallets/{wallet_id}/withdraw",
                json={
                    "amount": 999999.0,
                    "purpose": "should_fail"
                }
            )
            assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_transfer(self):
        import uuid
        
        async with httpx.AsyncClient() as client:
            # Create source wallet
            source_response = await client.post(
                f"{BASE_URL}/wallets",
                json={
                    "agent_id": f"source_{uuid.uuid4().hex[:8]}",
                    "agent_name": "SourceBot",
                    "initial_balance": 1000.0
                }
            )
            source_wallet = source_response.json()["wallet"]
            
            # Create destination wallet
            dest_response = await client.post(
                f"{BASE_URL}/wallets",
                json={
                    "agent_id": f"dest_{uuid.uuid4().hex[:8]}",
                    "agent_name": "DestBot",
                    "initial_balance": 0.0
                }
            )
            dest_wallet = dest_response.json()["wallet"]
            
            # Transfer
            transfer_amount = 100.0
            response = await client.post(
                f"{BASE_URL}/wallets/{source_wallet['id']}/transfer",
                json={
                    "to_wallet_id": dest_wallet["id"],
                    "amount": transfer_amount,
                    "description": "test_transfer"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["amount_sent"] == transfer_amount
            
            # Check fee (2.9%)
            expected_fee = transfer_amount * 0.029
            assert abs(data["fee"] - expected_fee) < 0.01
            
            # Check received amount
            expected_received = transfer_amount - expected_fee
            assert abs(data["amount_received"] - expected_received) < 0.01


class TestAgentEndpoints:
    """Test agent registration and listing"""
    
    @pytest.mark.asyncio
    async def test_register_agent(self):
        import uuid
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{BASE_URL}/agents/register",
                json={
                    "name": f"TestAgent_{uuid.uuid4().hex[:6]}",
                    "type": "content_creator",
                    "description": "Test agent for API testing"
                }
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "agent" in data
            assert "wallet" in data
            assert "api_key" in data
            assert data["api_key"].startswith("aura_")
    
    @pytest.mark.asyncio
    async def test_list_agents(self):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/agents")
            assert response.status_code == 200
            data = response.json()
            assert "agents" in data
            assert isinstance(data["agents"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
