import customtkinter as ctk
from typing import Callable, Optional
import threading

from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.configuration.config_manager import ConfigManager
from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.core.runtimes.runtime_config import RuntimeConfig
from kindle_to_anki.core.runtimes.runtime_registry import RuntimeRegistry
from kindle_to_anki.core.prompts import get_default_prompt_id, get_lui_default_prompt_id
from kindle_to_anki.tasks.collect_candidates.provider import CollectCandidatesProvider
from kindle_to_anki.tasks.translation.provider import TranslationProvider
from kindle_to_anki.tasks.wsd.provider import WSDProvider
from kindle_to_anki.tasks.hint.provider import HintProvider
from kindle_to_anki.tasks.cloze_scoring.provider import ClozeScoringProvider
from kindle_to_anki.tasks.usage_level.provider import UsageLevelProvider
from kindle_to_anki.tasks.collocation.provider import CollocationProvider
from kindle_to_anki.tasks.lui.provider import LUIProvider
from kindle_to_anki.metadata.metdata_manager import MetadataManager
from kindle_to_anki.export.export_anki import write_anki_import_file
from kindle_to_anki.pruning.pruning import (
    prune_existing_notes_automatically,
    prune_existing_notes_by_UID,
    prune_new_notes_against_eachother,
    prune_notes_identified_as_redundant
)


class ExportView(ctk.CTkFrame):
    """Export vocabulary view - runs the main export pipeline with progress display."""

    def __init__(self, master, on_back: Callable):
        super().__init__(master)
        self.on_back = on_back
        self.is_running = False
        self.export_thread: Optional[threading.Thread] = None

        self._create_widgets()

    def _create_widgets(self):
        # Header with back button
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        back_btn = ctk.CTkButton(
            header,
            text="← Back",
            width=80,
            command=self._on_back_clicked
        )
        back_btn.pack(side="left")

        title = ctk.CTkLabel(
            header,
            text="Export Vocabulary",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(side="left", padx=20)

        # Progress section
        progress_frame = ctk.CTkFrame(self)
        progress_frame.pack(fill="x", padx=10, pady=10)

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Ready to export",
            font=ctk.CTkFont(size=14)
        )
        self.status_label.pack(pady=10)

        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=400)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)

        self.step_label = ctk.CTkLabel(
            progress_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        )
        self.step_label.pack(pady=(0, 10))

        # Output log placeholder
        log_frame = ctk.CTkFrame(self)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)

        log_header = ctk.CTkLabel(
            log_frame,
            text="Output Log",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        log_header.pack(anchor="w", padx=10, pady=(10, 5))

        # Large output textbox (placeholder for future log streaming)
        self.log_textbox = ctk.CTkTextbox(
            log_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled"
        )
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Control buttons
        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=10, pady=10)

        self.start_btn = ctk.CTkButton(
            buttons_frame,
            text="Start Export",
            width=150,
            command=self._start_export
        )
        self.start_btn.pack(side="left", padx=5)

        self.cancel_btn = ctk.CTkButton(
            buttons_frame,
            text="Cancel",
            width=100,
            state="disabled",
            command=self._cancel_export
        )
        self.cancel_btn.pack(side="left", padx=5)

    def _on_back_clicked(self):
        if self.is_running:
            # Could add confirmation dialog here
            pass
        self.on_back()

    def _log(self, message: str):
        """Append message to the log textbox."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def _update_progress(self, step: int, total: int, status: str, detail: str = ""):
        """Update progress bar and status labels."""
        self.progress_bar.set(step / total if total > 0 else 0)
        self.status_label.configure(text=status)
        self.step_label.configure(text=detail)
        self._log(f"[{step}/{total}] {status}" + (f" - {detail}" if detail else ""))

    def _start_export(self):
        """Start the export process in a background thread."""
        self.is_running = True
        self.start_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")

        # Clear log
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

        self.export_thread = threading.Thread(target=self._run_export, daemon=True)
        self.export_thread.start()

    def _cancel_export(self):
        """Request cancellation of the export process."""
        self.is_running = False
        self._log("Cancellation requested...")

    def _run_export(self):
        """Run the export pipeline (mirrors main.py logic)."""
        try:
            self._export_pipeline()
        except Exception as e:
            self.after(0, lambda: self._log(f"Error: {str(e)}"))
        finally:
            self.after(0, self._export_finished)

    def _export_finished(self):
        """Called when export completes or fails."""
        self.is_running = False
        self.start_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.progress_bar.set(1)
        self.status_label.configure(text="Export completed")
        self.step_label.configure(text="")

    def _export_pipeline(self):
        """Main export pipeline - mirrors main.py structure."""
        total_steps = 14

        # Step 1: Bootstrap
        self.after(0, lambda: self._update_progress(1, total_steps, "Bootstrapping...", "Initializing runtimes"))
        bootstrap_all()

        if not self.is_running:
            return

        # Step 2: Setup providers
        self.after(0, lambda: self._update_progress(2, total_steps, "Setting up providers...", ""))
        candidate_provider = CollectCandidatesProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("collect_candidates"))
        translation_provider = TranslationProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("translation"))
        wsd_provider = WSDProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("wsd"))
        hint_provider = HintProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("hint"))
        cloze_scoring_provider = ClozeScoringProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("cloze_scoring"))
        usage_level_provider = UsageLevelProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("usage_level"))
        collocation_provider = CollocationProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("collocation"))
        lui_provider = LUIProvider(runtimes=RuntimeRegistry.find_by_task_as_dict("lui"))

        if not self.is_running:
            return

        # Step 3: Load configuration
        self.after(0, lambda: self._update_progress(3, total_steps, "Loading configuration...", ""))
        config_manager = ConfigManager()
        anki_decks_by_source_language = config_manager.get_anki_decks_by_source_language()

        if not self.is_running:
            return

        # Step 4: Collect candidates
        self.after(0, lambda: self._update_progress(4, total_steps, "Collecting candidates...", "Reading Kindle vocabulary"))
        notes_by_language, latest_candidate_timestamp = candidate_provider.collect_candidates(runtime_choice="kindle")

        if not notes_by_language or len(notes_by_language) == 0:
            self.after(0, lambda: self._log("No candidate notes collected."))
            return

        if not self.is_running:
            return

        # Step 5: Connect to Anki
        self.after(0, lambda: self._update_progress(5, total_steps, "Connecting to Anki...", ""))
        anki_connect_instance = AnkiConnect()

        # Process each language
        for source_language_code, notes in notes_by_language.items():
            if not self.is_running:
                return

            anki_deck = anki_decks_by_source_language.get(source_language_code)
            if not anki_deck:
                self.after(0, lambda slc=source_language_code: self._log(f"No deck configured for language: {slc}"))
                continue

            target_language_code = anki_deck.target_language_code
            language_pair_code = anki_deck.get_language_pair_code()

            self.after(0, lambda slc=source_language_code, n=len(notes): 
                       self._log(f"Processing {n} notes for {slc}"))

            # Get existing notes and prune
            existing_notes = anki_connect_instance.get_notes(anki_deck)
            notes = prune_existing_notes_by_UID(notes, existing_notes)
            if len(notes) == 0:
                self.after(0, lambda slc=source_language_code: 
                           self._log(f"No new notes after UID pruning for {slc}"))
                continue

            notes = prune_notes_identified_as_redundant(notes, cache_suffix=language_pair_code)
            if len(notes) == 0:
                self.after(0, lambda slc=source_language_code: 
                           self._log(f"No new notes after redundancy pruning for {slc}"))
                continue

            if not self.is_running:
                return

            # Step 6: LUI
            self.after(0, lambda: self._update_progress(6, total_steps, "Lexical Unit Identification...", ""))
            lui_setting = anki_deck.get_task_setting("lui")
            lui_prompt_id = lui_setting.get("prompt_id") or get_lui_default_prompt_id(source_language_code)
            lui_provider.identify(
                notes=notes,
                runtime_choice=lui_setting["runtime"],
                runtime_config=RuntimeConfig(
                    model_id=lui_setting["model_id"],
                    batch_size=lui_setting["batch_size"],
                    source_language_code=source_language_code,
                    target_language_code=target_language_code,
                    prompt_id=lui_prompt_id
                ),
                ignore_cache=False
            )

            if not self.is_running:
                return

            # Step 7: WSD
            self.after(0, lambda: self._update_progress(7, total_steps, "Word Sense Disambiguation...", ""))
            wsd_setting = anki_deck.get_task_setting("wsd")
            wsd_prompt_id = wsd_setting.get("prompt_id") or get_default_prompt_id("wsd")
            wsd_provider.disambiguate(
                notes=notes,
                runtime_choice=wsd_setting["runtime"],
                runtime_config=RuntimeConfig(
                    model_id=wsd_setting["model_id"],
                    batch_size=wsd_setting["batch_size"],
                    source_language_code=source_language_code,
                    target_language_code=target_language_code,
                    prompt_id=wsd_prompt_id
                ),
                ignore_cache=False
            )

            # Prune after WSD
            notes = prune_existing_notes_automatically(notes, existing_notes, cache_suffix=language_pair_code)
            notes = prune_new_notes_against_eachother(notes)
            if len(notes) == 0:
                self.after(0, lambda slc=source_language_code: 
                           self._log(f"No new notes after pruning for {slc}"))
                continue

            if not self.is_running:
                return

            # Step 8: Hint generation (optional)
            hint_setting = anki_deck.get_task_setting("hint")
            if hint_setting.get("enabled", True):
                self.after(0, lambda: self._update_progress(8, total_steps, "Generating hints...", ""))
                hint_prompt_id = hint_setting.get("prompt_id") or get_default_prompt_id("hint")
                hint_provider.generate(
                    notes=notes,
                    runtime_choice=hint_setting["runtime"],
                    runtime_config=RuntimeConfig(
                        model_id=hint_setting["model_id"],
                        batch_size=hint_setting["batch_size"],
                        source_language_code=source_language_code,
                        target_language_code=target_language_code,
                        prompt_id=hint_prompt_id
                    ),
                    ignore_cache=False
                )

            if not self.is_running:
                return

            # Step 9: Cloze scoring (optional)
            cloze_setting = anki_deck.get_task_setting("cloze_scoring")
            if cloze_setting.get("enabled", True):
                self.after(0, lambda: self._update_progress(9, total_steps, "Scoring cloze suitability...", ""))
                cloze_prompt_id = cloze_setting.get("prompt_id") or get_default_prompt_id("cloze_scoring")
                cloze_scoring_provider.score(
                    notes=notes,
                    runtime_choice=cloze_setting["runtime"],
                    runtime_config=RuntimeConfig(
                        model_id=cloze_setting["model_id"],
                        batch_size=cloze_setting["batch_size"],
                        source_language_code=source_language_code,
                        target_language_code=target_language_code,
                        prompt_id=cloze_prompt_id
                    ),
                    ignore_cache=False
                )
            else:
                for note in notes:
                    note.cloze_enabled = "?"

            if not self.is_running:
                return

            # Step 10: Usage level (optional)
            usage_level_setting = anki_deck.get_task_setting("usage_level")
            if usage_level_setting.get("enabled", True):
                self.after(0, lambda: self._update_progress(10, total_steps, "Estimating usage levels...", ""))
                usage_level_prompt_id = usage_level_setting.get("prompt_id") or get_default_prompt_id("usage_level")
                usage_level_provider.estimate(
                    notes=notes,
                    runtime_choice=usage_level_setting["runtime"],
                    runtime_config=RuntimeConfig(
                        model_id=usage_level_setting["model_id"],
                        batch_size=usage_level_setting["batch_size"],
                        source_language_code=source_language_code,
                        target_language_code=target_language_code,
                        prompt_id=usage_level_prompt_id
                    ),
                    ignore_cache=False
                )

            if not self.is_running:
                return

            # Step 11: Translation
            self.after(0, lambda: self._update_progress(11, total_steps, "Translating...", ""))
            translation_setting = anki_deck.get_task_setting("translation")
            translation_prompt_id = translation_setting.get("prompt_id") or get_default_prompt_id("translation")
            translation_provider.translate(
                notes=notes,
                runtime_choice=translation_setting["runtime"],
                runtime_config=RuntimeConfig(
                    model_id=translation_setting["model_id"],
                    batch_size=translation_setting["batch_size"],
                    source_language_code=source_language_code,
                    target_language_code=target_language_code,
                    prompt_id=translation_prompt_id
                ),
                ignore_cache=False,
                use_test_cache=False
            )

            if not self.is_running:
                return

            # Step 12: Collocations (optional)
            collocation_setting = anki_deck.get_task_setting("collocation")
            if collocation_setting.get("enabled", True):
                self.after(0, lambda: self._update_progress(12, total_steps, "Generating collocations...", ""))
                collocation_prompt_id = collocation_setting.get("prompt_id") or get_default_prompt_id("collocation")
                collocation_provider.generate_collocations(
                    notes=notes,
                    runtime_choice=collocation_setting["runtime"],
                    runtime_config=RuntimeConfig(
                        model_id=collocation_setting["model_id"],
                        batch_size=collocation_setting["batch_size"],
                        source_language_code=source_language_code,
                        target_language_code=target_language_code,
                        prompt_id=collocation_prompt_id
                    ),
                    ignore_cache=False
                )

            if not self.is_running:
                return

            # Step 13: Write import file
            self.after(0, lambda slc=source_language_code: 
                       self._update_progress(13, total_steps, "Writing import file...", slc))
            write_anki_import_file(notes, source_language_code)

            if not self.is_running:
                return

            # Step 14: Save to Anki
            self.after(0, lambda slc=source_language_code: 
                       self._update_progress(14, total_steps, "Saving to Anki...", slc))
            anki_connect_instance.create_notes_batch(anki_deck, notes)

        # Save timestamp
        if latest_candidate_timestamp:
            metadata_manager = MetadataManager()
            metadata = metadata_manager.load_metadata()
            metadata_manager.save_latest_vocab_builder_entry_timestamp(latest_candidate_timestamp, metadata)

        self.after(0, lambda: self._log("Export completed successfully!"))
