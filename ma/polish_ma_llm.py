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

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)}
        ],
    )

    # Strict JSON parsing — fail fast if the model misbehaves
    content = response.choices[0].message.content

    print("LLM Response:")
    print(content)

    return json.loads(content)


def perform_wsd_on_lemma_and_pos(notes: list[AnkiNote]):

    items = []

    for note in notes:
        item = dict()
        item["uid"] = note.uid
        item["token"] = note.kindle_word
        item["sentence"] = note.kindle_usage
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


def update_notes_with_llm(notes):
    disambiguation_results = perform_wsd_on_lemma_and_pos(notes)
    for i, note in enumerate(notes):
        disamb_result = disambiguation_results[i]

        selected_index = disamb_result['candidate_index']
        _, _, interpretation = note.morfeusz_candidates[selected_index]

        absorb_się = disamb_result['absorb_się']

        # Get lemma
        lemma = interpretation[1]
        if absorb_się:
            lemma = lemma + ' się'

        # Get part of speech
        tag = interpretation[2]
        readable_pos = morfeusz_tag_to_pos_string(tag)

        # Update note with normal MA fields
        note.expression = lemma
        note.part_of_speech = readable_pos
