from .runtime_config import RuntimeConfig
from ..pricing.usage_breakdown import UsageBreakdown
from ..pricing.usage_estimate import UsageEstimate
from .runtime_descriptor import RuntimeDescriptor


class Runtime:
    id: str
    display_name: str
    supported_tasks: set[str]
    supported_model_families: set[str] | None
    platform_requirements: set[str]
    supports_batching: bool
    supports_interactive: bool

    def estimate_usage(self, num_items: int, config: RuntimeConfig) -> UsageBreakdown:
        # num_items can be replaced with UsageContext in the future for various language situations etc.
        raise NotImplementedError

    def describe(self):
        return RuntimeDescriptor(
            id=self.id,
            display_name=self.display_name,
            supports_batching=self.supports_batching,
            supports_interactive=self.supports_interactive,
            notes=None,
        )
