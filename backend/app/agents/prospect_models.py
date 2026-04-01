"""Structures simples pour manipuler des prospects affiliés préparés."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ProspectStatus = Literal["new", "reviewed", "contacted"]


@dataclass(slots=True)
class ProspectItem:
    """Représente un prospect préparé (non enrichi / non contacté automatiquement)."""

    category: str
    city: str
    query: str
    status: ProspectStatus = "new"
    notes: str = ""

