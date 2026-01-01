#!/usr/bin/env python3
"""
Integration test for Source Language Hint via LLM runtime.
"""

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.tasks.source_language_hint.runtime_chat_completion import ChatCompletionSourceLanguageHint
from kindle_to_anki.tasks.source_language_hint.schema import SourceLanguageHintInput
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

bootstrap_all()

TEST_CASES = {
    "pl": [
        {
            'uid': 'pl_hint_1',
            'word': 'snop',
            'lemma': 'snop',
            'sentence': 'Z końca różdżki wytrysnął snop iskier, który ugodził w klamkę.',
            'pos': 'noun'
        },
        {
            'uid': 'pl_hint_2',
            'word': 'koty',
            'lemma': 'kot',
            'sentence': 'Koty lubią spać w słońcu.',
            'pos': 'noun'
        }
    ],
}


def run_source_language_hint_test(source_lang: str):
    """Run source language hint test for a specific language."""
    test_cases = TEST_CASES.get(source_lang, [])
    if not test_cases:
        print(f"No test cases for {source_lang}")
        return
    
    hint_inputs = [
        SourceLanguageHintInput(
            uid=case['uid'],
            word=case['word'],
            lemma=case['lemma'],
            pos=case['pos'],
            sentence=case['sentence']
        )
        for case in test_cases
    ]
    
    print(f"\nTesting Source Language Hint runtime ({source_lang}) with {len(hint_inputs)} inputs...")
    
    runtime = ChatCompletionSourceLanguageHint()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=2, source_language_code=source_lang, target_language_code="en")
    
    outputs = runtime.generate(
        hint_inputs,
        runtime_config=runtime_config,
        use_test_cache=True,
        ignore_cache=True
    )
    
    print(f"Source Language Hint completed. Got {len(outputs)} outputs.")
    
    for i, (output_item, test_case) in enumerate(zip(outputs, test_cases)):
        print(f"\nTest case {i+1}: {test_case['word']}")
        print(f"Sentence: {test_case['sentence']}")
        print(f"Source language hint: {output_item.source_language_hint}")
        
        assert output_item.source_language_hint, f"Empty source language hint for test case {i+1}"
    
    print(f"\n✓ Source Language Hint runtime test ({source_lang}) completed successfully")


def test_source_language_hint_runtime_llm():
    """Integration test of Source Language Hint via LLM runtime."""
    for source_lang in TEST_CASES.keys():
        run_source_language_hint_test(source_lang)


if __name__ == "__main__":
    test_source_language_hint_runtime_llm()
