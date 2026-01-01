#!/usr/bin/env python3
"""
Integration test for Usage Level estimation via LLM runtime.
"""

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.tasks.usage_level.runtime_chat_completion import ChatCompletionUsageLevel
from kindle_to_anki.tasks.usage_level.schema import UsageLevelInput
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

bootstrap_all()

TEST_CASES = {
    "pl": [
        {
            'uid': 'pl_usage_1',
            'word': 'snop',
            'lemma': 'snop',
            'sentence': 'Z końca różdżki wytrysnął snop iskier, który ugodził w klamkę.',
            'pos': 'noun',
            'definition': 'sheaf, bundle'
        },
        {
            'uid': 'pl_usage_2',
            'word': 'koty',
            'lemma': 'kot',
            'sentence': 'Koty lubią spać w słońcu.',
            'pos': 'noun',
            'definition': 'cat'
        }
    ],
}


def run_usage_level_test(source_lang: str):
    """Run usage level test for a specific language."""
    test_cases = TEST_CASES.get(source_lang, [])
    if not test_cases:
        print(f"No test cases for {source_lang}")
        return
    
    usage_inputs = [
        UsageLevelInput(
            uid=case['uid'],
            word=case['word'],
            lemma=case['lemma'],
            pos=case['pos'],
            sentence=case['sentence'],
            definition=case['definition']
        )
        for case in test_cases
    ]
    
    print(f"\nTesting Usage Level runtime ({source_lang}) with {len(usage_inputs)} inputs...")
    
    runtime = ChatCompletionUsageLevel()
    runtime_config = RuntimeConfig(model_id="gpt-5.1", batch_size=2, source_language_code=source_lang, target_language_code="en")
    
    outputs = runtime.estimate(
        usage_inputs,
        runtime_config=runtime_config,
        use_test_cache=True,
        ignore_cache=True
    )
    
    print(f"Usage Level completed. Got {len(outputs)} outputs.")
    
    for i, (output_item, test_case) in enumerate(zip(outputs, test_cases)):
        print(f"\nTest case {i+1}: {test_case['lemma']}")
        print(f"Definition: {test_case['definition']}")
        print(f"Usage level: {output_item.usage_level}")
        
        assert output_item.usage_level is None or (isinstance(output_item.usage_level, int) and 1 <= output_item.usage_level <= 5), f"Invalid usage level for test case {i+1}"
    
    print(f"\n✓ Usage Level runtime test ({source_lang}) completed successfully")


def test_usage_level_runtime_llm():
    """Integration test of Usage Level estimation via LLM runtime."""
    for source_lang in TEST_CASES.keys():
        run_usage_level_test(source_lang)


if __name__ == "__main__":
    test_usage_level_runtime_llm()
