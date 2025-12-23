"""
Cost Guardrail: Cross-session cost management and limits.
Implements budget tracking, alerts, and automatic throttling.
"""
import os
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field


@dataclass
class CostBudget:
    """Cost budget configuration."""
    budget_id: str
    scope: str  # global, session, user
    scope_id: Optional[str] = None  # session_id or user_id
    
    # Limits
    daily_limit: float = 10.0
    weekly_limit: float = 50.0
    monthly_limit: float = 200.0
    per_run_limit: float = 1.0
    
    # Current usage
    daily_used: float = 0.0
    weekly_used: float = 0.0
    monthly_used: float = 0.0
    
    # Tracking
    last_reset_daily: str = ""
    last_reset_weekly: str = ""
    last_reset_monthly: str = ""
    
    # Actions
    on_limit_reached: str = "throttle"  # throttle, block, warn
    throttle_factor: float = 0.5  # Reduce capacity by this factor
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def check_limits(self) -> Tuple[bool, str]:
        """Check if any limits are exceeded."""
        if self.daily_used >= self.daily_limit:
            return True, "daily"
        if self.weekly_used >= self.weekly_limit:
            return True, "weekly"
        if self.monthly_used >= self.monthly_limit:
            return True, "monthly"
        return False, ""
    
    def check_run_budget(self, estimated_cost: float) -> bool:
        """Check if a run can proceed."""
        if estimated_cost > self.per_run_limit:
            return False
        
        exceeded, _ = self.check_limits()
        return not exceeded


@dataclass
class CostEvent:
    """A cost event."""
    event_id: str
    run_id: str
    session_id: Optional[str]
    user_id: Optional[str]
    
    # Cost details
    cost: float
    cost_type: str  # token, api, compute, storage
    
    # Context
    operation: str
    model: Optional[str] = None
    tokens_in: int = 0
    tokens_out: int = 0
    
    # Timestamp
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CostDecision:
    """Cost guardrail decision."""
    allowed: bool
    run_id: str
    estimated_cost: float
    
    # Budget state
    budget_id: str
    remaining_daily: float
    remaining_weekly: float
    remaining_monthly: float
    
    # Action
    action: str  # allow, throttle, block, warn
    throttle_factor: float = 1.0
    
    # Reason
    reason: str = ""
    
    # Timestamp
    decided_at: str = ""
    
    def __post_init__(self):
        if not self.decided_at:
            self.decided_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CostGuardrail:
    """
    Cross-session cost management.
    
    Features:
    - Budget tracking (daily/weekly/monthly)
    - Per-run limits
    - Automatic throttling
    - Cost event logging
    """
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.cost_dir = os.path.join(artifacts_dir, "governance", "cost")
        os.makedirs(self.cost_dir, exist_ok=True)
        
        self._budgets: Dict[str, CostBudget] = {}
        self._events: List[CostEvent] = []
        
        self._load_budgets()
        self._setup_default_budget()
    
    def _setup_default_budget(self) -> None:
        """Set up default global budget."""
        if "global" not in self._budgets:
            self._budgets["global"] = CostBudget(
                budget_id="global",
                scope="global",
                daily_limit=50.0,
                weekly_limit=200.0,
                monthly_limit=500.0,
                per_run_limit=2.0
            )
            self._save_budgets()
    
    def set_budget(self, budget: CostBudget) -> None:
        """Set a budget."""
        self._budgets[budget.budget_id] = budget
        self._save_budgets()
    
    def get_budget(self, budget_id: str = "global") -> Optional[CostBudget]:
        """Get a budget."""
        return self._budgets.get(budget_id)
    
    def check_budget(
        self,
        run_id: str,
        estimated_cost: float,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> CostDecision:
        """
        Check if a run is allowed within budget.
        
        Args:
            run_id: Run identifier
            estimated_cost: Estimated cost for run
            session_id: Optional session ID
            user_id: Optional user ID
            
        Returns:
            CostDecision
        """
        # Get applicable budget
        budget = self._get_applicable_budget(session_id, user_id)
        
        # Reset periods if needed
        self._reset_periods_if_needed(budget)
        
        # Check limits
        exceeded, period = budget.check_limits()
        
        if exceeded:
            action = budget.on_limit_reached
            allowed = action != "block"
            throttle = budget.throttle_factor if action == "throttle" else 1.0
            reason = f"{period} limit exceeded"
        elif not budget.check_run_budget(estimated_cost):
            action = "block"
            allowed = False
            throttle = 1.0
            reason = f"estimated cost {estimated_cost} exceeds per-run limit {budget.per_run_limit}"
        else:
            action = "allow"
            allowed = True
            throttle = 1.0
            reason = "within budget"
        
        decision = CostDecision(
            allowed=allowed,
            run_id=run_id,
            estimated_cost=estimated_cost,
            budget_id=budget.budget_id,
            remaining_daily=budget.daily_limit - budget.daily_used,
            remaining_weekly=budget.weekly_limit - budget.weekly_used,
            remaining_monthly=budget.monthly_limit - budget.monthly_used,
            action=action,
            throttle_factor=throttle,
            reason=reason
        )
        
        # Save decision
        path = os.path.join(self.cost_dir, f"decision_{run_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(decision.to_dict(), f, indent=2, ensure_ascii=False)
        
        return decision
    
    def record_cost(
        self,
        run_id: str,
        cost: float,
        cost_type: str,
        operation: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[str] = None,
        tokens_in: int = 0,
        tokens_out: int = 0
    ) -> CostEvent:
        """Record a cost event."""
        event = CostEvent(
            event_id=f"cost_{run_id}_{datetime.now().strftime('%H%M%S%f')}",
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            cost=cost,
            cost_type=cost_type,
            operation=operation,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out
        )
        
        self._events.append(event)
        
        # Update budgets
        self._update_budget_usage(cost, session_id, user_id)
        
        # Trim events
        if len(self._events) > 100000:
            self._events = self._events[-100000:]
        
        return event
    
    def get_usage_summary(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get usage summary."""
        budget = self._get_applicable_budget(session_id, user_id)
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        relevant = [e for e in self._events if e.timestamp >= cutoff]
        
        total_cost = sum(e.cost for e in relevant)
        by_type: Dict[str, float] = {}
        for e in relevant:
            by_type[e.cost_type] = by_type.get(e.cost_type, 0) + e.cost
        
        return {
            "period_days": days,
            "total_cost": round(total_cost, 4),
            "by_type": by_type,
            "event_count": len(relevant),
            "budget": {
                "daily_used": round(budget.daily_used, 4),
                "daily_limit": budget.daily_limit,
                "weekly_used": round(budget.weekly_used, 4),
                "weekly_limit": budget.weekly_limit,
                "monthly_used": round(budget.monthly_used, 4),
                "monthly_limit": budget.monthly_limit
            }
        }
    
    def _get_applicable_budget(
        self,
        session_id: Optional[str],
        user_id: Optional[str]
    ) -> CostBudget:
        """Get the most specific applicable budget."""
        if session_id and f"session_{session_id}" in self._budgets:
            return self._budgets[f"session_{session_id}"]
        if user_id and f"user_{user_id}" in self._budgets:
            return self._budgets[f"user_{user_id}"]
        return self._budgets["global"]
    
    def _update_budget_usage(
        self,
        cost: float,
        session_id: Optional[str],
        user_id: Optional[str]
    ) -> None:
        """Update budget usage."""
        budget = self._get_applicable_budget(session_id, user_id)
        
        budget.daily_used += cost
        budget.weekly_used += cost
        budget.monthly_used += cost
        
        self._save_budgets()
    
    def _reset_periods_if_needed(self, budget: CostBudget) -> None:
        """Reset budget periods if needed."""
        now = datetime.now()
        
        # Daily reset
        today = now.strftime("%Y-%m-%d")
        if budget.last_reset_daily != today:
            budget.daily_used = 0.0
            budget.last_reset_daily = today
        
        # Weekly reset (Monday)
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        if budget.last_reset_weekly != week_start:
            budget.weekly_used = 0.0
            budget.last_reset_weekly = week_start
        
        # Monthly reset
        month_start = now.strftime("%Y-%m-01")
        if budget.last_reset_monthly != month_start:
            budget.monthly_used = 0.0
            budget.last_reset_monthly = month_start
    
    def _save_budgets(self) -> None:
        """Save budgets to disk."""
        path = os.path.join(self.cost_dir, "budgets.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._budgets.items()},
                f, indent=2, ensure_ascii=False
            )
    
    def _load_budgets(self) -> None:
        """Load budgets from disk."""
        path = os.path.join(self.cost_dir, "budgets.json")
        if not os.path.exists(path):
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                self._budgets[k] = CostBudget(**v)
        except (json.JSONDecodeError, IOError, TypeError):
            pass

