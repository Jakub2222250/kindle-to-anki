#!/usr/bin/env python3
"""
Integration test for Word Sense Disambiguation via LLM runtime.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from kindle_to_anki.tasks.wsd.runtime_chat_completion import ChatCompletionWSD
from kindle_to_anki.tasks.wsd.schema import WSDInput
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig


def test_wsd_runtime_llm():
    """Integration test of Word Sense Disambiguation via LLM runtime - focus on plural forms with singular lemmas."""
    
    test_cases = [
        {
            'uid': 'test_1',
            'word': 'dzieci',  # plural
            'lemma': 'dziecko',       # singular
            'sentence': 'Dzieci bawią się na placu zabaw.',
            'pos': 'noun'
        },
        {
            'uid': 'test_2',
            'word': 'koty',    # plural
            'lemma': 'kot',           # singular
            'sentence': 'Koty lubią spać w słońcu.',
            'pos': 'noun'
        }
    ]
    
    # Create WSD inputs
    wsd_inputs = [
        WSDInput(
            uid=case['uid'],
            word=case['word'],
            lemma=case['lemma'],
            pos=case['pos'],
            sentence=case['sentence']
        )
        for case in test_cases
    ]
    
    print(f"Testing WSD runtime with {len(wsd_inputs)} inputs...")
    
    # Create runtime and config
    runtime = ChatCompletionWSD()
    runtime_config = RuntimeConfig(model_id="gpt-5-mini", batch_size=2)
    
    # Test WSD
    try:
        outputs = runtime.disambiguate(
            wsd_inputs, 
            source_lang="pl", 
            target_lang="en",
            runtime_config=runtime_config,
            use_test_cache=True
        )
        
        print(f"WSD completed. Got {len(outputs)} outputs.")
        
        for i, (input_item, output_item, test_case) in enumerate(zip(wsd_inputs, outputs, test_cases)):
            print(f"\nTest case {i+1}: {test_case['word']} (lemma: {test_case['lemma']})")
            print(f"Sentence: {test_case['sentence']}")
            print(f"Definition: {output_item.definition}")
            print(f"Original definition: {output_item.original_language_definition}")
            print(f"Cloze score: {output_item.cloze_deletion_score}")
            
            # Basic validation
            assert output_item.definition, f"Empty definition for test case {i+1}"
            assert output_item.original_language_definition, f"Empty original definition for test case {i+1}"
            assert isinstance(output_item.cloze_deletion_score, int), f"Invalid cloze score type for test case {i+1}"
            assert 0 <= output_item.cloze_deletion_score <= 10, f"Invalid cloze score range for test case {i+1}"
            
        print("\n✓ WSD runtime test completed successfully")
        
    except Exception as e:
        print(f"✗ WSD runtime test failed: {e}")
        raise


if __name__ == "__main__":
    test_wsd_runtime_llm()