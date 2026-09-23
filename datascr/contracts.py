from dataclasses import dataclass, field
from typing import Protocol


class CollectionError(Exception):
    """An expected source, policy, or model failure safe to report to the user."""


@dataclass
class Document:
    url: str
    text: str
    language: str = "und"
    revision: str | None = None


@dataclass
class Field:
    name: str
    description: str
    kind: str = "number"
    unit: str = ""
    aliases: list[str] = field(default_factory=list)
    list_separator: str = ""
    exclude_terms: list[str] = field(default_factory=list)


class Model(Protocol):
    name: str

    def extract(self, document: Document, fields: list[Field]) -> list[dict]: ...


class Source(Protocol):
    def collect(self, config: dict) -> list[Document]: ...
