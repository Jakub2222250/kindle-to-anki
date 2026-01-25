from typing import List

from kindle_to_anki.logging import get_logger
from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from .schema import UsageLevelInput, UsageLevelOutput


class UsageLevelProvider:
    id = "usage_level"
    description = "Usage Level provider supporting multiple runtimes"

    def __init__(self, runtimes: dict):
        self.runtimes = runtimes

    def get_task_methods(self):
        return {"usage_level": self.estimate}

    def estimate(
        self,
        notes: List[AnkiNote],
        runtime_choice: str = None,
        runtime_config: RuntimeConfig = None,
        ignore_cache: bool = False,
        use_test_cache: bool = False
    ) -> List[AnkiNote]:
        if runtime_choice and runtime_choice in self.runtimes:
            runtime = self.runtimes[runtime_choice]
        else:
            runtime = next(iter(self.runtimes.values()))

        usage_inputs: List[UsageLevelInput] = []
        for note in notes:
            if note.source_usage and note.expression and note.source_word and note.definition:
                pos_tag = getattr(note, 'pos_tag', 'unknown')
                usage_input = UsageLevelInput(
                    uid=note.uid,
                    word=note.source_word,
                    lemma=note.expression,
                    pos=pos_tag,
                    sentence=note.source_usage,
                    definition=note.definition
                )
                usage_inputs.append(usage_input)

        if not usage_inputs:
            get_logger().info("No notes with required fields for usage level estimation")
            return notes

        usage_outputs: List[UsageLevelOutput] = runtime.estimate(
            usage_inputs,
            runtime_config,
            ignore_cache=ignore_cache,
            use_test_cache=use_test_cache
        )

        usage_map = {}
        for usage_input, usage_output in zip(usage_inputs, usage_outputs):
            usage_map[usage_input.uid] = usage_output

        for note in notes:
            if note.uid in usage_map:
                result = usage_map[note.uid]
                note.apply_usage_level_results({"usage_level": result.usage_level})
                note.add_generation_metadata(self.id, runtime.id, runtime_config.model_id, runtime_config.prompt_id)

        return notes
