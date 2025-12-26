"""
Migration helper for transitioning from translator_llm.py to the new runtime system.
This module provides backward compatibility and migration utilities.
"""
from typing import List

from kindle_to_anki.anki.anki_note import AnkiNote
from kindle_to_anki.platforms.openai_platform import OpenAIPlatform
from kindle_to_anki.tasks.translation.runtime_chat_completion import ChatCompletionTranslation
from kindle_to_anki.tasks.translation.provider import TranslationProvider


# Backward compatibility function that mimics the old translate_context_with_llm signature
def translate_context_with_llm(notes: List[AnkiNote], source_lang_code: str, target_lang_code: str, ignore_cache=False, use_test_cache=False):
    """
    Backward compatibility wrapper for the old translate_context_with_llm function.
    
    This function provides the same interface as the original translator_llm.py function
    but uses the new structured runtime system under the hood.
    
    Args:
        notes: List of AnkiNote objects to translate
        source_lang_code: Source language code (e.g., 'pl', 'es')
        target_lang_code: Target language code (e.g., 'en') 
        ignore_cache: Whether to ignore existing cache
        use_test_cache: Whether to use test cache instead of production cache
    """
    
    # Setup the platform and runtime with the same model as the original
    platform = OpenAIPlatform()
    runtime = ChatCompletionTranslation(platform=platform, model_name="gpt-5", batch_size=30)
    
    # Setup the provider
    runtimes = {"gpt-5": runtime}
    provider = TranslationProvider(runtimes=runtimes)
    
    # Translate using the provider
    provider.translate(
        notes=notes,
        runtime_choice="gpt-5",
        source_lang=source_lang_code,
        target_lang=target_lang_code, 
        ignore_cache=ignore_cache,
        use_test_cache=use_test_cache
    )


def create_translation_runtime(model_name: str = "gpt-5", batch_size: int = 30, platform=None):
    """
    Helper function to create a properly configured translation runtime.
    
    Args:
        model_name: The LLM model to use (default: "gpt-5")
        batch_size: Number of translations per batch (default: 30)
        platform: ChatCompletionPlatform instance (default: creates OpenAIPlatform)
    
    Returns:
        Configured ChatCompletionTranslation runtime
    """
    if platform is None:
        platform = OpenAIPlatform()
    
    return ChatCompletionTranslation(
        platform=platform, 
        model_name=model_name, 
        batch_size=batch_size
    )


def create_translation_provider(runtimes_config: dict = None):
    """
    Helper function to create a translation provider with common runtime configurations.
    
    Args:
        runtimes_config: Dict mapping runtime names to config dicts, e.g.:
                        {
                            "gpt-5": {"model_name": "gpt-5", "batch_size": 30},
                            "gpt-4": {"model_name": "gpt-4", "batch_size": 20}
                        }
                        If None, creates a default gpt-5 runtime.
    
    Returns:
        Configured TranslationProvider
    """
    if runtimes_config is None:
        runtimes_config = {"gpt-5": {"model_name": "gpt-5", "batch_size": 30}}
    
    runtimes = {}
    platform = OpenAIPlatform()  # Reuse the same platform for all runtimes
    
    for runtime_name, config in runtimes_config.items():
        runtime = ChatCompletionTranslation(
            platform=platform,
            model_name=config["model_name"],
            batch_size=config.get("batch_size", 30)
        )
        runtimes[runtime_name] = runtime
    
    return TranslationProvider(runtimes=runtimes)