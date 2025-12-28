#!/usr/bin/env python3
"""
Integration test for LLM-based translation runtime.
"""

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.tasks.translation.runtime_chat_completion import ChatCompletionTranslation
from kindle_to_anki.tasks.translation.schema import TranslationInput
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.anki.anki_note import AnkiNote

bootstrap_all()


def test_translation_runtime_llm():
    """Test LLM-based translation runtime."""
    
    # Create test translation inputs
    translation_inputs = [
        TranslationInput(
            uid="test_1", 
            context="To jest przykład zdania do przetłumaczenia."
        ),
        TranslationInput(
            uid="test_2", 
            context="Kot śpi na kanapie w salonie."
        )
    ]
    
    print(f"Testing translation runtime with {len(translation_inputs)} inputs...")
    
    # Create runtime and config
    runtime = ChatCompletionTranslation()
    runtime_config = RuntimeConfig(model_id="gpt-5-mini", batch_size=2, source_language_code="pl", target_language_code="en")
    
    # Test translation
    try:
        outputs = runtime.translate(
            translation_inputs,
            runtime_config=runtime_config,
            use_test_cache=True
        )
        
        print(f"Translation completed. Got {len(outputs)} outputs.")
        
        for i, (input_item, output_item) in enumerate(zip(translation_inputs, outputs)):
            print(f"\nInput {i+1}: {input_item.context}")
            print(f"Output {i+1}: {output_item.translation}")
            
            # Basic validation
            assert output_item.translation, f"Empty translation for input {i+1}"
            assert len(output_item.translation) > 0, f"No translation content for input {i+1}"
            
        print("\n✓ Translation runtime test completed successfully")
        
    except Exception as e:
        print(f"✗ Translation runtime test failed: {e}")
        raise


if __name__ == "__main__":
    test_translation_runtime_llm()