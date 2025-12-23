"""
Session Manager: Long-term session management across runs and days.
Supports session-level memory, policy, and statistics.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict, field


@dataclass
class SessionStats:
    """Statistics for a session."""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_cost: float = 0.0
    total_latency_ms: float = 0.0
    avg_quality_score: float = 0.0
    last_run_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def update(self, run_result: Dict[str, Any]) -> None:
        """Update stats with a run result."""
        self.total_runs += 1
        if run_result.get("success", False):
            self.successful_runs += 1
        else:
            self.failed_runs += 1
        self.total_cost += run_result.get("cost", 0.0)
        self.total_latency_ms += run_result.get("latency_ms", 0.0)
        
        # Rolling average for quality
        quality = run_result.get("quality_score", 0.0)
        if self.total_runs == 1:
            self.avg_quality_score = quality
        else:
            self.avg_quality_score = (
                self.avg_quality_score * (self.total_runs - 1) + quality
            ) / self.total_runs
        
        self.last_run_at = datetime.now().isoformat()


@dataclass
class SessionMemory:
    """Session-level memory (persists across runs)."""
    patterns: List[Dict[str, Any]] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    learned_shortcuts: List[Dict[str, Any]] = field(default_factory=list)
    context_cache: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def add_pattern(self, pattern: Dict[str, Any]) -> None:
        """Add a learned pattern."""
        self.patterns.append({
            **pattern,
            "added_at": datetime.now().isoformat()
        })
        # Keep last 100 patterns
        if len(self.patterns) > 100:
            self.patterns = self.patterns[-100:]
    
    def set_preference(self, key: str, value: Any) -> None:
        """Set a session preference."""
        self.preferences[key] = {
            "value": value,
            "set_at": datetime.now().isoformat()
        }


@dataclass
class SessionPolicy:
    """Session-level policy overrides."""
    max_cost_per_run: float = 1.0
    max_latency_ms: int = 60000
    preferred_agents: List[str] = field(default_factory=list)
    blocked_tools: List[str] = field(default_factory=list)
    quality_threshold: float = 0.7
    retry_policy: str = "exponential"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Session:
    """A user session spanning multiple runs."""
    session_id: str
    user_id: str
    
    # Timing
    created_at: str
    last_active_at: str
    expires_at: Optional[str] = None
    
    # Runs in this session
    run_ids: List[str] = field(default_factory=list)
    
    # Session-level state
    stats: SessionStats = field(default_factory=SessionStats)
    memory: SessionMemory = field(default_factory=SessionMemory)
    policy: SessionPolicy = field(default_factory=SessionPolicy)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = "1.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "last_active_at": self.last_active_at,
            "expires_at": self.expires_at,
            "run_ids": self.run_ids,
            "stats": self.stats.to_dict(),
            "memory": self.memory.to_dict(),
            "policy": self.policy.to_dict(),
            "metadata": self.metadata,
            "schema_version": self.schema_version
        }
    
    def add_run(self, run_id: str, run_result: Dict[str, Any]) -> None:
        """Add a run to this session."""
        self.run_ids.append(run_id)
        self.last_active_at = datetime.now().isoformat()
        self.stats.update(run_result)
    
    def is_expired(self) -> bool:
        """Check if session is expired."""
        if not self.expires_at:
            return False
        return datetime.now().isoformat() > self.expires_at


class SessionManager:
    """
    Manages long-term sessions across runs and days.
    
    Key features:
    - session_id ≠ run_id
    - Session-level memory, policy, stats
    - Automatic expiration and cleanup
    """
    
    DEFAULT_SESSION_TTL_HOURS = 24 * 7  # 1 week
    
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.sessions_dir = os.path.join(artifacts_dir, "session")
        os.makedirs(self.sessions_dir, exist_ok=True)
        
        self._sessions: Dict[str, Session] = {}
        self._load_sessions()
    
    def create_session(
        self,
        user_id: str,
        ttl_hours: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Session:
        """
        Create a new session.
        
        Args:
            user_id: User identifier
            ttl_hours: Session TTL in hours
            metadata: Optional metadata
            
        Returns:
            Session
        """
        session_id = self._generate_session_id(user_id)
        now = datetime.now()
        
        ttl = ttl_hours or self.DEFAULT_SESSION_TTL_HOURS
        expires_at = (now + timedelta(hours=ttl)).isoformat()
        
        session = Session(
            session_id=session_id,
            user_id=user_id,
            created_at=now.isoformat(),
            last_active_at=now.isoformat(),
            expires_at=expires_at,
            metadata=metadata or {}
        )
        
        self._sessions[session_id] = session
        self._save_session(session)
        
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            self._cleanup_session(session_id)
            return None
        return session
    
    def get_or_create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None
    ) -> Session:
        """Get existing session or create new one."""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        
        # Find active session for user
        for s in self._sessions.values():
            if s.user_id == user_id and not s.is_expired():
                return s
        
        return self.create_session(user_id)
    
    def add_run_to_session(
        self,
        session_id: str,
        run_id: str,
        run_result: Dict[str, Any]
    ) -> bool:
        """
        Add a run to a session.
        
        Args:
            session_id: Session ID
            run_id: Run ID
            run_result: Run result with success, cost, latency, quality
            
        Returns:
            True if added, False if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.add_run(run_id, run_result)
        self._save_session(session)
        return True
    
    def update_session_memory(
        self,
        session_id: str,
        pattern: Optional[Dict[str, Any]] = None,
        preference_key: Optional[str] = None,
        preference_value: Any = None
    ) -> bool:
        """Update session memory."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        if pattern:
            session.memory.add_pattern(pattern)
        
        if preference_key is not None:
            session.memory.set_preference(preference_key, preference_value)
        
        self._save_session(session)
        return True
    
    def update_session_policy(
        self,
        session_id: str,
        **policy_updates
    ) -> bool:
        """Update session policy."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        for key, value in policy_updates.items():
            if hasattr(session.policy, key):
                setattr(session.policy, key, value)
        
        self._save_session(session)
        return True
    
    def get_session_stats(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session statistics."""
        session = self.get_session(session_id)
        if not session:
            return None
        return session.stats.to_dict()
    
    def list_user_sessions(self, user_id: str) -> List[Session]:
        """List all sessions for a user."""
        return [
            s for s in self._sessions.values()
            if s.user_id == user_id and not s.is_expired()
        ]
    
    def cleanup_expired_sessions(self) -> int:
        """Cleanup expired sessions."""
        expired = [
            sid for sid, s in self._sessions.items()
            if s.is_expired()
        ]
        for sid in expired:
            self._cleanup_session(sid)
        return len(expired)
    
    def _generate_session_id(self, user_id: str) -> str:
        """Generate unique session ID."""
        content = f"{user_id}:{datetime.now().isoformat()}"
        return f"sess_{hashlib.sha256(content.encode()).hexdigest()[:16]}"
    
    def _save_session(self, session: Session) -> None:
        """Save session to artifact."""
        path = os.path.join(self.sessions_dir, f"{session.session_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
    
    def _load_sessions(self) -> None:
        """Load all sessions from artifacts."""
        if not os.path.exists(self.sessions_dir):
            return
        
        for filename in os.listdir(self.sessions_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.sessions_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    session = self._dict_to_session(data)
                    if not session.is_expired():
                        self._sessions[session.session_id] = session
                except (json.JSONDecodeError, IOError, KeyError):
                    pass
    
    def _cleanup_session(self, session_id: str) -> None:
        """Remove expired session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
        
        path = os.path.join(self.sessions_dir, f"{session_id}.json")
        if os.path.exists(path):
            # Move to archive instead of delete
            archive_dir = os.path.join(self.sessions_dir, "archived")
            os.makedirs(archive_dir, exist_ok=True)
            os.rename(path, os.path.join(archive_dir, f"{session_id}.json"))
    
    def _dict_to_session(self, data: Dict[str, Any]) -> Session:
        """Convert dict to Session."""
        stats_data = data.get("stats", {})
        memory_data = data.get("memory", {})
        policy_data = data.get("policy", {})
        
        return Session(
            session_id=data["session_id"],
            user_id=data["user_id"],
            created_at=data["created_at"],
            last_active_at=data["last_active_at"],
            expires_at=data.get("expires_at"),
            run_ids=data.get("run_ids", []),
            stats=SessionStats(**stats_data) if stats_data else SessionStats(),
            memory=SessionMemory(**memory_data) if memory_data else SessionMemory(),
            policy=SessionPolicy(**policy_data) if policy_data else SessionPolicy(),
            metadata=data.get("metadata", {}),
            schema_version=data.get("schema_version", "1.0")
        )
