#!/usr/bin/env python3
"""
Integration test for Hint via LLM runtime.
Compares outputs across different models.
"""

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.tasks.hint.runtime_chat_completion import ChatCompletionHint
from kindle_to_anki.tasks.hint.schema import HintInput
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

bootstrap_all()

MODELS = ["gpt-5.1", "gpt-5-mini"]

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


def run_hint_comparison(source_lang: str):
    """Run hint comparison across models."""
    test_cases = TEST_CASES.get(source_lang, [])
    if not test_cases:
        print(f"No test cases for {source_lang}")
        return
    
    hint_inputs = [
        HintInput(
            uid=case['uid'],
            word=case['word'],
            lemma=case['lemma'],
            pos=case['pos'],
            sentence=case['sentence']
        )
        for case in test_cases
    ]
    
    runtime = ChatCompletionHint()
    results_by_model = {}
    
    for model_id in MODELS:
        print(f"\n--- Running {model_id} ---")
        runtime_config = RuntimeConfig(model_id=model_id, batch_size=len(hint_inputs), source_language_code=source_lang, target_language_code="en")
        
        outputs = runtime.generate(
            hint_inputs,
            runtime_config=runtime_config,
            use_test_cache=True,
            ignore_cache=True
        )
        results_by_model[model_id] = outputs
    
    # Print comparison
    print(f"\n{'='*80}")
    print(f"HINT COMPARISON ({source_lang})")
    print(f"{'='*80}")
    
    for i, test_case in enumerate(test_cases):
        print(f"\n[{test_case['word']}] {test_case['sentence']}")
        print("-" * 60)
        for model_id in MODELS:
            hint = results_by_model[model_id][i].hint
            print(f"  {model_id:15} | {hint}")
        
        # Verify all models produced output
        for model_id in MODELS:
            assert results_by_model[model_id][i].hint, f"Empty hint from {model_id} for {test_case['word']}"
    
    print(f"\n✓ Hint comparison ({source_lang}) completed")


def test_hint_runtime_llm():
    """Integration test comparing Hint across models."""
    for source_lang in TEST_CASES.keys():
        run_hint_comparison(source_lang)


if __name__ == "__main__":
    test_hint_runtime_llm()
