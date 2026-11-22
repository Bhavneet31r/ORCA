"""Shared data structures passed between agents."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Location:
    name: str
    lat: float
    lon: float


@dataclass
class Evidence:
    source: str
    detail: str
    simulated: bool = False


@dataclass
class ParsedQuery:
    text: str
    language: str
    intents: list
    location: Optional[Location]
    day_offset: int
    part: Optional[str]
    window: tuple            # (start datetime, end datetime)
    window_label: str
    follow_up: bool = False


@dataclass
class Task:
    id: str
    agent: str
    action: str
    params: dict = field(default_factory=dict)


@dataclass
class Plan:
    intents: list
    tasks: list
    refs: dict = field(default_factory=dict)   # logical name -> task id


@dataclass
class TaskResult:
    task_id: str
    agent: str
    action: str
    ok: bool = True
    data: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class Session:
    location: Optional[Location] = None
    intents: list = field(default_factory=list)
    day_offset: int = 0
    part: Optional[str] = None
    language: str = "en"


@dataclass
class Response:
    text: str
    language: str
    plan: Optional[Plan] = None
    results: dict = field(default_factory=dict)
    trace: list = field(default_factory=list)
    evidence: list = field(default_factory=list)


@dataclass
class AnalysisResult:
    status: str
    location: Optional[str]
    language: str
    weather: dict = field(default_factory=dict)
    pfz: dict = field(default_factory=dict)
    geofence: dict = field(default_factory=dict)
    summary: str = ""
    timestamp: str = ""
    mode: str = "advisory"
    answer: str = ""
