from typing import List

from kindle_to_anki.logging import get_logger
from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.util.cancellation import CancellationToken, NONE_TOKEN
from .schema import ClozeScoringInput, ClozeScoringOutput


class ClozeScoringProvider:
    id = "cloze_scoring"
    description = "Cloze Scoring provider supporting multiple runtimes"

    def __init__(self, runtimes: dict):
        self.runtimes = runtimes

    def get_task_methods(self):
        return {"cloze_scoring": self.score}

    def score(
        self,
        notes: List[AnkiNote],
        runtime_choice: str = None,
        runtime_config: RuntimeConfig = None,
        ignore_cache: bool = False,
        use_test_cache: bool = False,
        cancellation_token: CancellationToken = NONE_TOKEN
    ) -> List[AnkiNote]:
        if runtime_choice and runtime_choice in self.runtimes:
            runtime = self.runtimes[runtime_choice]
        else:
            runtime = next(iter(self.runtimes.values()))

        scoring_inputs: List[ClozeScoringInput] = []
        for note in notes:
            if note.source_usage and note.expression and note.source_word:
                pos_tag = getattr(note, 'pos_tag', 'unknown')
                scoring_input = ClozeScoringInput(
                    uid=note.uid,
                    word=note.source_word,
                    lemma=note.expression,
                    pos=pos_tag,
                    sentence=note.source_usage
                )
                scoring_inputs.append(scoring_input)

        if not scoring_inputs:
            get_logger().info("No notes with required fields for cloze scoring")
            return notes

        scoring_outputs: List[ClozeScoringOutput] = runtime.score(
            scoring_inputs,
            runtime_config,
            ignore_cache=ignore_cache,
            use_test_cache=use_test_cache,
            cancellation_token=cancellation_token
        )

        score_map = {}
        for scoring_input, scoring_output in zip(scoring_inputs, scoring_outputs):
            score_map[scoring_input.uid] = scoring_output

        for note in notes:
            if note.uid in score_map:
                result = score_map[note.uid]
                note.apply_cloze_scoring_results({"cloze_deletion_score": result.cloze_deletion_score})
                note.add_generation_metadata(self.id, runtime.id, runtime_config.model_id, runtime_config.prompt_id)

        return notes
