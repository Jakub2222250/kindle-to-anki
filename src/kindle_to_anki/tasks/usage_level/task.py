from .schema import UsageLevelInput, UsageLevelOutput


class UsageLevelTask:
    id = "usage_level"
    name = "Usage Level"
    description = "Estimate word sense usage level for modern general usage"
    input_schema = UsageLevelInput
    output_schema = UsageLevelOutput
