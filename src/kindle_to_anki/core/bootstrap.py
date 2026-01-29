from kindle_to_anki.platforms.platform_registry import PlatformRegistry
from kindle_to_anki.platforms.openai_platform import OpenAIPlatform
from kindle_to_anki.platforms.grok_platform import GrokPlatform
from kindle_to_anki.platforms.gemini_platform import GeminiPlatform
from kindle_to_anki.platforms.deepl_platform import DeepLPlatform

from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.core.models.model_loader import load_models_from_yaml

from kindle_to_anki.core.runtimes.runtime_registry import RuntimeRegistry
from kindle_to_anki.tasks.lui.runtime_chat_completion import ChatCompletionLUI
from kindle_to_anki.tasks.translation.runtime_chat_completion import ChatCompletionTranslation
from kindle_to_anki.tasks.translation.runtime_deepl import DeepLTranslation
from kindle_to_anki.tasks.translation.runtime_polish_local import PolishLocalTranslation
from kindle_to_anki.tasks.wsd.runtime_chat_completion import ChatCompletionWSD
from kindle_to_anki.tasks.hint.runtime_chat_completion import ChatCompletionHint
from kindle_to_anki.tasks.cloze_scoring.runtime_chat_completion import ChatCompletionClozeScoring
from kindle_to_anki.tasks.usage_level.runtime_chat_completion import ChatCompletionUsageLevel
from kindle_to_anki.tasks.collocation.runtime_chat_completion import ChatCompletionCollocation
from kindle_to_anki.tasks.collect_candidates.runtime_kindle import KindleCandidateRuntime

_bootstrapped = False


def bootstrap_platform_registry():
    PlatformRegistry.register(OpenAIPlatform())
    PlatformRegistry.register(GrokPlatform())
    PlatformRegistry.register(GeminiPlatform())
    PlatformRegistry.register(DeepLPlatform())


def bootstrap_model_registry():
    for model in load_models_from_yaml():
        ModelRegistry.register(model)


def bootstrap_runtime_registry():
    RuntimeRegistry.register(ChatCompletionLUI())
    RuntimeRegistry.register(ChatCompletionTranslation())
    RuntimeRegistry.register(DeepLTranslation())
    RuntimeRegistry.register(ChatCompletionWSD())
    RuntimeRegistry.register(ChatCompletionHint())
    RuntimeRegistry.register(ChatCompletionClozeScoring())
    RuntimeRegistry.register(ChatCompletionUsageLevel())
    RuntimeRegistry.register(ChatCompletionCollocation())
    RuntimeRegistry.register(PolishLocalTranslation())
    RuntimeRegistry.register(KindleCandidateRuntime())


def bootstrap_all():
    global _bootstrapped
    if _bootstrapped:
        return
    bootstrap_platform_registry()
    bootstrap_model_registry()
    bootstrap_runtime_registry()
    _bootstrapped = True
