"""Schemas for the Obsidian import flow."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VocabItem(BaseModel):
    """Vocabulary candidate. Accepts the legacy Korean keys (``단어``/``뜻``) from the old UI."""

    model_config = ConfigDict(populate_by_name=True)

    word: str = Field(alias="단어")
    meaning: str = Field(default="", alias="뜻")

    def to_legacy(self) -> dict[str, str]:
        return {"단어": self.word, "뜻": self.meaning}


class ObsidianCommitRequest(BaseModel):
    selected_sentences: list[str] = Field(default_factory=list)
    selected_vocab: list[VocabItem] = Field(default_factory=list)
