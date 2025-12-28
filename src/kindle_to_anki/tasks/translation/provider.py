# tasks/translation/provider.py
from typing import List

from anki.anki_note import AnkiNote
from core.runtimes.runtime_config import RuntimeConfig
from tasks.translation.schema import TranslationInput, TranslationOutput


class TranslationProvider:
    id = "translation"
    description = "Translation provider supporting multiple runtimes"

    def __init__(self, runtimes: dict):
        """
        runtimes: dict mapping runtime IDs to runtime instances
                  e.g., {"gpt-5-mini": llm_runtime1, "deepl": deepl_runtime, "manual": manual_runtime}
        """
        self.runtimes = runtimes

    def get_task_methods(self):
        """Expose task to orchestrator"""
        return {"translation": self.translate}

    def translate(
        self,
        notes: List[AnkiNote],
        runtime_choice: str = None,
        runtime_config: RuntimeConfig = None,
        ignore_cache: bool = False,
        use_test_cache: bool = False
    ) -> List[AnkiNote]:
        """
        Translate a list of AnkiNote objects using the selected runtime.
        If runtime_choice is None, pick a default runtime.
        """
        if runtime_choice and runtime_choice in self.runtimes:
            runtime = self.runtimes[runtime_choice]
        else:
            # Pick default runtime (first in dict)
            runtime = next(iter(self.runtimes.values()))

        # Convert AnkiNotes to TranslationInput objects
        translation_inputs: List[TranslationInput] = []
        for note in notes:
            # Use kindle_usage if available, otherwise use context_sentence
            context = note.kindle_usage or note.context_sentence
            if context:  # Only process notes with context
                translation_input = TranslationInput(
                    uid=note.uid,
                    context=context
                )
                translation_inputs.append(translation_input)

        if not translation_inputs:
            print("No notes with context to translate")
            return notes

        # Translate using the runtime
        translation_outputs: List[TranslationOutput] = runtime.translate(
            translation_inputs,
            runtime_config,
            ignore_cache=ignore_cache,
            use_test_cache=use_test_cache
        )

        # Map translation results back to AnkiNote objects
        translation_map = {}
        for translation_input, translation_output in zip(translation_inputs, translation_outputs):
            translation_map[translation_input.uid] = translation_output.translation

        # Apply translations to notes
        for note in notes:
            if note.uid in translation_map:
                note.context_translation = translation_map[note.uid]

        return notes
