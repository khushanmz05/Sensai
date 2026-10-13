from dataclasses import dataclass, field
from time import time
from typing import Literal


Role = Literal["system", "user", "assistant", "tool"]
Status = Literal["completed", "failed", "cancelled"]


@dataclass(slots=True)
class Message:
    role: Role
    content: str
    status: Status = "completed"
    created_at: float = field(default_factory=time)

    def to_ollama(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class Session:
    id: str
    title: str
    created_at: float
    updated_at: float
    status: Status = "completed"

    @classmethod
    def from_row(cls, row: dict) -> "Session":
        return cls(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            status=row.get("status", "completed"),
        )


@dataclass(slots=True)
class Profile:
    user_id: str
    language: str = "English"
    explanation_level: str = "detailed"
    preferred_persona: str = "explainer"
    updated_at: float | None = None