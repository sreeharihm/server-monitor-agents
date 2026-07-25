"""Shared A2A (Agent-to-Agent) protocol Pydantic models.

Based on the A2A specification: an agent exposes /.well-known/agent.json (AgentCard)
and accepts task requests at POST /tasks/send (TaskSendRequest → TaskResponse).
"""

from typing import List, Literal, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Message parts
# ---------------------------------------------------------------------------

class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


# ---------------------------------------------------------------------------
# Task request / response
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str  # "user" | "agent"
    parts: List[TextPart]


class TaskSendRequest(BaseModel):
    id: str
    message: Message


class TaskStatus(BaseModel):
    state: str  # "submitted" | "working" | "completed" | "failed"
    message: Optional[str] = None


class Artifact(BaseModel):
    name: Optional[str] = None
    parts: List[TextPart]


class TaskResponse(BaseModel):
    id: str
    status: TaskStatus
    artifacts: List[Artifact] = []


# ---------------------------------------------------------------------------
# Agent discovery card  (GET /.well-known/agent.json)
# ---------------------------------------------------------------------------

class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    inputModes: List[str] = ["text"]
    outputModes: List[str] = ["text"]


class AgentCard(BaseModel):
    name: str
    description: str
    version: str
    url: str
    skills: List[AgentSkill] = []
    defaultInputModes: List[str] = ["text"]
    defaultOutputModes: List[str] = ["text"]
