def morfeusz_tag_to_pos_string(morf_tag: str) -> str:
    """
    Convert a full Morfeusz tag string into a learner-facing POS label,
    optionally augmented with verbal aspect.

    Examples:
      "praet:sg:m1:imperf" -> "verb (impf)"
      "inf:perf"           -> "verb (perf)"
      "subst:sg:nom:m1"    -> "noun"
    """

    if not morf_tag:
        return "other"

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
            return "verb (impf)"
        if "perf" in features:
            return "verb (perf)"
        # biaspectual or unresolved
        return "verb"

    return pos


def normalize_adj_to_masc_sg(surface: str) -> str:
    hard_i = ("k", "g", "c", "dz", "s", "z", "n", "l")

    def choose_suffix(stem: str) -> str:
        return "i" if stem.endswith(hard_i) else "y"

    for suffix in (
        "ego", "emu", "ymi", "ich", "ej", "e", "a"
    ):
        if surface.endswith(suffix):
            stem = surface[: -len(suffix)]
            return stem + choose_suffix(stem)

    return surface  # fallback


def normalize_lemma(
    surface: str,
    morfeusz_lemma: str,
    pos: str,
    sgjp_tag: str | None = None
) -> str:

    if pos == "verb":
        return morfeusz_lemma

    if pos == "adv":
        return surface

    if pos == "adj":
        if sgjp_tag and "sg" in sgjp_tag and "nom" in sgjp_tag and "m" in sgjp_tag:
            return surface
        return normalize_adj_to_masc_sg(surface)

    if pos in {"noun", "subst"}:
        return morfeusz_lemma

    return surface
