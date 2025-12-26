from tasks.collect_candidates.schema import CandidateInput, CandidateOutput


class CollectCandidatesTask:
    id = "collect_candidates"
    name = "Candidate Collection"
    description = "Collect candidate vocabulary data from various sources for Anki card creation"
    input_schema = CandidateInput
    output_schema = CandidateOutput
