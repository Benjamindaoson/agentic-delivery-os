"""
Long-term Memory Store: Hybrid vector + structured storage.
Persists across sessions for continuous learning.
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict, field
import sqlite3


@dataclass
class MemoryEntry:
    """A single memory entry."""
    memory_id: str
    memory_type: str  # pattern, behavior, outcome, knowledge
    content: Dict[str, Any]
    
    # Vector representation (for similarity search)
    embedding: Optional[List[float]] = None
    
    # Metadata
    source_run_id: Optional[str] = None
    source_session_id: Optional[str] = None
    created_at: str = ""
    last_accessed: str = ""
    access_count: int = 0
    
    # Relevance and decay
    importance_score: float = 1.0
    decay_factor: float = 0.99
    
    # Tags for filtering
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.last_accessed:
            self.last_accessed = now
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def access(self) -> None:
        """Record an access."""
        self.access_count += 1
        self.last_accessed = datetime.now().isoformat()
    
    def decay(self) -> None:
        """Apply decay to importance."""
        self.importance_score *= self.decay_factor


class LongTermMemoryStore:
    """
    Long-term memory with hybrid storage.
    
    Uses SQLite for structured queries and optional vector indexing.
    """
    
    def __init__(self, memory_dir: str = "memory/long_term"):
        self.memory_dir = memory_dir
        os.makedirs(memory_dir, exist_ok=True)
        
        self.db_path = os.path.join(memory_dir, "memories.db")
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                memory_id TEXT PRIMARY KEY,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding TEXT,
                source_run_id TEXT,
                source_session_id TEXT,
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                importance_score REAL DEFAULT 1.0,
                tags TEXT,
                schema_version TEXT DEFAULT '1.0'
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance_score DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source_session ON memories(source_session_id)
        """)
        
        conn.commit()
        conn.close()
    
    def store(self, entry: MemoryEntry) -> str:
        """
        Store a memory entry.
        
        Returns:
            memory_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO memories
            (memory_id, memory_type, content, embedding, source_run_id,
             source_session_id, created_at, last_accessed, access_count,
             importance_score, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            entry.memory_id,
            entry.memory_type,
            json.dumps(entry.content),
            json.dumps(entry.embedding) if entry.embedding else None,
            entry.source_run_id,
            entry.source_session_id,
            entry.created_at,
            entry.last_accessed,
            entry.access_count,
            entry.importance_score,
            json.dumps(entry.tags)
        ))
        
        conn.commit()
        conn.close()
        
        return entry.memory_id
    
    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a memory by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM memories WHERE memory_id = ?",
            (memory_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            entry = self._row_to_entry(row)
            entry.access()
            self._update_access(memory_id, entry.access_count, entry.last_accessed)
            return entry
        return None
    
    def search_by_type(
        self,
        memory_type: str,
        limit: int = 10,
        min_importance: float = 0.0
    ) -> List[MemoryEntry]:
        """Search memories by type."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM memories
            WHERE memory_type = ? AND importance_score >= ?
            ORDER BY importance_score DESC
            LIMIT ?
        """, (memory_type, min_importance, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row) for row in rows]
    
    def search_by_tags(
        self,
        tags: List[str],
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Search memories by tags."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Simple tag matching (could be improved with FTS)
        cursor.execute("""
            SELECT * FROM memories
            WHERE tags LIKE ?
            ORDER BY importance_score DESC
            LIMIT ?
        """, (f'%{tags[0]}%' if tags else '%', limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row) for row in rows]
    
    def search_by_session(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[MemoryEntry]:
        """Get memories from a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM memories
            WHERE source_session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (session_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row) for row in rows]
    
    def get_recent(
        self,
        limit: int = 20,
        memory_type: Optional[str] = None
    ) -> List[MemoryEntry]:
        """Get recent memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if memory_type:
            cursor.execute("""
                SELECT * FROM memories
                WHERE memory_type = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (memory_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM memories
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row) for row in rows]
    
    def get_most_important(
        self,
        limit: int = 10,
        memory_type: Optional[str] = None
    ) -> List[MemoryEntry]:
        """Get most important memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if memory_type:
            cursor.execute("""
                SELECT * FROM memories
                WHERE memory_type = ?
                ORDER BY importance_score DESC
                LIMIT ?
            """, (memory_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM memories
                ORDER BY importance_score DESC
                LIMIT ?
            """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row) for row in rows]
    
    def apply_decay(self, decay_factor: float = 0.99) -> int:
        """Apply decay to all memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE memories
            SET importance_score = importance_score * ?
        """, (decay_factor,))
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        return affected
    
    def prune(self, min_importance: float = 0.01, max_age_days: int = 90) -> int:
        """Prune old/unimportant memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = datetime.now().isoformat()[:10]  # Simple date comparison
        
        cursor.execute("""
            DELETE FROM memories
            WHERE importance_score < ?
        """, (min_importance,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted
    
    def count(self, memory_type: Optional[str] = None) -> int:
        """Count memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if memory_type:
            cursor.execute(
                "SELECT COUNT(*) FROM memories WHERE memory_type = ?",
                (memory_type,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM memories")
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def export_all(self) -> List[Dict[str, Any]]:
        """Export all memories."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM memories ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        
        return [self._row_to_entry(row).to_dict() for row in rows]
    
    def _update_access(self, memory_id: str, access_count: int, last_accessed: str) -> None:
        """Update access stats."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE memories
            SET access_count = ?, last_accessed = ?
            WHERE memory_id = ?
        """, (access_count, last_accessed, memory_id))
        
        conn.commit()
        conn.close()
    
    def _row_to_entry(self, row: tuple) -> MemoryEntry:
        """Convert DB row to MemoryEntry."""
        return MemoryEntry(
            memory_id=row[0],
            memory_type=row[1],
            content=json.loads(row[2]),
            embedding=json.loads(row[3]) if row[3] else None,
            source_run_id=row[4],
            source_session_id=row[5],
            created_at=row[6],
            last_accessed=row[7],
            access_count=row[8],
            importance_score=row[9],
            tags=json.loads(row[10]) if row[10] else []
        )


class PatternMemory:
    """
    Specialized memory for task patterns.
    """
    
    def __init__(self, store: LongTermMemoryStore):
        self.store = store
    
    def store_pattern(
        self,
        pattern_signature: str,
        pattern_data: Dict[str, Any],
        outcome: str,  # success, failure
        importance: float = 1.0,
        run_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Store a task pattern."""
        memory_id = f"pattern_{hashlib.sha256(pattern_signature.encode()).hexdigest()[:12]}"
        
        entry = MemoryEntry(
            memory_id=memory_id,
            memory_type="pattern",
            content={
                "signature": pattern_signature,
                "data": pattern_data,
                "outcome": outcome
            },
            source_run_id=run_id,
            source_session_id=session_id,
            importance_score=importance,
            tags=[outcome, pattern_data.get("task_type", "unknown")]
        )
        
        return self.store.store(entry)
    
    def get_similar_patterns(
        self,
        task_type: str,
        limit: int = 5
    ) -> List[MemoryEntry]:
        """Get similar patterns for a task type."""
        return self.store.search_by_tags([task_type], limit=limit)
    
    def get_success_patterns(self, limit: int = 10) -> List[MemoryEntry]:
        """Get successful patterns."""
        return self.store.search_by_tags(["success"], limit=limit)


class BehaviorMemory:
    """
    Specialized memory for agent behavior.
    """
    
    def __init__(self, store: LongTermMemoryStore):
        self.store = store
    
    def store_behavior(
        self,
        agent_id: str,
        behavior_type: str,
        context: Dict[str, Any],
        outcome: Dict[str, Any],
        run_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Store agent behavior."""
        memory_id = f"behavior_{agent_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        entry = MemoryEntry(
            memory_id=memory_id,
            memory_type="behavior",
            content={
                "agent_id": agent_id,
                "behavior_type": behavior_type,
                "context": context,
                "outcome": outcome
            },
            source_run_id=run_id,
            source_session_id=session_id,
            tags=[agent_id, behavior_type]
        )
        
        return self.store.store(entry)
    
    def get_agent_behaviors(
        self,
        agent_id: str,
        limit: int = 20
    ) -> List[MemoryEntry]:
        """Get behaviors for an agent."""
        return self.store.search_by_tags([agent_id], limit=limit)


class OutcomeMemory:
    """
    Specialized memory for planner outcomes.
    """
    
    def __init__(self, store: LongTermMemoryStore):
        self.store = store
    
    def store_outcome(
        self,
        planner_genome_hash: str,
        goal_type: str,
        outcome: Dict[str, Any],
        run_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """Store planner outcome."""
        memory_id = f"outcome_{run_id or datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        entry = MemoryEntry(
            memory_id=memory_id,
            memory_type="outcome",
            content={
                "genome_hash": planner_genome_hash,
                "goal_type": goal_type,
                "outcome": outcome
            },
            source_run_id=run_id,
            source_session_id=session_id,
            tags=[goal_type, "success" if outcome.get("success") else "failure"]
        )
        
        return self.store.store(entry)
    
    def get_outcomes_for_goal_type(
        self,
        goal_type: str,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Get outcomes for a goal type."""
        return self.store.search_by_tags([goal_type], limit=limit)



