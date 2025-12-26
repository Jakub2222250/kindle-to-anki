# runtimes/base.py
from typing import Protocol, Sequence, TypeVar

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")

class Runtime(Protocol[InputT, OutputT]):
    id: str
    supports_batching: bool
    max_batch_tokens: int | None

    def estimate_cost(self, inp: InputT) -> int:
        ...

    def run(self, inputs: Sequence[InputT]) -> list[OutputT]:
        ...
