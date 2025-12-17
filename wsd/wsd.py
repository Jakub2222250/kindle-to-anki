from anki.anki_note import AnkiNote
from wsd.wsd_llm_provider import provide_wsd_with_llm


def provide_word_sense_disambiguation(notes: list[AnkiNote], source_language_code: str, target_language_code: str, ignore_cache=False):
    provide_wsd_with_llm(notes, source_language_code, target_language_code, ignore_cache=ignore_cache)
