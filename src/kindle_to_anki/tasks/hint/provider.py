from typing import List

from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from .schema import HintInput, HintOutput


class HintProvider:
    id = "hint"
    description = "Hint provider supporting multiple runtimes"

    def __init__(self, runtimes: dict):
        self.runtimes = runtimes

    def get_task_methods(self):
        return {"hint": self.generate}

    def generate(
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

        hint_inputs: List[HintInput] = []
        for note in notes:
            if note.kindle_usage and note.expression and note.kindle_word:
                pos_tag = getattr(note, 'pos_tag', 'unknown')
                hint_input = HintInput(
                    uid=note.uid,
                    word=note.kindle_word,
                    lemma=note.expression,
                    pos=pos_tag,
                    sentence=note.kindle_usage
                )
                hint_inputs.append(hint_input)

        if not hint_inputs:
            print("No notes with required fields for hint")
            return notes

        hint_outputs: List[HintOutput] = runtime.generate(
            hint_inputs,
            runtime_config,
            ignore_cache=ignore_cache,
            use_test_cache=use_test_cache
        )

        hint_map = {}
        for hint_input, hint_output in zip(hint_inputs, hint_outputs):
            hint_map[hint_input.uid] = hint_output

        for note in notes:
            if note.uid in hint_map:
                result = hint_map[note.uid]
                note.apply_hint_results({"hint": result.hint})
                note.add_generation_metadata(self.id, runtime.id, runtime_config.model_id, runtime_config.prompt_id)

        return notes
