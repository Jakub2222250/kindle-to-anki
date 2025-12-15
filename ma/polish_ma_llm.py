import json
import time
from typing import List, Dict, Any
from pathlib import Path
from openai import OpenAI


from anki.anki_note import AnkiNote
from ma.polish_ma_sgjp_helper import morfeusz_tag_to_pos_string


class MACache:
    def __init__(self, cache_dir="cache", cache_suffix='default'):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / f"ma_cache-{cache_suffix}.json"

        # Load existing cache
        self.cache = self.load_cache()

    def load_cache(self):
        """Load cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return {}

    def save_cache(self):
        """Save cache to file"""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    def get(self, uid):
        """Get cached MA result for UID"""
        cache_entry = self.cache.get(uid)
        if cache_entry and isinstance(cache_entry, dict) and "ma_data" in cache_entry:
            return cache_entry["ma_data"]
        return None

    def set(self, uid, ma_result, model_used=None, timestamp=None):
        """Set cached MA result for UID"""
        cache_entry = {
            "ma_data": ma_result,
            "model_used": model_used,
            "timestamp": timestamp
        }
        self.cache[uid] = cache_entry
        self.save_cache()


MA_WSD_LLM = "gpt-5-mini"


def disambiguate_lemma_pos(
    model: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Resolves lemma for a batch of Polish tokens using context and
    Morfeusz options, determining whether 'się' should be absorbed.

    Returns:
        {
          "uid1": {"candidate_index": 0, "absorb_się": true},
          "uid2": {"candidate_index": 1, "absorb_się": false},
          ...
        }
    """

    system_prompt = (
        "You are a linguistic disambiguation engine. "
        "You must output valid JSON only. "
        "No explanations, no extra text."
    )

    user_prompt = {
        "instruction": (
            "For each item, select exactly ONE lemma from the morfeusz_options by providing its index.\n"
            "Also determine whether 'się' should be absorbed with the token.\n\n"
            "CRITICAL: Only absorb 'się' if ALL of these conditions are met:\n"
            "1. The token is a VERB (check the sgjp_tag - must be a verb form)\n"
            "2. 'się' appears adjacent to the token in the sentence (can be separated by 'nie')\n"
            "3. 'się' is syntactically bound to THIS SPECIFIC verb token (not to another verb in the sentence)\n"
            "4. 'się' is semantically essential to the verb's meaning (reflexive/reciprocal verbs)\n\n"
            "Do NOT absorb 'się' if:\n"
            "- The token is a noun, adjective, adverb, or any non-verb part of speech\n"
            "- 'się' belongs to a different verb in the sentence\n"
            "- 'się' is just a voice alternation (removing it preserves the core meaning)\n"
            "- 'się' appears near the token but is not syntactically related to it\n\n"
            "Examples:\n"
            "- 'uczy się' → absorb_się: true (reflexive verb)\n"
            "- 'się nie boi' → absorb_się: true (reflexive verb with negation)\n"
            "- 'nie boi się' → absorb_się: true (reflexive verb with negation)\n"
            "- 'nie boi' (without się) → absorb_się: false (no się to absorb)\n"
            "- 'pozbyłem się zjawy' → for token 'zjawy': absorb_się: false (noun, się belongs to 'pozbyłem')\n"
            "- 'zatrzymał się' → absorb_się: true (reflexive verb)\n\n"
            "Prefer the analysis that best fits syntactic role, argument structure, "
            "and idiomatic or lexicalized usage.\n\n"
            "Return results as a JSON object where keys are the UIDs and values are the analysis objects:\n"
            "{\"uid1\": {\"candidate_index\": 0, \"absorb_się\": true}, \"uid2\": {\"candidate_index\": 1, \"absorb_się\": false}}\n"
            "where candidate_index is the 0-based index of the selected option from morfeusz_options "
            "and absorb_się is a boolean indicating whether 'się' should be absorbed."
        ),
        "items": items,
    }

    client = OpenAI()

    print("\nSending LLM disambiguation request...")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)}
        ],
    )

    # Strict JSON parsing — fail fast if the model misbehaves
    content = response.choices[0].message.content

    print("Sending LLM disambiguation request completed.")

    return json.loads(content)


def perform_wsd_on_lemma_and_pos(notes: list[AnkiNote]):

    items = []

    for note in notes:
        item = dict()
        item["uid"] = note.uid
        item["token"] = note.kindle_word
        # Clean whitespace: remove leading/trailing spaces and normalize internal whitespace
        cleaned_sentence = " ".join(note.kindle_usage.split())
        item["sentence"] = cleaned_sentence
        morfeusz_candidates = note.morfeusz_candidates
        item["morfeusz_options"] = []
        for _, lemma, interpretation in morfeusz_candidates:
            tag = interpretation[2]
            item["morfeusz_options"].append(
                {"lemma": lemma, "sgjp_tag": tag}
            )
        items.append(item)

    # Call the LLM disambiguation function
    disambiguate_lemma_pos_response = disambiguate_lemma_pos(MA_WSD_LLM, items)

    # Return the results directly (lemma and candidate_index for each item)
    return disambiguate_lemma_pos_response


def process_notes_in_batches(notes: list[AnkiNote], cache: MACache):

    # Capture timestamp at the start of MA processing
    processing_timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # Process in batches
    batch_size = 20
    total_batches = (len(notes) + batch_size - 1) // batch_size
    failing_notes = []

    for i in range(0, len(notes), batch_size):
        batch = notes[i:i + batch_size]
        batch_num = (i // batch_size) + 1

        print(f"\nProcessing batch {batch_num}/{total_batches} ({len(batch)} notes)")

        try:
            disambiguation_results = perform_wsd_on_lemma_and_pos(batch)

            for note in batch:
                if note.uid in disambiguation_results:
                    disamb_result = disambiguation_results[note.uid]

                    selected_index = disamb_result['candidate_index']
                    _, _, interpretation = note.morfeusz_candidates[selected_index]

                    absorb_się = disamb_result['absorb_się']

                    # Get part of speech first for validation
                    tag = interpretation[2]
                    readable_pos, aspect = morfeusz_tag_to_pos_string(tag)

                    # Validate absorb_się - only verbs can absorb się
                    if absorb_się and 'verb' not in readable_pos.lower():
                        print(f"    WARNING: Overriding absorb_się=True for non-verb '{note.kindle_word}' ({readable_pos})")
                        absorb_się = False

                    # Get lemma
                    lemma = interpretation[1].split(":")[0] if ":" in interpretation[1] else interpretation[1]
                    if absorb_się:
                        lemma = lemma + ' się'

                    # Create MA result for caching
                    ma_result = {
                        "candidate_index": selected_index,
                        "absorb_się": absorb_się,
                        "morfeusz_lemma": lemma,
                        "morfeusz_tag": tag,
                        "part_of_speech": readable_pos,
                        "aspect": aspect
                    }

                    # Save to cache
                    cache.set(note.uid, ma_result, MA_WSD_LLM, processing_timestamp)

                    # Update note with normal MA fields
                    note.morfeusz_tag = tag
                    note.morfeusz_lemma = lemma
                    note.part_of_speech = readable_pos
                    note.aspect = aspect

                    print(f"  SUCCESS - processed MA for {note.kindle_word}")
                else:
                    print(f"  FAILED - no result for {note.kindle_word}")
                    failing_notes.append(note)

        except Exception as e:
            print(f"  BATCH FAILED - {str(e)}")
            failing_notes.extend(batch)

    if len(failing_notes) > 0:
        print(f"{len(failing_notes)} notes failed MA processing.")
        print("All successful MA results already saved to cache. Running script again usually fixes the issue. Exiting.")
        exit()


def update_notes_with_llm(notes, cache_suffix='pl', ignore_cache=False):
    """Process MA enrichment for all notes"""

    print("\nStarting LLM MA processing...")

    cache = MACache(cache_suffix=cache_suffix)
    notes_needing_llm = []

    if not ignore_cache:
        print(f"Loaded MA cache with {len(cache.cache)} entries")

        # Phase 1: Collect notes that need LLM MA processing

        cached_count = 0

        for note in notes:
            cached_result = cache.get(note.uid)
            if cached_result:
                cached_count += 1
                # Apply cached MA result
                note.morfeusz_tag = cached_result['morfeusz_tag']
                note.morfeusz_lemma = cached_result['morfeusz_lemma']
                note.part_of_speech = cached_result['part_of_speech']
                note.aspect = cached_result['aspect']
            else:
                notes_needing_llm.append(note)

        print(f"Found {cached_count} cached results, {len(notes_needing_llm)} notes need LLM calls")
    else:
        notes_needing_llm = notes
        print("Ignoring cache as per user request. Fresh results will be generated.")

    if not notes_needing_llm:
        print("LLM MA processing completed.")
        return

    result = input(f"\nDo you want to proceed with LLM MA processing for {len(notes_needing_llm)} notes? [y/n]: ").strip().lower()
    if result != 'y' and result != 'yes':
        print("LLM MA processing aborted by user.")
        exit()

    # Phase 2: Process notes in batches
    process_notes_in_batches(notes_needing_llm, cache)

    print("LLM MA processing completed.")
