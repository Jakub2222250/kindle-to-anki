from dataclasses import dataclass

@dataclass
class RuntimeDescriptor:
    id: str
    display_name: str
    supports_batching: bool
    supports_interactive: bool
    notes: str | None
    