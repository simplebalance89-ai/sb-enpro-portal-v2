"""
Enpro Conversation Context — Track multi-turn context for conversational AI

This module manages conversation state across multiple turns, enabling
the "knowledgeable colleague" experience rather than command-based interactions.

v2.16: Session-based memory (resets on browser close)
v2.17+: Will support persistent profiles
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


@dataclass
class ConversationContext:
    """
    Tracks context through a conversation session.
    
    This is the foundation for v2.17 persistent profiles.
    Currently session-based (in-memory), but structured for easy DB migration.
    """
    # Session identification
    session_id: str
    user_id: Optional[str] = None  # For v2.17 user profiles
    
    # Customer context (what the sales rep is working on)
    customer_type: Optional[str] = None  # "data center", "manufacturing", "oil & gas", etc.
    customer_company: Optional[str] = None
    application: Optional[str] = None  # "HVAC", "hydraulic", "compressed air", etc.
    
    # Technical specs discussed
    specs: Dict[str, Any] = field(default_factory=dict)
    # e.g., {"micron": 10, "media": "polypropylene", "size": "24x24", "merv": 13}
    
    # Products referenced in this conversation
    products_discussed: List[Dict] = field(default_factory=list)
    # Each item: {"part_number": "HC9600", "timestamp": "...", "context": "primary recommendation"}
    
    # Conversation flow tracking
    turn_count: int = 0
    last_intent: Optional[str] = None
    last_query: Optional[str] = None
    
    # For recommendation narrowing
    recommendations_shown: int = 0
    needs_clarification: bool = False
    open_questions: List[str] = field(default_factory=list)
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "customer_type": self.customer_type,
            "customer_company": self.customer_company,
            "application": self.application,
            "specs": self.specs,
            "products_discussed": self.products_discussed,
            "turn_count": self.turn_count,
            "last_intent": self.last_intent,
            "last_query": self.last_query,
            "recommendations_shown": self.recommendations_shown,
            "needs_clarification": self.needs_clarification,
            "open_questions": self.open_questions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationContext":
        """Deserialize from dict."""
        return cls(
            session_id=data.get("session_id", ""),
            user_id=data.get("user_id"),
            customer_type=data.get("customer_type"),
            customer_company=data.get("customer_company"),
            application=data.get("application"),
            specs=data.get("specs", {}),
            products_discussed=data.get("products_discussed", []),
            turn_count=data.get("turn_count", 0),
            last_intent=data.get("last_intent"),
            last_query=data.get("last_query"),
            recommendations_shown=data.get("recommendations_shown", 0),
            needs_clarification=data.get("needs_clarification", False),
            open_questions=data.get("open_questions", []),
            created_at=data.get("created_at", datetime.utcnow().isoformat()),
            updated_at=data.get("updated_at", datetime.utcnow().isoformat()),
        )
    
    def add_product(self, part_number: str, context: str = ""):
        """Track a product that was discussed."""
        self.products_discussed.append({
            "part_number": part_number,
            "timestamp": datetime.utcnow().isoformat(),
            "context": context,
        })
        # Keep only last 10 to prevent bloat
        if len(self.products_discussed) > 10:
            self.products_discussed = self.products_discussed[-10:]
        self._touch()
    
    def update_specs(self, **kwargs):
        """Update technical specs (accumulates, doesn't replace)."""
        for key, value in kwargs.items():
            if value is not None:
                self.specs[key] = value
        self._touch()
    
    def set_customer_context(self, customer_type: Optional[str] = None, 
                            company: Optional[str] = None,
                            application: Optional[str] = None):
        """Set the customer/application context."""
        if customer_type:
            self.customer_type = customer_type
        if company:
            self.customer_company = company
        if application:
            self.application = application
        self._touch()
    
    def increment_turn(self, intent: str, query: str):
        """Track a conversation turn."""
        self.turn_count += 1
        self.last_intent = intent
        self.last_query = query
        self._touch()
    
    def get_recent_products(self, count: int = 3) -> List[str]:
        """Get the most recently discussed part numbers."""
        products = [p["part_number"] for p in self.products_discussed[-count:]]
        return list(reversed(products))  # Most recent first
    
    def get_primary_product(self) -> Optional[str]:
        """Get the main product being discussed (most recent)."""
        if self.products_discussed:
            return self.products_discussed[-1]["part_number"]
        return None
    
    def format_for_prompt(self) -> str:
        """Format context as a string to inject into system prompts."""
        lines = []
        
        if self.customer_type or self.customer_company:
            customer = self.customer_company or self.customer_type
            lines.append(f"Customer: {customer}")
        
        if self.application:
            lines.append(f"Application: {self.application}")
        
        if self.specs:
            specs_str = ", ".join([f"{k}={v}" for k, v in self.specs.items()])
            lines.append(f"Specs discussed: {specs_str}")
        
        if self.products_discussed:
            recent = self.get_recent_products(3)
            lines.append(f"Products discussed: {', '.join(recent)}")
        
        if self.open_questions:
            lines.append(f"Open questions: {'; '.join(self.open_questions)}")
        
        return "\n".join(lines) if lines else "No prior context."
    
    def _touch(self):
        """Update the timestamp."""
        self.updated_at = datetime.utcnow().isoformat()


# ═══════════════════════════════════════════════════════════════════════════
# Context Manager (in-memory for v2.16, DB-backed for v2.17)
# ═══════════════════════════════════════════════════════════════════════════

class ContextManager:
    """
    Manages conversation contexts across sessions.
    
    v2.16: In-memory only (dictionary)
    v2.17: Will support Redis/database persistence
    """
    
    def __init__(self):
        self._contexts: Dict[str, ConversationContext] = {}
    
    def get_context(self, session_id: str, user_id: Optional[str] = None) -> ConversationContext:
        """Get or create context for a session."""
        if session_id not in self._contexts:
            self._contexts[session_id] = ConversationContext(
                session_id=session_id,
                user_id=user_id
            )
        return self._contexts[session_id]
    
    def update_context(self, session_id: str, **updates) -> ConversationContext:
        """Update context fields."""
        ctx = self.get_context(session_id)
        
        for key, value in updates.items():
            if hasattr(ctx, key):
                setattr(ctx, key, value)
        
        ctx._touch()
        return ctx
    
    def clear_context(self, session_id: str):
        """Clear context for a session (reset)."""
        if session_id in self._contexts:
            del self._contexts[session_id]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get system stats for monitoring."""
        return {
            "active_sessions": len(self._contexts),
            "total_turns": sum(c.turn_count for c in self._contexts.values()),
            "sessions_needing_clarification": sum(
                1 for c in self._contexts.values() if c.needs_clarification
            ),
        }


# Module-level instance (singleton)
context_manager = ContextManager()
