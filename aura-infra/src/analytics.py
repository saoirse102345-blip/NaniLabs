"""
AURA Infra - Analytics Module
Track platform metrics, revenue, and growth
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import json


@dataclass
class DailyMetrics:
    """Metrics for a single day"""
    date: str
    transactions_count: int = 0
    transaction_volume: float = 0.0
    deposits_count: int = 0
    deposits_volume: float = 0.0
    withdrawals_count: int = 0
    withdrawals_volume: float = 0.0
    transfers_count: int = 0
    transfers_volume: float = 0.0
    fees_collected: float = 0.0
    new_wallets: int = 0
    new_agents: int = 0
    active_wallets: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "transactions_count": self.transactions_count,
            "transaction_volume": self.transaction_volume,
            "deposits_count": self.deposits_count,
            "deposits_volume": self.deposits_volume,
            "withdrawals_count": self.withdrawals_count,
            "withdrawals_volume": self.withdrawals_volume,
            "transfers_count": self.transfers_count,
            "transfers_volume": self.transfers_volume,
            "fees_collected": self.fees_collected,
            "new_wallets": self.new_wallets,
            "new_agents": self.new_agents,
            "active_wallets": self.active_wallets
        }


class AnalyticsTracker:
    """
    Track and calculate platform analytics
    """
    
    def __init__(self):
        self.daily_metrics: Dict[str, DailyMetrics] = {}
        self.real_time_counters = {
            "transactions_today": 0,
            "volume_today": 0.0,
            "fees_today": 0.0,
            "active_wallets_today": set()
        }
        self._today = datetime.now().date().isoformat()
    
    def _get_today(self) -> str:
        """Get current date string, resetting counters if day changed"""
        today = datetime.now().date().isoformat()
        if today != self._today:
            self._save_daily_metrics()
            self._today = today
            self.real_time_counters = {
                "transactions_today": 0,
                "volume_today": 0.0,
                "fees_today": 0.0,
                "active_wallets_today": set()
            }
        return today
    
    def _save_daily_metrics(self):
        """Save current day's metrics"""
        if self._today not in self.daily_metrics:
            self.daily_metrics[self._today] = DailyMetrics(date=self._today)
        
        metrics = self.daily_metrics[self._today]
        metrics.transactions_count = self.real_time_counters["transactions_today"]
        metrics.transaction_volume = self.real_time_counters["volume_today"]
        metrics.fees_collected = self.real_time_counters["fees_today"]
        metrics.active_wallets = len(self.real_time_counters["active_wallets_today"])
    
    def track_transaction(
        self,
        tx_type: str,
        amount: float,
        wallet_id: str,
        fee: float = 0.0
    ):
        """Track a transaction"""
        self._get_today()
        
        self.real_time_counters["transactions_today"] += 1
        self.real_time_counters["volume_today"] += amount
        self.real_time_counters["fees_today"] += fee
        self.real_time_counters["active_wallets_today"].add(wallet_id)
        
        if self._today not in self.daily_metrics:
            self.daily_metrics[self._today] = DailyMetrics(date=self._today)
        
        metrics = self.daily_metrics[self._today]
        
        if tx_type == "deposit":
            metrics.deposits_count += 1
            metrics.deposits_volume += amount
        elif tx_type == "withdrawal":
            metrics.withdrawals_count += 1
            metrics.withdrawals_volume += amount
        elif tx_type == "transfer":
            metrics.transfers_count += 1
            metrics.transfers_volume += amount
            metrics.fees_collected += fee
    
    def track_wallet_created(self):
        """Track new wallet creation"""
        today = self._get_today()
        if today not in self.daily_metrics:
            self.daily_metrics[today] = DailyMetrics(date=today)
        self.daily_metrics[today].new_wallets += 1
    
    def track_agent_registered(self):
        """Track new agent registration"""
        today = self._get_today()
        if today not in self.daily_metrics:
            self.daily_metrics[today] = DailyMetrics(date=today)
        self.daily_metrics[today].new_agents += 1
    
    def get_today_metrics(self) -> Dict[str, Any]:
        """Get real-time metrics for today"""
        self._get_today()
        return {
            "date": self._today,
            "transactions_count": self.real_time_counters["transactions_today"],
            "transaction_volume": self.real_time_counters["volume_today"],
            "fees_collected": self.real_time_counters["fees_today"],
            "active_wallets": len(self.real_time_counters["active_wallets_today"])
        }
    
    def get_metrics_range(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get metrics for a date range"""
        if end_date is None:
            end_date = datetime.now().date().isoformat()
        
        if start_date is None:
            start = datetime.fromisoformat(end_date) - timedelta(days=days)
            start_date = start.date().isoformat()
        
        result = []
        current = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        
        while current <= end:
            date_str = current.date().isoformat()
            if date_str in self.daily_metrics:
                result.append(self.daily_metrics[date_str].to_dict())
            else:
                # Return zeros for missing days
                result.append(DailyMetrics(date=date_str).to_dict())
            current += timedelta(days=1)
        
        return result
    
    def get_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get summary analytics"""
        metrics = self.get_metrics_range(days=days)
        
        total_transactions = sum(m["transactions_count"] for m in metrics)
        total_volume = sum(m["transaction_volume"] for m in metrics)
        total_fees = sum(m["fees_collected"] for m in metrics)
        total_new_wallets = sum(m["new_wallets"] for m in metrics)
        total_new_agents = sum(m["new_agents"] for m in metrics)
        
        # Calculate averages
        avg_daily_volume = total_volume / len(metrics) if metrics else 0
        avg_daily_transactions = total_transactions / len(metrics) if metrics else 0
        
        # Calculate growth (compare last 7 days to previous 7 days)
        recent_volume = sum(m["transaction_volume"] for m in metrics[-7:])
        previous_volume = sum(m["transaction_volume"] for m in metrics[-14:-7])
        volume_growth = ((recent_volume - previous_volume) / previous_volume * 100) if previous_volume > 0 else 0
        
        return {
            "period_days": days,
            "total_transactions": total_transactions,
            "total_volume": round(total_volume, 2),
            "total_fees_collected": round(total_fees, 2),
            "total_new_wallets": total_new_wallets,
            "total_new_agents": total_new_agents,
            "average_daily_volume": round(avg_daily_volume, 2),
            "average_daily_transactions": round(avg_daily_transactions, 2),
            "volume_growth_7d_percent": round(volume_growth, 2),
            "today": self.get_today_metrics()
        }
    
    def get_revenue_report(self, days: int = 30) -> Dict[str, Any]:
        """Get revenue-focused report"""
        metrics = self.get_metrics_range(days=days)
        
        total_fees = sum(m["fees_collected"] for m in metrics)
        daily_fees = [{"date": m["date"], "revenue": m["fees_collected"]} for m in metrics]
        
        # Project monthly revenue
        avg_daily_revenue = total_fees / len(metrics) if metrics else 0
        projected_monthly = avg_daily_revenue * 30
        projected_yearly = avg_daily_revenue * 365
        
        return {
            "period_days": days,
            "total_revenue": round(total_fees, 2),
            "average_daily_revenue": round(avg_daily_revenue, 2),
            "projected_monthly_revenue": round(projected_monthly, 2),
            "projected_yearly_revenue": round(projected_yearly, 2),
            "daily_revenue": daily_fees,
            "currency": "USD"
        }


# Global analytics instance
analytics = AnalyticsTracker()


# Convenience functions
def track_deposit(amount: float, wallet_id: str):
    analytics.track_transaction("deposit", amount, wallet_id)


def track_withdrawal(amount: float, wallet_id: str):
    analytics.track_transaction("withdrawal", amount, wallet_id)


def track_transfer(amount: float, wallet_id: str, fee: float):
    analytics.track_transaction("transfer", amount, wallet_id, fee)


def track_new_wallet():
    analytics.track_wallet_created()


def track_new_agent():
    analytics.track_agent_registered()
