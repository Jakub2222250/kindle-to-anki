#!/usr/bin/env python3
"""
Integration test for collocation generation via LLM runtime.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'src'))

from kindle_to_anki.tasks.collocation.runtime_chat_completion import ChatCompletionCollocation
from kindle_to_anki.tasks.collocation.schema import CollocationInput
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.anki.anki_note import AnkiNote


def test_collocation_runtime_llm():
    """Test LLM-based collocation generation runtime."""
    
    test_cases = [
        {
            'uid': 'test_1',
            'word': 'dzieci',
            'lemma': 'dziecko',
            'sentence': 'Dzieci bawią się na placu zabaw.',
            'pos': 'noun'
        },
        {
            'uid': 'test_2', 
            'word': 'książki',
            'lemma': 'książka',
            'sentence': 'Książki leżą na półce w bibliotece.',
            'pos': 'noun'
        }
    ]
    
    # Create collocation inputs
    collocation_inputs = [
        CollocationInput(
            uid=case['uid'],
            word=case['word'],
            lemma=case['lemma'], 
            pos=case['pos'],
            sentence=case['sentence']
        )
        for case in test_cases
    ]
    
    print(f"Testing collocation runtime with {len(collocation_inputs)} inputs...")
    
    # Create runtime and config
    runtime = ChatCompletionCollocation()
    runtime_config = RuntimeConfig(model_id="gpt-5-mini", batch_size=2)
    
    # Test collocation generation
    try:
        outputs = runtime.generate_collocations(
            collocation_inputs, 
            source_lang="pl", 
            target_lang="en",
            runtime_config=runtime_config,
            use_test_cache=True
        )
        
        print(f"Collocation generation completed. Got {len(outputs)} outputs.")
        
        for i, (input_item, output_item, test_case) in enumerate(zip(collocation_inputs, outputs, test_cases)):
            print(f"\nTest case {i+1}: {test_case['word']} (lemma: {test_case['lemma']})")
            print(f"Sentence: {test_case['sentence']}")
            print(f"Collocations: {output_item.collocations}")
            
            # Basic validation
            assert isinstance(output_item.collocations, list), f"Collocations should be a list for test case {i+1}"
            assert len(output_item.collocations) <= 3, f"Too many collocations for test case {i+1}"
            
        print("\n✓ Collocation runtime test completed successfully")
        
    except Exception as e:
        print(f"✗ Collocation runtime test failed: {e}")
        raise


if __name__ == "__main__":
    test_collocation_runtime_llm()