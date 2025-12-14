import json
from typing import List, Dict, Any
from openai import OpenAI


from anki.anki_note import AnkiNote
from ma.polish_ma_sgjp_helper import morfeusz_tag_to_pos_string


MA_WSD_LLM = "gpt-5-mini"


def disambiguate_lemma_pos(
    model: str,
    items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Resolves lemma for a batch of Polish tokens using context and
    Morfeusz options, determining whether 'się' should be absorbed.

    Returns:
        [
          {"candidate_index": 0, "absorb_się": true},
          ...
        ]
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
            "If 'się' appears adjacent to the token in the sentence, determine if it should be "
            "absorbed based on semantic necessity (e.g. for reflexive verbs where 'się' is integral "
            "to the meaning).\n"
            "- Absorb 'się' when it is semantically binding and essential to the verb's meaning\n"
            "- Do NOT absorb 'się' if removing it preserves the same core meaning "
            "(voice/diathesis alternation only)\n\n"
            "Prefer the analysis that best fits syntactic role, argument structure, "
            "and idiomatic or lexicalized usage.\n\n"
            "Return results as a JSON list in the form:\n"
            "[{\"candidate_index\": 0, \"absorb_się\": true}]\n"
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


def process_notes_in_batches(notes: list[AnkiNote], cache):

    # Process in batches
    batch_size = 20

    for batch_start in range(0, len(notes), batch_size):
        batch_notes = notes[batch_start:batch_start + batch_size]

        disambiguation_results = perform_wsd_on_lemma_and_pos(batch_notes)

        for i, note in enumerate(batch_notes):
            disamb_result = disambiguation_results[i]

            selected_index = disamb_result['candidate_index']
            _, _, interpretation = note.morfeusz_candidates[selected_index]

            absorb_się = disamb_result['absorb_się']

            # Get lemma
            lemma = interpretation[1].split(":")[0] if ":" in interpretation[1] else interpretation[1]
            if absorb_się:
                lemma = lemma + ' się'

            # Get part of speech
            tag = interpretation[2]
            readable_pos = morfeusz_tag_to_pos_string(tag)

            # Update note with normal MA fields
            note.morfeusz_tag = tag
            note.morfeusz_lemma = lemma
            note.part_of_speech = readable_pos


def update_notes_with_llm(notes):

    print(f"{len(notes)} notes need LLM MA processing.")

    # TODO resolve notes from cache if available. Then only process those that are missing if any.
    notes_needing_llm = notes

    result = input(f"Do you want to proceed with LLM MA processing for {len(notes)} notes? [y/n]: ").strip().lower()
    if result != 'y' and result != 'yes':
        print("LLM MA processing aborted by user.")
        exit()

    process_notes_in_batches(notes_needing_llm, cache=None)
