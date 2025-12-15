def morfeusz_tag_to_pos_string(morf_tag: str) -> tuple[str, str]:
    """
    Convert a full Morfeusz tag string into a learner-facing POS label and aspect.

    Returns:
        tuple: (pos, aspect) where pos is the part of speech and aspect is 
               "" for non-verbs, or "impf"/"perf" for verbs

    Examples:
      "praet:sg:m1:imperf" -> ("verb", "impf")
      "inf:perf"           -> ("verb", "perf")
      "subst:sg:nom:m1"    -> ("noun", "")
    """

    if not morf_tag:
        return ("other", "")

    parts = morf_tag.split(":")
    base = parts[0]
    features = set(parts[1:])

    # --- POS mapping (coarse) ---
    if base in {"subst", "depr", "ger", "brev"}:
        pos = "noun"

    elif base in {
        "fin", "inf", "impt", "praet", "bedzie",
        "pcon", "pant"
    }:
        pos = "verb"

    elif base in {"adj", "adja", "adjp", "pact", "ppas"}:
        pos = "adj"

    elif base == "adv":
        pos = "adv"

    elif base in {"ppron12", "ppron3", "siebie", "pron"}:
        pos = "pron"

    elif base in {"num", "numcol", "numord", "numfrac"}:
        pos = "num"

    elif base == "prep":
        pos = "prep"

    elif base == "conj":
        pos = "conj"

    elif base in {"qub", "part", "pred"}:
        pos = "part"

    elif base == "interj":
        pos = "interj"

    else:
        pos = "other"

    # --- Aspect extraction (verbs only) ---
    if pos == "verb":
        if "imperf" in features:
            return (pos, "impf")
        if "perf" in features:
            return (pos, "perf")
        # biaspectual or unresolved
        return (pos, "")

    return (pos, "")


def normalize_adj_to_masc_sg(surface: str) -> str:
    # Stems ending in these consonants take 'i' instead of 'y'
    hard_consonants = ("k", "g")

    def choose_suffix(stem: str) -> str:
        # Check if stem ends with any hard consonant
        for consonant in hard_consonants:
            if stem.endswith(consonant):
                return "i"
        return "y"

    # Extended list of adjectival suffixes to handle more inflected forms
    for suffix in (
        "iego", "ego", "emu", "ymi", "ych", "ym", "ich", "ej", "e", "a", "ą", "em"
    ):
        if surface.endswith(suffix):
            stem = surface[: -len(suffix)]
            return stem + choose_suffix(stem)

    # Special case: if the adjective ends with "i", it might need to be changed to "y"
    # but only if it's not a stem that should end with "i" (like after k, g)
    if surface.endswith("i"):
        stem = surface[:-1]
        # Check if stem should keep 'i' (ends with hard consonant)
        for consonant in hard_consonants:
            if stem.endswith(consonant):
                return surface  # Keep the original 'i'
        return stem + "y"

    return surface  # fallback


def normalize_lemma(
    surface: str,
    morfeusz_lemma: str,
    pos: str,
    sgjp_tag: str | None = None
) -> str:

    surface_lower = surface.lower()

    if pos == "verb":
        return morfeusz_lemma

    if pos == "adv":
        return surface_lower

    if pos == "adj":
        if sgjp_tag and "sg" in sgjp_tag and "nom" in sgjp_tag and "m" in sgjp_tag:
            return surface_lower
        return normalize_adj_to_masc_sg(surface_lower)

    if pos in {"noun", "subst"}:
        return morfeusz_lemma

    return surface_lower


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


if __name__ == "__main__":
    test_normalize_adj_to_masc_sg()
