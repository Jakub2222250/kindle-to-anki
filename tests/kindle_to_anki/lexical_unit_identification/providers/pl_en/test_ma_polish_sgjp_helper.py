#!/usr/bin/env python3
"""
Integration test for Polish SGJP helper functions.
"""
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'src'))

from lexical_unit_identification.providers.pl_en.ma_polish_sgjp_helper import normalize_adj_to_masc_sg


def test_normalize_adj_to_masc_sg():
    """
    Integration test for normalize_adj_to_masc_sg function.
    Tests various Polish adjective inflections and edge cases.
    """
    test_cases = [
        # Test cases that were previously failing
        ("kościstym", "kościsty"),  # instrumental masculine singular
        ("tęgi", "tęgi"),           # already masculine singular (stem ends in 'g')
        ("pieszczotliwym", "pieszczotliwy"),  # instrumental masculine singular
        ("mosiężnych", "mosiężny"),  # genitive/locative plural

        # Standard inflection patterns
        ("duże", "duży"),           # neuter/plural nominative
        ("dużego", "duży"),         # genitive masculine singular
        ("dużemu", "duży"),         # dative masculine singular
        ("dużymi", "duży"),         # instrumental plural
        ("dużych", "duży"),         # genitive/locative plural
        ("dużej", "duży"),          # genitive/dative/locative feminine singular
        ("dużą", "duży"),           # accusative/instrumental feminine singular

        # Stems ending in k/g (should get 'i' not 'y')
        ("polskiego", "polski"),    # genitive masculine singular
        ("polskich", "polski"),     # genitive/locative plural
        ("głębokiego", "głęboki"),  # genitive masculine singular
        ("głębokich", "głęboki"),   # genitive/locative plural

        # Adjectives ending in 'i' that should change to 'y'
        ("zieloni", "zielony"),     # nominative masculine personal plural
        ("dobri", "dobry"),         # hypothetical case

        # Adjectives ending in 'i' that should stay as 'i' (k/g stems)
        ("wielki", "wielki"),       # already correct masculine singular
        ("długi", "długi"),         # already correct masculine singular

        # Edge cases and other forms
        ("piękna", "piękny"),       # feminine nominative singular
        ("piękne", "piękny"),       # neuter nominative singular or plural
        ("młodym", "młody"),        # instrumental masculine singular
        ("starych", "stary"),       # genitive/locative plural

        # Additional test cases
        ("włochata", "włochaty"),   # feminine nominative singular
        ("pulchna", "pulchny"),     # feminine nominative singular  
        ("bystra", "bystry"),       # feminine nominative singular
        ("kiełkowa", "kiełkowy"),   # feminine nominative singular
        ("wierne", "wierny"),       # neuter nominative singular or plural
        ("niemym", "niemy"),        # instrumental masculine singular

        # Words that should remain unchanged (already masc sg or unknown forms)
        ("nieznany", "nieznany"),   # already masculine singular
        ("xyz", "xyz"),             # unknown word
    ]

    passed = 0
    failed = 0

    for input_adj, expected in test_cases:
        result = normalize_adj_to_masc_sg(input_adj)

        if result == expected:
            print(f"Test PASSED for adjective '{input_adj}': got expected normalized form '{result}'")
            passed += 1
        else:
            print(f"Test FAILED for adjective '{input_adj}': expected '{expected}', got '{result}'")
            failed += 1

    return failed == 0


def test_ma_polish_sgjp_helper():
    """Test normalize adj to masc sg function."""
    return test_normalize_adj_to_masc_sg()


if __name__ == "__main__":
    test_ma_polish_sgjp_helper()