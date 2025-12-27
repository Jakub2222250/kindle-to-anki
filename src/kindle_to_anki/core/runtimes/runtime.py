from typing import Tuple
from .runtime_descriptor import RuntimeDescriptor


class Runtime:
    id: str
    display_name: str
    supported_tasks: set[str]
    supported_model_families: set[str]
    platform_requirements: set[str]
    supports_batching: bool
    supports_interactive: bool

    def estimate_tokens(self, task, model, batch_info) -> Tuple[int, int]:
        # Returns estimated tokens per 1000 words (input, output)
        raise NotImplementedError

    def describe(self):
        return RuntimeDescriptor(
            id=self.id,
            display_name=self.display_name,
            supports_batching=self.supports_batching,
            supports_interactive=self.supports_interactive,
            notes=None,
        )
