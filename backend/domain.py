from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class Card(BaseModel):
    entity_id: int
    card_id: str
    name: str
    type: str = "MINION"
    attack: int | None = None
    health: int | None = None
    tier: int | None = None
    cost: int | None = None
    position: int = 0
    text: str = ""
    races: list[str] = Field(default_factory=list)
    mechanics: list[str] = Field(default_factory=list)


class Snapshot(BaseModel):
    schema_version: int = 1
    id: str = Field(default_factory=lambda: str(uuid4()))
    game_id: str
    observed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: Literal["live", "demo", "import"]
    build: str | None = None
    phase: Literal["recruit", "combat", "ended", "unknown"] = "unknown"
    player_id: int | None = None
    turn: int | None = None
    hero: str | None = None
    health: int | None = None
    armor: int | None = None
    gold: int | None = None
    tier: int | None = None
    board: list[Card] = Field(default_factory=list)
    hand: list[Card] = Field(default_factory=list)
    shop: list[Card] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class Advice(BaseModel):
    rule: str
    title: str
    reason: str
    confidence: str = "基础规则 · 未经实局验证"
    action: Literal["buy", "play", "review"] = "review"
    entity_id: int | None = None
    remaining_gold: int | None = None
