
from .collocation.task import CollocationTask
from .translation.task import TranslationTask
from .wsd.task import WSDTask
from .collect_candidates.task import CollectCandidatesTask
from .lui.task import LUITask


TASKS = [
    CollectCandidatesTask.id,
    LUITask.id,
    WSDTask.id,
    TranslationTask.id,
    CollocationTask.id
]
