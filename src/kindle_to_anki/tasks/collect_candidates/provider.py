# tasks/collect_candidate/provider.py
from typing import List, Dict
from datetime import datetime

from anki.anki_note import AnkiNote
from .schema import CandidateInput, CandidateOutput


class CollectCandidatesProvider:
    id = "collect_candidates"
    description = "Candidate collection provider supporting multiple runtimes"

    def __init__(self, runtimes: dict):
        """
        runtimes: dict mapping runtime IDs to runtime instances
                  e.g., {"kindle": kindle_runtime, "manual": manual_runtime}
        """
        self.runtimes = runtimes

    def get_task_methods(self):
        """Expose task to orchestrator"""
        return {"collect_candidates": self.collect_candidates}

    def collect_candidates(
        self,
        db_path: str,
        runtime_choice: str = None,
        last_vocab_entry_timestamp: datetime = None,
        incremental: bool = True
    ) -> tuple[Dict[str, List[AnkiNote]], int]:
        """
        Collect candidate data using the selected runtime.
        If runtime_choice is None, pick a default runtime.
        Returns (notes_by_language, latest_timestamp)
        """
        if runtime_choice and runtime_choice in self.runtimes:
            runtime = self.runtimes[runtime_choice]
        else:
            # Pick default runtime (first in dict)
            runtime = next(iter(self.runtimes.values()))

        # Create CandidateInput for the runtime
        candidate_input = CandidateInput(
            db_path=db_path,
            last_timestamp=last_vocab_entry_timestamp,
            incremental=incremental
        )

        # Collect candidate data using the runtime
        candidate_outputs: List[CandidateOutput] = runtime.collect_candidates(candidate_input)

        if not candidate_outputs:
            print("No candidate data collected")
            return {}, 0

        # Convert CandidateOutput objects to AnkiNote objects and group by language
        notes_by_language = {}
        latest_timestamp = 0

        for candidate_output in candidate_outputs:
            # Create AnkiNote from CandidateOutput
            note = AnkiNote(
                word=candidate_output.word,
                stem=candidate_output.stem,
                usage=candidate_output.usage,
                language=candidate_output.language,
                book_name=candidate_output.book_title,
                position=candidate_output.position,
                timestamp=candidate_output.timestamp
            )

            # Group by language
            if candidate_output.language not in notes_by_language:
                notes_by_language[candidate_output.language] = []
            notes_by_language[candidate_output.language].append(note)

            # Track latest timestamp
            if candidate_output.timestamp > latest_timestamp:
                latest_timestamp = candidate_output.timestamp

        return notes_by_language, latest_timestamp