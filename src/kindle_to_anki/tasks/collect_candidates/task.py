from kindle_to_anki.tasks.collect_candidates.schema import CandidateOutput


class CollectCandidatesTask:
    id = "collect_candidates"
    name = "Candidate Collection"
    description = "Collect candidate vocabulary data from various sources for Anki card creation"
    input_schema = None
    output_schema = CandidateOutput
