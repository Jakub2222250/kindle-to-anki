#!/usr/bin/env python3
"""
Integration test for Cloze Scoring via LLM runtime.
"""

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.tasks.cloze_scoring.runtime_chat_completion import ChatCompletionClozeScoring
from kindle_to_anki.tasks.cloze_scoring.schema import ClozeScoringInput
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

bootstrap_all()

TEST_CASES = {
    "pl": [
        {
            'uid': 'pl_cloze_1',
            'word': 'snop',
            'lemma': 'snop',
            'sentence': 'Z końca różdżki wytrysnął snop iskier, który ugodził w klamkę.',
            'pos': 'noun'
        },
        {
            'uid': 'pl_cloze_2',
            'word': 'koty',
            'lemma': 'kot',
            'sentence': 'Koty lubią spać w słońcu.',
            'pos': 'noun'
        }
    ],
}


def run_cloze_scoring_test(source_lang: str):
    """Run cloze scoring test for a specific language."""
    test_cases = TEST_CASES.get(source_lang, [])
    if not test_cases:
        print(f"No test cases for {source_lang}")
        return
    
    scoring_inputs = [
        ClozeScoringInput(
            uid=case['uid'],
            word=case['word'],
            lemma=case['lemma'],
            pos=case['pos'],
            sentence=case['sentence']
        )
        for case in test_cases
    ]
    
    print(f"\nTesting Cloze Scoring runtime ({source_lang}) with {len(scoring_inputs)} inputs...")
    
    runtime = ChatCompletionClozeScoring()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=2, source_language_code=source_lang, target_language_code="en")
    
    outputs = runtime.score(
        scoring_inputs,
        runtime_config=runtime_config,
        use_test_cache=True,
        ignore_cache=True
    )
    
    print(f"Cloze Scoring completed. Got {len(outputs)} outputs.")
    
    for i, (output_item, test_case) in enumerate(zip(outputs, test_cases)):
        print(f"\nTest case {i+1}: {test_case['word']}")
        print(f"Sentence: {test_case['sentence']}")
        print(f"Cloze score: {output_item.cloze_deletion_score}")
        
        assert isinstance(output_item.cloze_deletion_score, int), f"Invalid cloze score type for test case {i+1}"
        assert 0 <= output_item.cloze_deletion_score <= 10, f"Invalid cloze score range for test case {i+1}"
    
    print(f"\n✓ Cloze Scoring runtime test ({source_lang}) completed successfully")


def test_cloze_scoring_runtime_llm():
    """Integration test of Cloze Scoring via LLM runtime."""
    for source_lang in TEST_CASES.keys():
        run_cloze_scoring_test(source_lang)


if __name__ == "__main__":
    test_cloze_scoring_runtime_llm()
