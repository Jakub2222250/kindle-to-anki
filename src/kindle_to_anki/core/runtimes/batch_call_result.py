from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class BatchCallResult:
    """Result of a batch API call, encapsulating success/failure state."""
    success: bool
    results: Dict[str, Any] = field(default_factory=dict)
    model_id: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None
