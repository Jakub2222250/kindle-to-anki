#!/usr/bin/env python3
"""
Integration test for Word Sense Disambiguation via LLM runtime.
Compares outputs across different models.
"""

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.tasks.wsd.runtime_chat_completion import ChatCompletionWSD
from kindle_to_anki.tasks.wsd.schema import WSDInput
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig

bootstrap_all()

MODELS = ["gpt-5.1", "gpt-5-mini", "gemini-3-flash"]

# Baseline outputs for A/B testing (original results before runtime modifications)
BASELINE_OUTPUTS = {
    ("pl", "en"): {
        "pl_en_1": {
            "gpt-5.1": "a burst or spray of light, sparks, or similar particles",
            "gpt-5-mini": "snop — a shaft or stream (of light or sparks); beam (here: a burst/stream of sparks)",
            "gemini-3-flash": "N/A"
        },
        "pl_en_2": {
            "gpt-5.1": "a cat (a small domesticated carnivorous mammal kept as a pet or for catching mice)",
            "gpt-5-mini": "kot — cat (domestic cat)",
            "gemini-3-flash": "N/A"
        }
    },
    ("en", "pl"): {
        "en_pl_1": {
            "gpt-5.1": "sposób wyrażania się charakterystyczny dla danej dziedziny, środowiska lub grupy; fachowe określenia używane w danym języku lub kontekście",
            "gpt-5-mini": "terminologia, żargon lub sposób wyrażania się używany w określonym kontekście",
            "gemini-3-flash": "N/A"
        },
        "en_pl_2": {
            "gpt-5.1": "dawać pewność, że coś na pewno nastąpi, będzie prawdziwe lub zostanie spełnione; stanowić gwarancję czegoś",
            "gpt-5-mini": "gwarantować, zapewniać (sprawić, że coś na pewno będzie miało miejsce lub będzie przyjmowane)",
            "gemini-3-flash": "N/A"
        }
    }
}

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


def run_wsd_comparison(source_lang: str, target_lang: str):
    """Run WSD comparison across models for a specific language pair."""
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

    runtime = ChatCompletionWSD()
    results_by_model = {}

    for model_id in MODELS:
        print(f"\n--- Running {model_id} ---")
        runtime_config = RuntimeConfig(model_id=model_id, batch_size=len(wsd_inputs), source_language_code=source_lang, target_language_code=target_lang)

        outputs = runtime.disambiguate(
            wsd_inputs,
            runtime_config=runtime_config,
            use_test_cache=True,
            ignore_cache=True
        )
        results_by_model[model_id] = outputs

    # Print comparison
    print(f"\n{'=' * 80}")
    print(f"WSD COMPARISON ({source_lang} -> {target_lang})")
    print(f"{'=' * 80}")

    baselines = BASELINE_OUTPUTS.get((source_lang, target_lang), {})

    for i, test_case in enumerate(test_cases):
        print(f"\n[{test_case['word']} -> {test_case['lemma']}] {test_case['sentence']}")
        print("-" * 60)
        for model_id in MODELS:
            definition = results_by_model[model_id][i].definition
            baseline = baselines.get(test_case['uid'], {}).get(model_id, "N/A")
            print(f"  {model_id:15} | NEW: {definition}")
            print(f"  {' ':15} | OLD: {baseline}")

        # Verify all models produced output
        for model_id in MODELS:
            assert results_by_model[model_id][i].definition, f"Empty definition from {model_id} for {test_case['word']}"

    print(f"\n✓ WSD comparison ({source_lang} -> {target_lang}) completed")


def test_wsd_runtime_llm():
    """Integration test comparing WSD across models."""
    for (source_lang, target_lang) in TEST_CASES.keys():
        run_wsd_comparison(source_lang, target_lang)


if __name__ == "__main__":
    test_wsd_runtime_llm()
