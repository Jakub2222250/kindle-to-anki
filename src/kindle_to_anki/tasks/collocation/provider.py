# tasks/collocation/provider.py
from typing import List

from kindle_to_anki.logging import get_logger
from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.util.cancellation import CancellationToken, NONE_TOKEN
from kindle_to_anki.tasks.collocation.schema import CollocationInput, CollocationOutput


class CollocationProvider:
    id = "collocation"
    description = "Collocation provider supporting multiple runtimes"

    def __init__(self, runtimes: dict):
        """
        runtimes: dict mapping runtime IDs to runtime instances
                  e.g., {"gpt-5-mini": llm_runtime1, "claude": claude_runtime}
        """
        self.runtimes = runtimes

    def get_task_methods(self):
        """Expose task to orchestrator"""
        return {"collocation": self.generate_collocations}

    def generate_collocations(
        self,
        notes: List[AnkiNote],
        runtime_choice: str = None,
        runtime_config: RuntimeConfig = None,
        ignore_cache: bool = False,
        use_test_cache: bool = False,
        cancellation_token: CancellationToken = NONE_TOKEN
    ) -> List[AnkiNote]:
        """
        Generate collocations for a list of AnkiNote objects using the selected runtime.
        If runtime_choice is None, pick a default runtime.
        """
        if runtime_choice and runtime_choice in self.runtimes:
            runtime = self.runtimes[runtime_choice]
        else:
            # Pick default runtime (first in dict)
            runtime = next(iter(self.runtimes.values()))

        # Convert AnkiNotes to CollocationInput objects
        collocation_inputs: List[CollocationInput] = []
        for note in notes:
            # Only process notes with required fields
            if note.expression:
                pos_tag = getattr(note, 'pos_tag', 'unknown')
                collocation_input = CollocationInput(
                    uid=note.uid,
                    lemma=note.expression,
                    pos=pos_tag,
                )
                collocation_inputs.append(collocation_input)

        if not collocation_inputs:
            get_logger().info("No notes with required fields for collocation generation")
            return notes

        # Generate collocations using the runtime
        collocation_outputs: List[CollocationOutput] = runtime.generate_collocations(
            collocation_inputs,
            runtime_config,
            ignore_cache=ignore_cache,
            use_test_cache=use_test_cache,
            cancellation_token=cancellation_token
        )

        # Map collocation results back to AnkiNote objects
        collocation_map = {}
        for collocation_input, collocation_output in zip(collocation_inputs, collocation_outputs):
            collocation_map[collocation_input.uid] = collocation_output

        # Apply collocation results to notes
        for note in notes:
            if note.uid in collocation_map:
                collocation_result = collocation_map[note.uid]
                # Convert list to comma-separated string as expected by AnkiNote
                if isinstance(collocation_result.collocations, list):
                    note.collocations = ', '.join(collocation_result.collocations)
                else:
                    note.collocations = str(collocation_result.collocations)

                note.add_generation_metadata(self.id, runtime.id, runtime_config.model_id, runtime_config.prompt_id)

        return notes
