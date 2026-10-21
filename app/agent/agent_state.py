"""Agent state management for Skill Checker Agent."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
import uuid


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of a single step execution."""
    step_name: str
    status: StepStatus
    output: Any = None
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentState:
    """Mutable state for the agent during execution."""
    
    # Identity
    skill_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Input
    skill_zip_path: Optional[str] = None
    skill_md_path: Optional[str] = None
    skill_content: Optional[str] = None
    
    # Extracted info
    skill_name: Optional[str] = None
    skill_description: Optional[str] = None
    frontmatter_valid: bool = False
    frontmatter_warnings: int = 0
    
    # Step results
    steps: dict[str, StepResult] = field(default_factory=dict)
    
    # Evaluation data
    evals: list[dict] = field(default_factory=list)  # test queries
    trigger_results: list[dict] = field(default_factory=list)
    trigger_summary: Optional[dict] = None
    env_dependencies: list[dict] = field(default_factory=list)
    env_summary: Optional[dict] = None
    
    # Final report
    trace_report: Optional[dict] = None
    
    # Conversation history for LLM context
    conversation: list[dict] = field(default_factory=list)
    
    # Current step being executed
    current_step: Optional[str] = None
    
    def record_step(self, step_name: str, status: StepStatus, 
                    output: Any = None, error: str = None, metadata: dict = None):
        """Record the result of a step execution."""
        self.steps[step_name] = StepResult(
            step_name=step_name,
            status=status,
            output=output,
            error=error,
            metadata=metadata or {}
        )
        if status == StepStatus.IN_PROGRESS:
            self.current_step = step_name
    
    def get_step(self, step_name: str) -> Optional[StepResult]:
        """Get result of a specific step."""
        return self.steps.get(step_name)
    
    def is_step_done(self, step_name: str) -> bool:
        """Check if a step is completed."""
        result = self.steps.get(step_name)
        return result is not None and result.status == StepStatus.COMPLETED
    
    def get_completed_steps(self) -> list[str]:
        """Get list of completed step names."""
        return [name for name, result in self.steps.items() 
                if result.status == StepStatus.COMPLETED]
    
    def add_conversation(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation.append({"role": role, "content": content})
    
    def get_conversation_summary(self) -> str:
        """Get a summary of conversation for LLM context."""
        lines = []
        for msg in self.conversation[-10:]:  # Last 10 messages
            lines.append(f"{msg['role']}: {msg['content'][:200]}")
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """Convert state to dictionary for serialization."""
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "skill_description": self.skill_description,
            "frontmatter_valid": self.frontmatter_valid,
            "frontmatter_warnings": self.frontmatter_warnings,
            "completed_steps": self.get_completed_steps(),
            "current_step": self.current_step,
            "has_evals": len(self.evals) > 0,
            "has_trigger_results": len(self.trigger_results) > 0,
            "has_env_data": len(self.env_dependencies) > 0,
            "has_trace": self.trace_report is not None,
        }
