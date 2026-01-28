# tasks/lui/provider.py
from typing import List

from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.logging import get_logger
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.tasks.lui.schema import LUIInput, LUIOutput
from kindle_to_anki.util.cancellation import CancellationToken, NONE_TOKEN


class LUIProvider:
    id = "lui"
    description = "Lexical Unit Identification provider supporting multiple runtimes"

    def __init__(self, runtimes: dict):
        """
        runtimes: dict mapping runtime IDs to runtime instances
                  e.g., {"gpt-5": llm_runtime1, "claude": claude_runtime}
        """
        self.runtimes = runtimes

    def get_task_methods(self):
        """Expose task to orchestrator"""
        return {"identify": self.identify}

    def identify(
        self,
        notes: List[AnkiNote],
        runtime_choice: str = None,
        runtime_config: RuntimeConfig = None,
        ignore_cache: bool = False,
        use_test_cache: bool = False,
        cancellation_token: CancellationToken = NONE_TOKEN
    ) -> List[AnkiNote]:
        """
        Perform Lexical Unit Identification on a list of AnkiNote objects using the selected runtime.
        If runtime_choice is None, pick a default runtime.
        """
        if runtime_choice and runtime_choice in self.runtimes:
            runtime = self.runtimes[runtime_choice]
        else:
            # Pick default runtime (first in dict)
            runtime = next(iter(self.runtimes.values()))

        # Convert AnkiNotes to LUIInput objects
        lui_inputs: List[LUIInput] = []
        for note in notes:
            # Use source_usage if available, otherwise use context_sentence
            sentence = note.source_usage or note.context_sentence
            if sentence and note.source_word:  # Only process notes with required fields
                lui_input = LUIInput(
                    uid=note.uid,
                    word=note.source_word,
                    sentence=sentence
                )
                lui_inputs.append(lui_input)

        if not lui_inputs:
            get_logger().info("No notes with required fields for lexical unit identification")
            return notes

        # Identify using the runtime
        lui_outputs: List[LUIOutput] = runtime.identify(
            lui_inputs,
            runtime_config=runtime_config,
            ignore_cache=ignore_cache,
            use_test_cache=use_test_cache,
            cancellation_token=cancellation_token
        )

        # Map LUI results back to AnkiNote objects
        lui_map = {}
        for lui_input, lui_output in zip(lui_inputs, lui_outputs):
            lui_map[lui_input.uid] = lui_output

        # Apply LUI results to notes
        for note in notes:
            if note.uid in lui_map:
                lui_result = lui_map[note.uid]
                note.expression = lui_result.lemma
                note.part_of_speech = lui_result.part_of_speech
                note.aspect = lui_result.aspect
                note.surface_lexical_unit = lui_result.surface_lexical_unit
                note.unit_type = lui_result.unit_type
                note.add_generation_metadata(self.id, runtime.id, runtime_config.model_id, runtime_config.prompt_id)

        return notes
