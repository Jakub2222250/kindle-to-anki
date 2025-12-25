#!/usr/bin/env python3
"""
Test runner for all integration tests.
Run this script to execute all integration tests in the proper order.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def run_all_tests():
    """Run all integration tests."""
    
    print("=" * 80)
    print("RUNNING ALL INTEGRATION TESTS")
    print("=" * 80)
    print()
    
    test_modules = [
        ('tests.kindle_to_anki.lexical_unit_identification.providers.test_lui_llm', 'LLM Lexical Unit Identification'),
        ('tests.kindle_to_anki.lexical_unit_identification.providers.test_lui_polish_hybrid', 'Polish Hybrid Lexical Unit Identification'),
        ('tests.kindle_to_anki.lexical_unit_identification.providers.pl_en.test_ma_polish_sgjp_helper', 'Polish SGJP Helper'),
        ('tests.kindle_to_anki.pruning.test_pruning', 'Note Pruning'),
        ('tests.kindle_to_anki.wsd.providers.test_wsd_llm', 'Word Sense Disambiguation (LLM)'),
        ('tests.kindle_to_anki.translation.providers.test_polish_translator_local', 'Polish Local Translation'),
        ('tests.kindle_to_anki.translation.providers.test_translator_llm', 'LLM Translation')
    ]
    
    for module_name, test_name in test_modules:
        print(f"Running {test_name}...")
        try:
            # Import and run the test module
            module = __import__(module_name, fromlist=[''])
            if hasattr(module, '__main__'):
                # Execute the module's main section
                exec(compile(open(module.__file__).read(), module.__file__, 'exec'))
            print(f"✓ {test_name} completed")
        except Exception as e:
            print(f"✗ {test_name} failed: {e}")
        print("-" * 40)
        print()

if __name__ == "__main__":
    run_all_tests()