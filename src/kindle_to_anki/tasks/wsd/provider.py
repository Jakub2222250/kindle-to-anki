# tasks/wsd/provider.py
from typing import List

from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from .schema import WSDInput, WSDOutput


class WSDProvider:
    id = "wsd"
    description = "Word Sense Disambiguation provider supporting multiple runtimes"

    def __init__(self, runtimes: dict):
        """
        runtimes: dict mapping runtime IDs to runtime instances
                  e.g., {"gpt-5-mini": llm_runtime1, "claude": claude_runtime}
        """
        self.runtimes = runtimes

    def get_task_methods(self):
        """Expose task to orchestrator"""
        return {"wsd": self.disambiguate}

    def disambiguate(
        self,
        notes: List[AnkiNote],
        runtime_choice: str = None,
        runtime_config: RuntimeConfig = None,
        ignore_cache: bool = False,
        use_test_cache: bool = False
    ) -> List[AnkiNote]:
        """
        Perform Word Sense Disambiguation on a list of AnkiNote objects using the selected runtime.
        If runtime_choice is None, pick a default runtime.
        """
        if runtime_choice and runtime_choice in self.runtimes:
            runtime = self.runtimes[runtime_choice]
        else:
            # Pick default runtime (first in dict)
            runtime = next(iter(self.runtimes.values()))

        # Convert AnkiNotes to WSDInput objects
        wsd_inputs: List[WSDInput] = []
        for note in notes:
            # Only process notes with required fields
            if note.kindle_usage and note.expression and note.kindle_word:
                pos_tag = getattr(note, 'pos_tag', 'unknown')
                wsd_input = WSDInput(
                    uid=note.uid,
                    word=note.kindle_word,
                    lemma=note.expression,
                    pos=pos_tag,
                    sentence=note.kindle_usage
                )
                wsd_inputs.append(wsd_input)

        if not wsd_inputs:
            print("No notes with required fields for WSD")
            return notes

        # Process WSD using the runtime
        wsd_outputs: List[WSDOutput] = runtime.disambiguate(
            wsd_inputs,
            runtime_config,
            ignore_cache=ignore_cache,
            use_test_cache=use_test_cache
        )

        # Map WSD results back to AnkiNote objects
        wsd_map = {}
        for wsd_input, wsd_output in zip(wsd_inputs, wsd_outputs):
            wsd_map[wsd_input.uid] = wsd_output

        # Apply WSD results to notes
        for note in notes:
            if note.uid in wsd_map:
                wsd_result = wsd_map[note.uid]
                # Create a dict that matches the expected format for apply_wsd_results
                wsd_data = {
                    "definition": wsd_result.definition,
                    "original_language_definition": wsd_result.original_language_definition,
                    "cloze_deletion_score": wsd_result.cloze_deletion_score
                }
                note.apply_wsd_results(wsd_data)
                note.notes = note.notes + (f"\n{self.id}: runtime: {runtime.id}, {runtime_config.model_id}")

        return notes