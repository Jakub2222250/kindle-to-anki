import string
from typing import List

from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.platforms.platform_registry import PlatformRegistry
from .schema import LUIInput, LUIOutput
from .pl_en.ma_polish_hybrid_llm import update_notes_with_llm
from .pl_en.ma_polish_sgjp_helper import morfeusz_tag_to_pos_string, normalize_lemma
from kindle_to_anki.anki.anki_note import AnkiNote


class PolishMALLMHybridLUI:
    """
    Runtime for Polish Lexical Unit Identification using Morfeusz2 morphological analyzer
    combined with LLM for disambiguation when needed.
    
    This is a hybrid approach that uses:
    1. Morfeusz2 to get all possible morphological analyses
    2. Simple heuristics for clear cases (single candidate, no complex particles)
    3. LLM for complex disambiguation (multiple candidates, reflexive verbs with 'się')
    """
    
    id: str = "polish_ma_llm_hybrid_lui"
    display_name: str = "Polish MA+LLM Hybrid LUI Runtime"
    supported_tasks = ["lui"]
    supported_model_families = ["chat_completion"]
    supports_batching: bool = True

    def __init__(self):
        """
        Initialize the Polish MA+LLM hybrid runtime.
        """
        pass

    def identify(self, lui_inputs: List[LUIInput], source_lang: str, target_lang: str, 
                config: RuntimeConfig, ignore_cache: bool = False, use_test_cache: bool = False) -> List[LUIOutput]:
        """
        Perform Lexical Unit Identification on Polish words using Morfeusz2 + LLM hybrid approach.
        
        Args:
            lui_inputs: List of LUIInput objects containing word and sentence context
            source_lang: Source language (should be "pl" for Polish)
            target_lang: Target language 
            config: Runtime configuration containing model settings
            ignore_cache: Whether to ignore LLM cache
            use_test_cache: Whether to use test cache
            
        Returns:
            List of LUIOutput objects with identified lexical units
        """
        if source_lang != "pl":
            raise ValueError(f"PolishMALLMHybridLUI only supports Polish (pl), got {source_lang}")

        try:
            import morfeusz2
        except ImportError:
            raise ImportError("morfeusz2 library is required for Polish morphological analysis. Please install it via 'pip install morfeusz2'.")

        print(f"\nStarting Polish MA+LLM hybrid lexical unit identification for {len(lui_inputs)} items...")

        morf = morfeusz2.Morfeusz()
        
        # Convert LUIInputs to temporary AnkiNotes for processing with existing logic
        temp_notes = []
        for lui_input in lui_inputs:
            note = AnkiNote(
                uid=lui_input.uid,
                kindle_word=lui_input.word,
                kindle_usage=lui_input.sentence
            )
            temp_notes.append(note)

        # Process with Morfeusz and determine which need LLM
        notes_requiring_llm_ma = []
        num_notes_not_requiring_llm_ma = 0

        for note in temp_notes:
            # Get candidates from Morfeusz
            candidates = morf.analyse(note.kindle_word.lower())
            note.morfeusz_candidates = candidates

            requires_llm_ma = self._check_if_requires_llm_ma(note)

            # Simple case - use first candidate
            if not requires_llm_ma:
                self._update_note_without_llm(note)
                num_notes_not_requiring_llm_ma += 1
            else:
                notes_requiring_llm_ma.append(note)

        print(f"{num_notes_not_requiring_llm_ma} notes did not require LLM MA processing.")

        # Process complex cases with LLM
        if len(notes_requiring_llm_ma) > 0:
            # Get model and platform from registries using config
            # Note: For now assuming OpenAI platform since that's what was used directly before
            # In the future this could be made more dynamic
            model = None
            platform = None
            if config and config.model_id:
                try:
                    model = ModelRegistry.get("openai", config.model_id)
                    platform = PlatformRegistry.get(model.platform)
                except KeyError:
                    print(f"Warning: Model {config.model_id} not found in registry, falling back to defaults")
            
            cache_suffix = 'pl-en_hybrid'
            if use_test_cache:
                cache_suffix += "_test"
            
            # Pass platform and model to the updated function
            update_notes_with_llm(
                notes_requiring_llm_ma, 
                cache_suffix=cache_suffix, 
                ignore_cache=ignore_cache,
                platform=platform,
                model=model.id if model else "gpt-5"  # fallback to previous default
            )

        # Post-process all notes for reflexive verbs and lemma normalization
        for note in temp_notes:
            if "się" in note.morfeusz_lemma:
                note.original_form = self._absorb_nearest_sie(note.kindle_word, note.kindle_usage)
                # Set unit_type to reflexive for verbs with się
                note.unit_type = "reflexive"
            else:
                # Set unit_type to lemma for regular words
                note.unit_type = "lemma"

            # Normalize morfeusz lemma to best lemma for Anki learning now that final POS is known
            # Morfeusz lemma already has "się" absorbed if applicable for verbs
            note.expression = normalize_lemma(note.original_form, note.morfeusz_lemma, note.part_of_speech, note.morfeusz_tag)

        # Convert back to LUIOutputs
        lui_outputs = []
        for note in temp_notes:
            lui_output = LUIOutput(
                lemma=note.expression,
                part_of_speech=note.part_of_speech,
                aspect=getattr(note, 'aspect', ''),
                original_form=getattr(note, 'original_form', note.kindle_word),
                unit_type=getattr(note, 'unit_type', 'lemma')
            )
            lui_outputs.append(lui_output)

        return lui_outputs

    def _select_first_candidate(self, candidates):
        """Select first morphological analysis candidate."""
        return candidates[0]

    def _update_note_without_llm(self, note: AnkiNote):
        """Update note with first Morfeusz candidate without LLM disambiguation."""
        candidates = note.morfeusz_candidates
        _, _, interpretation = self._select_first_candidate(candidates)

        # Extract lemma and tag
        lemma_raw = interpretation[1]
        lemma = lemma_raw.split(':')[0] if ':' in lemma_raw else lemma_raw
        tag = interpretation[2]

        # Map SGJP tag to readable POS
        readable_pos, aspect = morfeusz_tag_to_pos_string(tag)

        note.morfeusz_tag = tag
        note.morfeusz_lemma = lemma
        note.part_of_speech = readable_pos
        note.aspect = aspect

    def _has_sie_adjacent_to_word(self, usage_text, target_word):
        """
        Check if 'się' appears immediately before or after the first occurrence of target_word.
        Handles punctuation cleanly by ignoring non-alphabetic characters when comparing.
        """
        lowercase_usage = usage_text.lower()
        words_list = lowercase_usage.split()

        # Find the first occurrence of the target_word
        target_word_lower = target_word.lower()
        target_index = None

        for i, word in enumerate(words_list):
            # Remove punctuation from word for comparison
            clean_word = ''.join(char for char in word if char.isalpha())
            if clean_word == target_word_lower:
                target_index = i
                break

        if target_index is None:
            return False

        # Check if "się" appears just before the target word
        if target_index > 0:
            prev_word = words_list[target_index - 1]
            clean_prev_word = ''.join(char for char in prev_word if char.isalpha())
            if clean_prev_word == "się":
                return True

        # Check if "się" appears just after the target word
        if target_index < len(words_list) - 1:
            next_word = words_list[target_index + 1]
            clean_next_word = ''.join(char for char in next_word if char.isalpha())
            if clean_next_word == "się":
                return True

        return False

    def _check_if_requires_llm_ma(self, note: AnkiNote):
        """
        Determine if a note requires LLM-based morphological analysis.
        
        LLM is needed if:
        1. "się" is adjacent to the word (reflexive verbs need context-aware analysis)
        2. Multiple morphological candidates exist (disambiguation needed)
        """
        # Check if "się" is adjacent to the word
        has_sie_before_or_after = self._has_sie_adjacent_to_word(note.kindle_usage, note.kindle_word)

        # Identify if the word has only one candidate
        has_single_candidate = len(note.morfeusz_candidates) == 1

        return has_sie_before_or_after or not has_single_candidate

    def _absorb_nearest_sie(self, kindle_word, usage_text):
        """
        Find the nearest 'się' to the first occurrence of kindle_word and return
        all text between them (inclusive). Returns the absorbed phrase as a string.

        Args:
            kindle_word: The target word to find
            usage_text: The sentence containing the word

        Returns:
            String containing 'się' and all words between it and kindle_word
        """
        words_list = usage_text.split()

        # Find the first occurrence of the target word
        target_word_lower = kindle_word.lower()
        target_index = None

        for i, word in enumerate(words_list):
            # Remove punctuation from word for comparison
            clean_word = ''.join(char for char in word if char.isalpha())
            if clean_word.lower() == target_word_lower:
                target_index = i
                break

        if target_index is None:
            return kindle_word  # Fallback if word not found

        # Find all occurrences of "się"
        sie_indices = []
        for i, word in enumerate(words_list):
            clean_word = ''.join(char for char in word if char.isalpha())
            if clean_word.lower() == "się":
                sie_indices.append(i)

        if not sie_indices:
            return kindle_word  # No "się" found, return original word

        # Find the nearest "się" to the target word
        nearest_sie_index = min(sie_indices, key=lambda x: abs(x - target_index))

        # Determine the range to extract (inclusive)
        start_index = min(nearest_sie_index, target_index)
        end_index = max(nearest_sie_index, target_index)

        # Extract the words between and including "się" and the target word
        absorbed_words = words_list[start_index:end_index + 1]
        result = ' '.join(absorbed_words)

        # Trim punctuation from the beginning and end of the result
        result = result.strip(string.punctuation + ' ')

        return result
