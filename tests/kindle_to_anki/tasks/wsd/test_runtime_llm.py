#!/usr/bin/env python3
"""
Integration test for Word Sense Disambiguation via LLM runtime.
"""

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.tasks.wsd.runtime_chat_completion import ChatCompletionWSD
from kindle_to_anki.tasks.wsd.schema import WSDInput
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

bootstrap_all()

# Test cases per language pair: (source_lang, target_lang) -> list of test cases
TEST_CASES = {
    ("pl", "en"): [
        {
            'uid': 'pl_en_1',  # General example
            'word': 'snop',
            'lemma': 'snop',
            'sentence': 'Z końca różdżki wytrysnął snop iskier, który ugodził w klamkę.',
            'pos': 'noun'
        },
        {
            'uid': 'pl_en_2',  # Plural vs singular example
            'word': 'koty',
            'lemma': 'kot',
            'sentence': 'Koty lubią spać w słońcu.',
            'pos': 'noun'
        }
    ],
    ("en", "pl"): [
        {
            'uid': 'en_pl_1',
            'word': 'parlance',  # plural
            'lemma': 'parlance',    # singular
            'sentence': 'Using the parlance, each object is an instance of a class, in which “class” is synonymous with “type.”',
            'pos': 'noun'
        },
        {
            'uid': 'en_pl_2',
            'word': 'guarantee',      # plural
            'lemma': 'guarantee',      # singular
            'sentence': 'Because an object of type “circle” is also an object of type “shape,” a circle is guaranteed to accept shape messages.',
            'pos': 'verb'
        }
    ],
}


def run_wsd_test(source_lang: str, target_lang: str):
    """Run WSD test for a specific language pair."""
    test_cases = TEST_CASES.get((source_lang, target_lang), [])
    if not test_cases:
        print(f"No test cases for {source_lang} -> {target_lang}")
        return
    
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
    
    print(f"\nTesting WSD runtime ({source_lang} -> {target_lang}) with {len(wsd_inputs)} inputs...")
    
    runtime = ChatCompletionWSD()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=2, source_language_code=source_lang, target_language_code=target_lang)
    
    outputs = runtime.disambiguate(
        wsd_inputs,
        runtime_config=runtime_config,
        use_test_cache=True,
        ignore_cache=True
    )
    
    print(f"WSD completed. Got {len(outputs)} outputs.")
    
    for i, (output_item, test_case) in enumerate(zip(outputs, test_cases)):
        print(f"\nTest case {i+1}: {test_case['word']} (lemma: {test_case['lemma']})")
        print(f"Sentence: {test_case['sentence']}")
        print(f"Definition: {output_item.definition}")
        print(f"Source language hint: {output_item.source_language_hint}")
        
        assert output_item.definition, f"Empty definition for test case {i+1}"
        assert output_item.source_language_hint, f"Empty source language hint for test case {i+1}"
    
    print(f"\n✓ WSD runtime test ({source_lang} -> {target_lang}) completed successfully")


def test_wsd_runtime_llm():
    """Integration test of Word Sense Disambiguation via LLM runtime - focus on plural forms with singular lemmas."""
    for (source_lang, target_lang) in TEST_CASES.keys():
        run_wsd_test(source_lang, target_lang)


if __name__ == "__main__":
    test_wsd_runtime_llm()