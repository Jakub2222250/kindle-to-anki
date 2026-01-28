import customtkinter as ctk
from tkinterdnd2 import DND_FILES
from typing import Callable, Optional, Dict, List
from datetime import datetime
import threading
import subprocess
import sqlite3
import shutil
from pathlib import Path

from kindle_to_anki.logging import LogLevel, UILogger, LoggerRegistry
from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.anki.anki_note import AnkiNote
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
    """Create Notes view - unified page with swappable card content."""

    def __init__(self, master, on_back: Callable):
        super().__init__(master)
        self.on_back = on_back
        self.is_running = False
        self.export_thread: Optional[threading.Thread] = None
        self.notes_by_language: Dict[str, List[AnkiNote]] = {}
        self.latest_candidate_timestamp: Optional[datetime] = None
        self.vocab_db_path: Optional[Path] = None

        self._create_main_layout()
        self._show_collect_lookups_card()

    def _create_main_layout(self):
        """Create the main layout with header, progress bar, card area, and controls."""
        # Header with back button
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        self.back_btn = ctk.CTkButton(
            header,
            text="← Back",
            width=80,
            command=self._on_back_clicked
        )
        self.back_btn.pack(side="left")

        title = ctk.CTkLabel(
            header,
            text="Create Notes",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(side="left", padx=20)

        # Progress section (always visible)
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="Step 1: Collect Lookups",
            font=ctk.CTkFont(size=13)
        )
        self.status_label.pack(anchor="w", pady=(0, 5))

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", pady=(0, 5))
        self.progress_bar.set(0)

        self.step_label = ctk.CTkLabel(
            progress_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        self.step_label.pack(anchor="w")

        # Card container (centered)
        self.card_container = ctk.CTkFrame(self, fg_color="transparent")
        self.card_container.pack(fill="both", expand=True, padx=10)

        # Bottom controls (outside card)
        controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        controls_frame.pack(fill="x", padx=10, pady=(10, 10))

        self.create_notes_btn = ctk.CTkButton(
            controls_frame,
            text="▶ Create Notes",
            width=140,
            state="disabled",
            command=self._start_create_notes
        )
        self.create_notes_btn.pack(side="left", padx=(0, 10))

        self.cancel_btn = ctk.CTkButton(
            controls_frame,
            text="Cancel",
            width=100,
            state="disabled",
            command=self._cancel_export
        )
        self.cancel_btn.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(controls_frame, text="Log Level:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 5))

        self.log_level_var = ctk.StringVar(value="INFO")
        self.log_level_dropdown = ctk.CTkOptionMenu(
            controls_frame,
            variable=self.log_level_var,
            values=[level.name for level in LogLevel],
            width=90,
            command=self._on_log_level_change
        )
        self.log_level_dropdown.pack(side="left")

        # Setup UI logger
        self._ui_logger = UILogger(level=LogLevel.INFO, callback=self._on_log_message)
        LoggerRegistry.set(self._ui_logger)

    def _show_collect_lookups_card(self):
        """Show the Collect Lookups card content."""
        # Clear card container
        for widget in self.card_container.winfo_children():
            widget.destroy()

        # Centered card with modest width
        card = ctk.CTkFrame(self.card_container, corner_radius=12, width=400)
        card.pack(expand=True, pady=10)
        card.pack_propagate(False)
        card.configure(width=420, height=380)

        # Card content
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=15)

        # Auto-locate button
        self.auto_locate_btn = ctk.CTkButton(
            inner,
            text="🔍 Auto-locate from Kindle",
            width=250,
            command=self._auto_locate_vocab_db
        )
        self.auto_locate_btn.pack(pady=(10, 10))

        # Divider with "or"
        ctk.CTkLabel(inner, text="— or —", text_color=("gray50", "gray60")).pack(pady=5)

        # Drop zone frame
        self.drop_zone = ctk.CTkFrame(
            inner,
            height=60,
            corner_radius=8,
            border_width=2,
            border_color=("gray70", "gray30"),
            fg_color=("gray90", "gray17")
        )
        self.drop_zone.pack(fill="x", pady=5)
        self.drop_zone.pack_propagate(False)

        self.drop_label = ctk.CTkLabel(
            self.drop_zone,
            text="📁 Drop vocab.db here or click to browse",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        self.drop_label.pack(expand=True)

        # Make drop zone clickable
        self.drop_zone.bind("<Button-1>", lambda e: self._browse_vocab_db())
        self.drop_label.bind("<Button-1>", lambda e: self._browse_vocab_db())

        # Register drag-and-drop
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind('<<Drop>>', self._on_file_drop)

        # Path entry
        path_frame = ctk.CTkFrame(inner, fg_color="transparent")
        path_frame.pack(fill="x", pady=(10, 5))

        self.path_entry = ctk.CTkEntry(path_frame, placeholder_text="Path to vocab.db...")
        self.path_entry.pack(side="left", fill="x", expand=True)

        self.load_path_btn = ctk.CTkButton(path_frame, text="Load", width=50, command=self._load_from_path)
        self.load_path_btn.pack(side="left", padx=(5, 0))

        # Status indicator
        self.collect_status_label = ctk.CTkLabel(inner, text="", font=ctk.CTkFont(size=11))
        self.collect_status_label.pack(pady=(5, 5))

        # Small output log
        log_header = ctk.CTkLabel(inner, text="Output Log", font=ctk.CTkFont(size=11, weight="bold"))
        log_header.pack(anchor="w", pady=(5, 2))

        self.log_textbox = ctk.CTkTextbox(inner, font=ctk.CTkFont(family="Consolas", size=10), state="disabled", height=80)
        self.log_textbox.pack(fill="both", expand=True)

    def _show_export_card(self):
        """Show the Export/Create Notes card content."""
        # Clear card container
        for widget in self.card_container.winfo_children():
            widget.destroy()

        # Card with same modest width
        card = ctk.CTkFrame(self.card_container, corner_radius=12)
        card.pack(fill="both", expand=True, pady=10, padx=50)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=15)

        # Info about what's being processed
        total_notes = sum(len(notes) for notes in self.notes_by_language.values())
        languages = ", ".join(self.notes_by_language.keys())

        info_label = ctk.CTkLabel(
            inner,
            text=f"Processing {total_notes} lookups ({languages})",
            font=ctk.CTkFont(size=13)
        )
        info_label.pack(pady=(5, 10))

        # Output log (larger in this view)
        log_header = ctk.CTkLabel(inner, text="Output Log", font=ctk.CTkFont(size=12, weight="bold"))
        log_header.pack(anchor="w", pady=(10, 5))

        self.log_textbox = ctk.CTkTextbox(inner, font=ctk.CTkFont(family="Consolas", size=11), state="disabled")
        self.log_textbox.pack(fill="both", expand=True)

    def _start_create_notes(self):
        """Switch to export card and start the export."""
        if not self.notes_by_language:
            self._log("No candidates loaded.")
            return

        self._show_export_card()
        self._start_export()

    def _auto_locate_vocab_db(self):
        """Try to locate vocab.db from connected Kindle via PowerShell."""
        self._set_collect_status("Searching for Kindle...", "info")
        self._log("Searching for connected Kindle device...")
        threading.Thread(target=self._auto_locate_thread, daemon=True).start()

    def _auto_locate_thread(self):
        """Background thread for auto-locating vocab.db."""
        try:
            copy_vocab_script = Path(__file__).parent.parent / "copy_vocab.bat"
            project_root = Path(__file__).parent.parent.parent.parent
            inputs_dir = project_root / "data" / "inputs"
            inputs_dir.mkdir(parents=True, exist_ok=True)

            result = subprocess.run([str(copy_vocab_script)], capture_output=True, text=True)

            if result.returncode == 0:
                src_db = inputs_dir / "vocab_powershell_copy.db"
                dest_db = inputs_dir / "vocab.db"
                if src_db.exists():
                    src_db.replace(dest_db)
                    self.after(0, lambda: self._load_vocab_db(dest_db))
                else:
                    self.after(0, lambda: self._set_collect_status("❌ vocab.db not found after copy", "error"))
                    self.after(0, lambda: self._log("[ERROR] vocab.db not found after PowerShell copy"))
            else:
                self.after(0, lambda: self._set_collect_status("❌ Kindle not found or not connected", "error"))
                if result.stderr:
                    self.after(0, lambda: self._log(f"[ERROR] Auto-locate failed:\n{result.stderr.strip()}"))
                else:
                    self.after(0, lambda: self._log("[ERROR] Auto-locate failed: Kindle not found or not connected"))
        except Exception as e:
            self.after(0, lambda: self._set_collect_status("❌ Auto-locate failed", "error"))
            self.after(0, lambda: self._log(f"[ERROR] Auto-locate exception: {str(e)}"))

    def _browse_vocab_db(self):
        """Open file dialog to browse for vocab.db."""
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            title="Select vocab.db",
            filetypes=[("SQLite Database", "*.db"), ("All files", "*.*")]
        )
        if filepath:
            self._load_vocab_db(Path(filepath))

    def _on_file_drop(self, event):
        """Handle file drop onto the drop zone."""
        filepath = event.data.strip('{}')
        if filepath:
            self._load_vocab_db(Path(filepath))

    def _load_from_path(self):
        """Load vocab.db from the path entry."""
        path = self.path_entry.get().strip()
        if path:
            self._load_vocab_db(Path(path))
        else:
            self._set_collect_status("❌ Please enter a path", "error")
            self._log("[ERROR] No path entered")

    def _load_vocab_db(self, db_path: Path):
        """Load and validate vocab.db, then collect candidates."""
        if not db_path.exists():
            self._set_collect_status(f"❌ File not found", "error")
            self._log(f"[ERROR] File not found: {db_path}")
            return

        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='LOOKUPS'")
            if not cur.fetchone():
                conn.close()
                self._set_collect_status("❌ Invalid vocab.db", "error")
                self._log(f"[ERROR] Invalid vocab.db: missing LOOKUPS table")
                return
            conn.close()
        except Exception as e:
            self._set_collect_status(f"❌ Error reading database", "error")
            self._log(f"[ERROR] Error reading database: {str(e)}")
            return

        self.vocab_db_path = db_path
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, str(db_path))
        self._log(f"Loading vocab.db from: {db_path}")

        project_root = Path(__file__).parent.parent.parent.parent
        inputs_dir = project_root / "data" / "inputs"
        target_path = inputs_dir / "vocab.db"

        if db_path.resolve() != target_path.resolve():
            inputs_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_path, target_path)

        self._set_collect_status("Loading candidates...", "info")
        threading.Thread(target=self._collect_candidates_thread, daemon=True).start()

    def _collect_candidates_thread(self):
        """Background thread for collecting candidates."""
        try:
            bootstrap_all()
            candidate_provider = CollectCandidatesProvider(
                runtimes=RuntimeRegistry.find_by_task_as_dict("collect_candidates")
            )
            notes_by_language, latest_timestamp = candidate_provider.collect_candidates(runtime_choice="kindle")

            self.notes_by_language = notes_by_language or {}
            self.latest_candidate_timestamp = latest_timestamp

            total_notes = sum(len(notes) for notes in self.notes_by_language.values())
            languages = ", ".join(self.notes_by_language.keys())

            if total_notes > 0:
                self.after(0, lambda: self._on_candidates_loaded(total_notes, languages))
            else:
                self.after(0, lambda: self._set_collect_status("⚠️ No new candidates found", "warning"))
                self.after(0, lambda: self._log("[WARNING] No new candidates found in vocab.db"))
        except Exception as e:
            self.after(0, lambda: self._set_collect_status(f"❌ Error loading candidates", "error"))
            self.after(0, lambda: self._log(f"[ERROR] Error loading candidates: {str(e)}"))

    def _on_candidates_loaded(self, total_notes: int, languages: str):
        """Called when candidates are successfully loaded."""
        self._set_collect_status(f"✅ Loaded {total_notes} lookups ({languages})", "success")
        self._log(f"Successfully loaded {total_notes} lookups for languages: {languages}")
        self.create_notes_btn.configure(state="normal")
        self.progress_bar.set(0.1)
        self.step_label.configure(text=f"{total_notes} lookups ready")

    def _set_collect_status(self, message: str, status_type: str = "info"):
        """Update the collect status label with color."""
        colors = {
            "info": ("gray50", "gray60"),
            "success": ("green", "green"),
            "error": ("red", "red"),
            "warning": ("orange", "orange")
        }
        self.collect_status_label.configure(text=message, text_color=colors.get(status_type, colors["info"]))

    def _on_back_clicked(self):
        if self.is_running:
            return
        self.on_back()

    def _on_log_level_change(self, value: str):
        """Update the UI logger's level when dropdown changes."""
        self._ui_logger.level = LogLevel[value]

    def _on_log_message(self, level: LogLevel, message: str):
        """Callback for UILogger - append to log textbox from any thread."""
        self.after(0, lambda: self._log(f"[{level.name}] {message}"))

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
        if not self.notes_by_language:
            self._log("No candidates loaded.")
            return

        self.is_running = True
        self.back_btn.configure(state="disabled")
        self.create_notes_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")

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
        """Run the export pipeline."""
        try:
            self._export_pipeline()
        except Exception as e:
            self.after(0, lambda: self._log(f"Error: {str(e)}"))
        finally:
            self.after(0, self._export_finished)

    def _export_finished(self):
        """Called when export completes or fails."""
        self.is_running = False
        self.back_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.progress_bar.set(1)
        self.status_label.configure(text="Export completed")
        self.step_label.configure(text="")

    def _export_pipeline(self):
        """Main export pipeline - uses pre-loaded candidates."""
        total_steps = 11  # Reduced since candidates already loaded

        # Step 1: Bootstrap (if not done)
        self.after(0, lambda: self._update_progress(1, total_steps, "Initializing...", "Setting up runtimes"))
        bootstrap_all()

        if not self.is_running:
            return

        # Step 2: Setup providers
        self.after(0, lambda: self._update_progress(2, total_steps, "Setting up providers...", ""))
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

        # Use pre-loaded candidates
        notes_by_language = self.notes_by_language

        if not notes_by_language or len(notes_by_language) == 0:
            self.after(0, lambda: self._log("No candidate notes to process."))
            return

        # Step 4: Connect to Anki
        self.after(0, lambda: self._update_progress(4, total_steps, "Connecting to Anki...", ""))
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

            # Step 5: LUI
            self.after(0, lambda: self._update_progress(5, total_steps, "Lexical Unit Identification...", ""))
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

            # Step 6: WSD
            self.after(0, lambda: self._update_progress(6, total_steps, "Word Sense Disambiguation...", ""))
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

            # Step 7: Hint generation (optional)
            hint_setting = anki_deck.get_task_setting("hint")
            if hint_setting.get("enabled", True):
                self.after(0, lambda: self._update_progress(7, total_steps, "Generating hints...", ""))
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

            # Step 8: Cloze scoring (optional)
            cloze_setting = anki_deck.get_task_setting("cloze_scoring")
            if cloze_setting.get("enabled", True):
                self.after(0, lambda: self._update_progress(8, total_steps, "Scoring cloze suitability...", ""))
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

            # Step 9: Usage level (optional)
            usage_level_setting = anki_deck.get_task_setting("usage_level")
            if usage_level_setting.get("enabled", True):
                self.after(0, lambda: self._update_progress(9, total_steps, "Estimating usage levels...", ""))
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

            # Step 10: Translation
            self.after(0, lambda: self._update_progress(10, total_steps, "Translating...", ""))
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

            # Step 11: Collocations (optional)
            collocation_setting = anki_deck.get_task_setting("collocation")
            if collocation_setting.get("enabled", True):
                self.after(0, lambda: self._update_progress(11, total_steps, "Generating collocations...", ""))
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

            # Write import file
            self.after(0, lambda slc=source_language_code: 
                       self._update_progress(total_steps - 1, total_steps, "Writing import file...", slc))
            write_anki_import_file(notes, source_language_code)

            if not self.is_running:
                return

            # Save to Anki
            self.after(0, lambda slc=source_language_code: 
                       self._update_progress(total_steps, total_steps, "Saving to Anki...", slc))
            anki_connect_instance.create_notes_batch(anki_deck, notes)

        # Save timestamp
        if self.latest_candidate_timestamp:
            metadata_manager = MetadataManager()
            metadata = metadata_manager.load_metadata()
            metadata_manager.save_latest_vocab_builder_entry_timestamp(self.latest_candidate_timestamp, metadata)

        self.after(0, lambda: self._log("Export completed successfully!"))
