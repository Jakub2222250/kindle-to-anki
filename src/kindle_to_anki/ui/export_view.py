import customtkinter as ctk
from tkinterdnd2 import DND_FILES
from typing import Callable, Optional, Dict, List
from datetime import datetime
from pathlib import Path
import threading
import sqlite3
import shutil

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
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.core.pricing.token_pricing_policy import TokenPricingPolicy
from kindle_to_anki.util.kindle_device import find_and_copy_vocab_db
from kindle_to_anki.util.paths import get_inputs_dir
from kindle_to_anki.util.cancellation import CancellationToken, CancelledException


class ExportView(ctk.CTkFrame):
    """Create Notes view - unified page with swappable card content."""

    def __init__(self, master, on_back: Callable):
        super().__init__(master)
        self.on_back = on_back
        self.is_running = False
        self.export_thread: Optional[threading.Thread] = None
        self._cancellation_token: Optional[CancellationToken] = None
        self.notes_by_language: Dict[str, List[AnkiNote]] = {}
        self.pruned_notes_by_language: Dict[str, List[AnkiNote]] = {}  # After UID pruning
        self.latest_candidate_timestamp: Optional[datetime] = None
        self.vocab_db_path: Optional[Path] = None
        self.selected_language: Optional[str] = None
        self.note_limit: int = 30
        self.limit_enabled: bool = True
        self.timestamp_filter_enabled: bool = True
        self.timestamp_cutoff: Optional[datetime] = None  # User-selected cutoff

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

        # Outer card matching export card width
        card = ctk.CTkFrame(self.card_container, corner_radius=12)
        card.pack(fill="both", expand=True, pady=10, padx=50)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20, pady=15)

        # Centered content frame for source/provider (narrower)
        content_frame = ctk.CTkFrame(inner, fg_color="transparent", width=380)
        content_frame.pack(pady=(0, 10))
        content_frame.pack_propagate(False)
        content_frame.configure(height=280)

        # Source subtitle
        source_label = ctk.CTkLabel(
            content_frame,
            text="Source",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        source_label.pack(anchor="w", pady=(0, 8))

        # Source selector (segmented button for future extensibility)
        self.source_var = ctk.StringVar(value="kindle")
        self.source_selector = ctk.CTkSegmentedButton(
            content_frame,
            values=["Kindle", "Kobo", "Manual Import"],
            variable=self.source_var,
            command=self._on_source_changed
        )
        self.source_selector.pack(fill="x", pady=(0, 10))
        self.source_selector.set("Kindle")

        # Provider content frame (swappable based on source)
        self.provider_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        self.provider_frame.pack(fill="both", expand=True)

        self._show_kindle_provider()

        # Status indicator (shared across providers)
        self.collect_status_label = ctk.CTkLabel(content_frame, text="", font=ctk.CTkFont(size=11))
        self.collect_status_label.pack(pady=(5, 0))

        # Output log (full width)
        log_header = ctk.CTkLabel(inner, text="Output Log", font=ctk.CTkFont(size=11, weight="bold"))
        log_header.pack(anchor="w", pady=(5, 2))

        self.log_textbox = ctk.CTkTextbox(inner, font=ctk.CTkFont(family="Consolas", size=10), state="disabled", height=100)
        self.log_textbox.pack(fill="both", expand=True)

    def _on_source_changed(self, value: str):
        """Handle source selection change."""
        for widget in self.provider_frame.winfo_children():
            widget.destroy()

        if value == "Kindle":
            self._show_kindle_provider()
        elif value == "Kobo":
            self._show_kobo_provider()
        elif value == "Manual Import":
            self._show_manual_import_provider()

    def _show_kindle_provider(self):
        """Show Kindle-specific provider content."""
        # Auto-locate button
        self.auto_locate_btn = ctk.CTkButton(
            self.provider_frame,
            text="🔍 Auto-locate from Kindle",
            width=250,
            command=self._auto_locate_vocab_db
        )
        self.auto_locate_btn.pack(pady=(5, 8))

        # Divider with "or"
        ctk.CTkLabel(self.provider_frame, text="— or —", text_color=("gray50", "gray60")).pack(pady=3)

        # Drop zone frame
        self.drop_zone = ctk.CTkFrame(
            self.provider_frame,
            height=55,
            corner_radius=8,
            border_width=2,
            border_color=("gray70", "gray30"),
            fg_color=("gray90", "gray17")
        )
        self.drop_zone.pack(fill="x", pady=3)
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
        path_frame = ctk.CTkFrame(self.provider_frame, fg_color="transparent")
        path_frame.pack(fill="x", pady=(8, 0))

        self.path_entry = ctk.CTkEntry(path_frame, placeholder_text="Path to vocab.db...")
        self.path_entry.pack(side="left", fill="x", expand=True)

        # Pre-populate with existing vocab.db if available
        default_vocab_path = get_inputs_dir() / "vocab.db"
        if default_vocab_path.exists():
            self.path_entry.insert(0, str(default_vocab_path))

        self.load_path_btn = ctk.CTkButton(path_frame, text="Load", width=50, command=self._load_from_path)
        self.load_path_btn.pack(side="left", padx=(5, 0))

    def _show_kobo_provider(self):
        """Show Kobo provider placeholder."""
        todo_label = ctk.CTkLabel(
            self.provider_frame,
            text="🚧 Kobo Support",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        todo_label.pack(pady=(20, 10))

        desc_label = ctk.CTkLabel(
            self.provider_frame,
            text="Kobo e-reader integration is planned for a future release.",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        desc_label.pack(pady=(0, 10))

    def _show_manual_import_provider(self):
        """Show Manual Import provider placeholder."""
        todo_label = ctk.CTkLabel(
            self.provider_frame,
            text="🚧 Manual Import",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        todo_label.pack(pady=(20, 10))

        desc_label = ctk.CTkLabel(
            self.provider_frame,
            text="Manual word list import is planned for a future release.",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        desc_label.pack(pady=(0, 10))

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
        notes_dict = getattr(self, 'notes_to_export', self.notes_by_language)
        total_notes = sum(len(notes) for notes in notes_dict.values())
        languages = ", ".join(notes_dict.keys())

        info_label = ctk.CTkLabel(
            inner,
            text=f"Processing {total_notes} notes ({languages})",
            font=ctk.CTkFont(size=13)
        )
        info_label.pack(pady=(5, 10))

        # Output log (larger in this view)
        log_header = ctk.CTkLabel(inner, text="Output Log", font=ctk.CTkFont(size=12, weight="bold"))
        log_header.pack(anchor="w", pady=(10, 5))

        self.log_textbox = ctk.CTkTextbox(inner, font=ctk.CTkFont(family="Consolas", size=11), state="disabled")
        self.log_textbox.pack(fill="both", expand=True)

    def _show_preview_card(self):
        """Show the preview card after collecting lookups - allows deck selection and settings review."""
        for widget in self.card_container.winfo_children():
            widget.destroy()

        self.status_label.configure(text="Step 2: Preview & Configure")
        self.progress_bar.set(0.15)

        # Card with fixed height content area
        self.preview_card = ctk.CTkFrame(self.card_container, corner_radius=12)
        self.preview_card.pack(fill="both", expand=True, pady=10, padx=50)

        # Show loading state first
        self.preview_loading_frame = ctk.CTkFrame(self.preview_card, fg_color="transparent")
        self.preview_loading_frame.pack(fill="both", expand=True, padx=20, pady=40)

        self.loading_status_label = ctk.CTkLabel(
            self.preview_loading_frame,
            text="🔗 Connecting to Anki...",
            font=ctk.CTkFont(size=14)
        )
        self.loading_status_label.pack(pady=(20, 10))

        self.loading_detail_label = ctk.CTkLabel(
            self.preview_loading_frame,
            text="Validating AnkiConnect and checking existing cards",
            font=ctk.CTkFont(size=11),
            text_color=("gray50", "gray60")
        )
        self.loading_detail_label.pack(pady=(0, 20))

        # Progress indicator
        self.loading_progress = ctk.CTkProgressBar(self.preview_loading_frame, width=300, mode="indeterminate")
        self.loading_progress.pack(pady=10)
        self.loading_progress.start()

        # Perform Anki connection and pruning in background
        threading.Thread(target=self._prune_and_update_preview, daemon=True).start()

    def _show_preview_content(self):
        """Show the full preview content after Anki connection is validated."""
        # Remove loading frame
        if hasattr(self, 'preview_loading_frame'):
            self.preview_loading_frame.destroy()

        # Scrollable inner content
        scroll_inner = ctk.CTkScrollableFrame(self.preview_card, fg_color="transparent")
        scroll_inner.pack(fill="both", expand=True, padx=20, pady=15)

        # Deck selector section
        deck_frame = ctk.CTkFrame(scroll_inner, fg_color="transparent")
        deck_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(deck_frame, text="Select Deck", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w")

        # Get available languages with notes
        available_languages = list(self.notes_by_language.keys())
        self.selected_language = available_languages[0] if available_languages else None

        self.deck_var = ctk.StringVar(value=self.selected_language or "")
        self.deck_selector = ctk.CTkOptionMenu(
            deck_frame,
            values=available_languages,
            variable=self.deck_var,
            width=180,
            command=self._on_deck_selected
        )
        self.deck_selector.pack(anchor="w", pady=(5, 0))

        # Options section
        ctk.CTkLabel(scroll_inner, text="Options", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(10, 5))

        options_frame = ctk.CTkFrame(scroll_inner, corner_radius=8)
        options_frame.pack(fill="x", pady=(0, 10))

        options_inner = ctk.CTkFrame(options_frame, fg_color="transparent")
        options_inner.pack(fill="x", padx=10, pady=10)

        # Note Limit option
        limit_row = ctk.CTkFrame(options_inner, fg_color="transparent")
        limit_row.pack(fill="x", pady=(0, 8))

        self.limit_enabled_var = ctk.BooleanVar(value=self.limit_enabled)
        self.limit_checkbox = ctk.CTkCheckBox(
            limit_row,
            text="Limit to:",
            variable=self.limit_enabled_var,
            command=self._on_limit_checkbox_changed,
            font=ctk.CTkFont(size=11)
        )
        self.limit_checkbox.pack(side="left")

        self.limit_var = ctk.StringVar(value=str(self.note_limit))
        self.limit_var.trace_add("write", lambda *_: self._on_limit_changed())
        self.limit_entry = ctk.CTkEntry(limit_row, width=60, textvariable=self.limit_var)
        self.limit_entry.pack(side="left", padx=(10, 5))

        ctk.CTkLabel(limit_row, text="(useful with rate-limited models)", font=ctk.CTkFont(size=10), text_color=("gray50", "gray60")).pack(side="left", padx=(5, 0))

        # Timestamp filter option
        timestamp_row = ctk.CTkFrame(options_inner, fg_color="transparent")
        timestamp_row.pack(fill="x", pady=(0, 0))

        self.timestamp_filter_var = ctk.BooleanVar(value=self.timestamp_filter_enabled)
        self.timestamp_checkbox = ctk.CTkCheckBox(
            timestamp_row,
            text="Only lookups since:",
            variable=self.timestamp_filter_var,
            command=self._on_timestamp_checkbox_changed,
            font=ctk.CTkFont(size=11)
        )
        self.timestamp_checkbox.pack(side="left")

        # Date/time entry
        self.timestamp_date_var = ctk.StringVar(value="")
        self.timestamp_date_entry = ctk.CTkEntry(timestamp_row, width=100, textvariable=self.timestamp_date_var, placeholder_text="YYYY-MM-DD")
        self.timestamp_date_entry.pack(side="left", padx=(10, 5))

        self.timestamp_time_var = ctk.StringVar(value="")
        self.timestamp_time_entry = ctk.CTkEntry(timestamp_row, width=60, textvariable=self.timestamp_time_var, placeholder_text="HH:MM")
        self.timestamp_time_entry.pack(side="left", padx=(0, 5))

        # Bind entry changes to update filtering
        self.timestamp_date_var.trace_add("write", lambda *_: self._on_timestamp_entry_changed())
        self.timestamp_time_var.trace_add("write", lambda *_: self._on_timestamp_entry_changed())

        # Summary section
        self.preview_summary_frame = ctk.CTkFrame(scroll_inner, fg_color="transparent")
        self.preview_summary_frame.pack(fill="x", pady=(5, 10))

        # Options table section
        ctk.CTkLabel(scroll_inner, text="Task Settings", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=(5, 5))

        # Frame for options table (not scrollable, table is small)
        self.options_table_frame = ctk.CTkFrame(scroll_inner, corner_radius=8)
        self.options_table_frame.pack(fill="x", pady=(0, 10))

        # Enable create notes button
        self.create_notes_btn.configure(state="normal")

        # Initialize options and timestamp for selected deck, then update display
        self._load_preview_options_for_deck()
        self._init_timestamp_for_deck()
        self._update_preview_display()

    def _show_preview_error(self, error_message: str):
        """Show an error state in the preview card."""
        # Stop and remove loading indicator
        if hasattr(self, 'loading_progress'):
            self.loading_progress.stop()

        if hasattr(self, 'loading_status_label'):
            self.loading_status_label.configure(text="❌ Connection Failed", text_color=("red", "red"))

        if hasattr(self, 'loading_detail_label'):
            self.loading_detail_label.configure(
                text=error_message,
                text_color=("red", "red")
            )

        if hasattr(self, 'loading_progress'):
            self.loading_progress.pack_forget()

        # Add retry button
        retry_btn = ctk.CTkButton(
            self.preview_loading_frame,
            text="Retry Connection",
            command=lambda: self._retry_preview()
        )
        retry_btn.pack(pady=20)

    def _retry_preview(self):
        """Retry the preview connection."""
        self._show_preview_card()

    def _prune_and_update_preview(self):
        """Background thread to prune notes and update preview."""
        try:
            self.after(0, lambda: self._update_loading_status("🔗 Connecting to Anki...", "Validating AnkiConnect connection"))

            bootstrap_all()
            config_manager = ConfigManager()
            anki_decks_by_source_language = config_manager.get_anki_decks_by_source_language()

            # Test Anki connection first
            try:
                anki_connect = AnkiConnect()
                # Constructor already validates connection via is_reachable()
            except Exception as e:
                error_msg = f"Cannot connect to Anki. Please ensure Anki is running\nwith AnkiConnect add-on installed.\n\nError: {str(e)}"
                self.after(0, lambda msg=error_msg: self._show_preview_error(msg))
                return

            self.after(0, lambda: self._update_loading_status("📚 Checking existing cards...", "Checking for duplicates"))

            self.pruned_notes_by_language = {}

            for lang_code, notes in self.notes_by_language.items():
                anki_deck = anki_decks_by_source_language.get(lang_code)
                if not anki_deck:
                    self.pruned_notes_by_language[lang_code] = notes
                    continue

                language_pair_code = anki_deck.get_language_pair_code()

                self.after(0, lambda lc=lang_code: self._update_loading_status(
                    f"📚 Checking existing cards...",
                    f"Processing {lc} deck"
                ))

                # Get existing notes and prune by UID
                existing_notes = anki_connect.get_notes(anki_deck)
                pruned = prune_existing_notes_by_UID(notes.copy(), existing_notes)

                # Also prune notes identified as redundant
                pruned = prune_notes_identified_as_redundant(pruned, cache_suffix=language_pair_code)

                self.pruned_notes_by_language[lang_code] = pruned

            # Show the full preview content
            self.after(0, self._show_preview_content)

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.after(0, lambda msg=error_msg: self._show_preview_error(msg))

    def _update_loading_status(self, status: str, detail: str):
        """Update the loading status labels."""
        if hasattr(self, 'loading_status_label'):
            self.loading_status_label.configure(text=status)
        if hasattr(self, 'loading_detail_label'):
            self.loading_detail_label.configure(text=detail)

    def _on_deck_selected(self, value: str):
        """Handle deck selection change."""
        self.selected_language = value
        self._load_preview_options_for_deck()
        self._init_timestamp_for_deck()
        self._update_preview_display()

    def _load_preview_options_for_deck(self):
        """Load saved preview options for the selected deck."""
        if not self.selected_language:
            return

        config_manager = ConfigManager()
        anki_decks = config_manager.get_anki_decks_by_source_language()
        anki_deck = anki_decks.get(self.selected_language)

        if not anki_deck:
            return

        opts = anki_deck.preview_options
        self.limit_enabled = opts.get("note_limit_enabled", True)
        self.note_limit = opts.get("note_limit", 30)

        # Update UI controls
        if hasattr(self, 'limit_enabled_var'):
            self.limit_enabled_var.set(self.limit_enabled)
        if hasattr(self, 'limit_var'):
            self.limit_var.set(str(self.note_limit))

    def _save_preview_options_for_deck(self):
        """Save preview options for the selected deck to config."""
        if not self.selected_language:
            return

        try:
            limit = int(self.limit_var.get()) if hasattr(self, 'limit_var') else self.note_limit
        except ValueError:
            limit = self.note_limit

        preview_options = {
            "note_limit_enabled": self.limit_enabled,
            "note_limit": limit
        }

        config_manager = ConfigManager()
        config_manager.save_preview_options(self.selected_language, preview_options)

    def _on_limit_changed(self):
        """Handle note limit change - refresh cost estimates and save."""
        if hasattr(self, 'options_table_frame'):
            self._update_preview_display()
            self._save_preview_options_for_deck()

    def _on_limit_checkbox_changed(self):
        """Handle limit checkbox toggle."""
        self.limit_enabled = self.limit_enabled_var.get()
        self._update_preview_display()
        self._save_preview_options_for_deck()

    def _on_timestamp_checkbox_changed(self):
        """Handle timestamp filter checkbox toggle."""
        self.timestamp_filter_enabled = self.timestamp_filter_var.get()
        state = "normal" if self.timestamp_filter_enabled else "disabled"
        if hasattr(self, 'timestamp_date_entry'):
            self.timestamp_date_entry.configure(state=state)
        if hasattr(self, 'timestamp_time_entry'):
            self.timestamp_time_entry.configure(state=state)
        self._update_preview_display()

    def _on_timestamp_entry_changed(self):
        """Handle timestamp entry changes."""
        self._parse_timestamp_cutoff()
        self._update_preview_display()

    def _init_timestamp_for_deck(self):
        """Initialize timestamp cutoff from metadata for the selected deck."""
        if not self.selected_language:
            return

        config_manager = ConfigManager()
        anki_decks_by_source_language = config_manager.get_anki_decks_by_source_language()
        anki_deck = anki_decks_by_source_language.get(self.selected_language)

        if not anki_deck:
            self.timestamp_cutoff = None
            return

        metadata_manager = MetadataManager()
        last_timestamp = metadata_manager.get_last_vocab_timestamp(
            source_language_code=self.selected_language,
            target_language_code=anki_deck.target_language_code
        )

        self.timestamp_cutoff = last_timestamp

        # Update entry fields
        if hasattr(self, 'timestamp_date_var') and hasattr(self, 'timestamp_time_var'):
            if last_timestamp:
                self.timestamp_date_var.set(last_timestamp.strftime("%Y-%m-%d"))
                self.timestamp_time_var.set(last_timestamp.strftime("%H:%M"))
            else:
                self.timestamp_date_var.set("")
                self.timestamp_time_var.set("")

    def _parse_timestamp_cutoff(self):
        """Parse the timestamp cutoff from entry fields."""
        if not hasattr(self, 'timestamp_date_var') or not hasattr(self, 'timestamp_time_var'):
            return

        date_str = self.timestamp_date_var.get().strip()
        time_str = self.timestamp_time_var.get().strip() or "00:00"

        if not date_str:
            self.timestamp_cutoff = None
            return

        try:
            self.timestamp_cutoff = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            pass  # Keep previous value if parse fails

    def _get_filtered_notes(self) -> List[AnkiNote]:
        """Get notes after applying timestamp filter and limit."""
        if not self.selected_language:
            return []

        pruned_notes = self.pruned_notes_by_language.get(self.selected_language, [])

        # Apply timestamp filter if enabled
        if self.timestamp_filter_enabled and self.timestamp_cutoff:
            pruned_notes = [
                n for n in pruned_notes
                if n.source_timestamp and n.source_timestamp > self.timestamp_cutoff
            ]

        # Apply limit if enabled
        if self.limit_enabled:
            try:
                limit = int(self.limit_var.get()) if hasattr(self, 'limit_var') else self.note_limit
                if limit > 0:
                    pruned_notes = pruned_notes[:limit]
            except ValueError:
                pass

        return pruned_notes

    def _update_preview_display(self):
        """Update the preview summary and options table for the selected deck."""
        if not self.selected_language:
            return

        lang_code = self.selected_language
        original_count = len(self.notes_by_language.get(lang_code, []))
        pruned_notes = self.pruned_notes_by_language.get(lang_code, [])
        after_uid_prune = len(pruned_notes)

        # Get final filtered notes
        filtered_notes = self._get_filtered_notes()
        cards_to_create = len(filtered_notes)

        # Update summary
        for widget in self.preview_summary_frame.winfo_children():
            widget.destroy()

        summary_text = f"Language: {lang_code} | Lookups: {original_count} | After dedup: {after_uid_prune} | Cards to be Created: {cards_to_create}"
        ctk.CTkLabel(self.preview_summary_frame, text=summary_text, font=ctk.CTkFont(size=11)).pack(anchor="w")

        # Update step label
        self.step_label.configure(text=f"{cards_to_create} notes will be processed")

        # Update options table
        self._populate_options_table()

    def _populate_options_table(self):
        """Populate the options table with task settings for the selected deck."""
        # Clear existing
        for widget in self.options_table_frame.winfo_children():
            widget.destroy()

        if not self.selected_language:
            return

        # Get deck config
        config_manager = ConfigManager()
        anki_decks_by_source_language = config_manager.get_anki_decks_by_source_language()
        anki_deck = anki_decks_by_source_language.get(self.selected_language)

        if not anki_deck:
            ctk.CTkLabel(self.options_table_frame, text="No deck configured for this language").pack(padx=10, pady=10)
            return

        # Get note count for cost estimation using filtered notes
        note_count = len(self._get_filtered_notes())

        target_language_code = anki_deck.target_language_code

        # Table container with padding
        table_inner = ctk.CTkFrame(self.options_table_frame, fg_color="transparent")
        table_inner.pack(fill="x", padx=10, pady=10)

        # Configure grid columns
        table_inner.grid_columnconfigure(0, weight=1, minsize=90)
        table_inner.grid_columnconfigure(1, weight=2, minsize=200)
        table_inner.grid_columnconfigure(2, weight=1, minsize=130)
        table_inner.grid_columnconfigure(3, weight=0, minsize=70)

        # Table header
        headers = ["Task", "Runtime", "Model", "Est. Cost"]
        for col, h in enumerate(headers):
            ctk.CTkLabel(table_inner, text=h, font=ctk.CTkFont(size=11, weight="bold")).grid(
                row=0, column=col, sticky="w", padx=(5, 10), pady=(0, 5)
            )

        # Task rows
        tasks = ["lui", "wsd", "hint", "cloze_scoring", "usage_level", "translation", "collocation"]
        total_cost = 0.0
        row_idx = 1

        for task in tasks:
            setting = anki_deck.get_task_setting(task)
            if not setting:
                continue

            # Check if task is enabled (some are optional)
            if task in ["hint", "cloze_scoring", "usage_level", "collocation"]:
                if not setting.get("enabled", True):
                    continue

            runtime_id = setting.get("runtime", "")
            model_id = setting.get("model_id", "")

            # Calculate estimated cost
            cost_str = "$0.00"
            if model_id:
                model = ModelRegistry.get(model_id) if model_id else None
                if model:
                    runtime = RuntimeRegistry.get(runtime_id)
                    if runtime:
                        runtime_config = RuntimeConfig(
                            model_id=model_id,
                            batch_size=setting.get("batch_size", 30),
                            source_language_code=self.selected_language,
                            target_language_code=target_language_code
                        )
                        usage = runtime.estimate_usage(note_count, runtime_config)
                        pricing = TokenPricingPolicy(
                            input_cost_per_1m=model.input_token_cost_per_1m,
                            output_cost_per_1m=model.output_token_cost_per_1m,
                        )
                        cost = pricing.estimate_cost(usage).usd
                        total_cost += cost
                        cost_str = f"${cost:.4f}"

            # Alternating row background
            row_bg = ("gray85", "gray25") if row_idx % 2 == 0 else None

            # Create a frame for the row to hold background color
            row_frame = ctk.CTkFrame(table_inner, fg_color=row_bg if row_bg else "transparent", corner_radius=4)
            row_frame.grid(row=row_idx, column=0, columnspan=4, sticky="ew", pady=1)
            row_frame.grid_columnconfigure(0, weight=1, minsize=90)
            row_frame.grid_columnconfigure(1, weight=2, minsize=200)
            row_frame.grid_columnconfigure(2, weight=1, minsize=130)
            row_frame.grid_columnconfigure(3, weight=0, minsize=70)

            ctk.CTkLabel(row_frame, text=task, font=ctk.CTkFont(size=11), fg_color="transparent").grid(
                row=0, column=0, sticky="w", padx=(5, 10), pady=3
            )
            ctk.CTkLabel(row_frame, text=runtime_id or "n/a", font=ctk.CTkFont(size=11), fg_color="transparent").grid(
                row=0, column=1, sticky="w", padx=(5, 10), pady=3
            )
            ctk.CTkLabel(row_frame, text=model_id or "n/a", font=ctk.CTkFont(size=11), fg_color="transparent").grid(
                row=0, column=2, sticky="w", padx=(5, 10), pady=3
            )
            ctk.CTkLabel(row_frame, text=cost_str, font=ctk.CTkFont(size=11), fg_color="transparent").grid(
                row=0, column=3, sticky="w", padx=(5, 10), pady=3
            )
            row_idx += 1

        # Separator line
        separator = ctk.CTkFrame(table_inner, height=1, fg_color=("gray70", "gray40"))
        separator.grid(row=row_idx, column=0, columnspan=4, sticky="ew", pady=(5, 5))
        row_idx += 1

        # Total row
        ctk.CTkLabel(table_inner, text="TOTAL", font=ctk.CTkFont(size=11, weight="bold")).grid(
            row=row_idx, column=0, sticky="w", padx=(5, 10), pady=2
        )
        ctk.CTkLabel(table_inner, text="", font=ctk.CTkFont(size=11)).grid(
            row=row_idx, column=1, sticky="w", padx=(5, 10), pady=2
        )
        ctk.CTkLabel(table_inner, text=f"({note_count} notes)", font=ctk.CTkFont(size=11)).grid(
            row=row_idx, column=2, sticky="w", padx=(5, 10), pady=2
        )
        ctk.CTkLabel(table_inner, text=f"${total_cost:.4f}", font=ctk.CTkFont(size=11, weight="bold")).grid(
            row=row_idx, column=3, sticky="w", padx=(5, 10), pady=2
        )

    def _start_create_notes(self):
        """Switch to export card and start the export."""
        if not self.pruned_notes_by_language and not self.notes_by_language:
            self._log("No candidates loaded.")
            return

        if not self.selected_language:
            self._log("No deck selected.")
            return

        # Use filtered notes from preview (applies timestamp filter and limit)
        filtered_notes = self._get_filtered_notes()

        self.notes_to_export = {self.selected_language: filtered_notes}

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
            success, message = find_and_copy_vocab_db()

            if success:
                inputs_dir = get_inputs_dir()
                # Check for both possible output filenames
                for filename in ["vocab_powershell_copy.db", "vocab_copy.db"]:
                    src_db = inputs_dir / filename
                    if src_db.exists():
                        dest_db = inputs_dir / "vocab.db"
                        src_db.replace(dest_db)
                        self.after(0, lambda: self._load_vocab_db(dest_db))
                        return
                self.after(0, lambda: self._set_collect_status("❌ vocab.db not found after copy", "error"))
                self.after(0, lambda: self._log("[ERROR] vocab.db not found after copy"))
            else:
                self.after(0, lambda m=message: self._set_collect_status(f"❌ {m}", "error"))
                self.after(0, lambda m=message: self._log(f"[ERROR] {m}"))
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

        inputs_dir = get_inputs_dir()
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
        self.progress_bar.set(0.1)
        self.step_label.configure(text=f"{total_notes} lookups ready")
        # Proceed to preview step
        self._show_preview_card()

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
        try:
            if not self.winfo_exists():
                return
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
        except Exception:
            pass  # Widget destroyed

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
        self._cancellation_token = CancellationToken(lambda: not self.is_running)
        self.back_btn.configure(state="disabled")
        self.create_notes_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.log_level_dropdown.configure(state="disabled")

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
        except CancelledException:
            self.after(0, lambda: self._log("Export cancelled."))
        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda msg=error_msg: self._log(f"Error: {msg}"))
        finally:
            self.after(0, self._export_finished)

    def _export_finished(self):
        """Called when export completes or fails."""
        self.is_running = False
        self.back_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.log_level_dropdown.configure(state="normal")
        # Re-enable Create Notes if there are still candidates (allows retry on failure)
        if self.notes_by_language:
            self.create_notes_btn.configure(state="normal")
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

        # Use pre-pruned and limited notes from preview step
        notes_by_language = getattr(self, 'notes_to_export', self.notes_by_language)

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

            # Get existing notes for later pruning after WSD (UID pruning already done in preview)
            existing_notes = anki_connect_instance.get_notes(anki_deck)

            if len(notes) == 0:
                self.after(0, lambda slc=source_language_code: 
                           self._log(f"No notes to process for {slc}"))
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
                ignore_cache=False,
                cancellation_token=self._cancellation_token
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
                ignore_cache=False,
                cancellation_token=self._cancellation_token
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
                    ignore_cache=False,
                    cancellation_token=self._cancellation_token
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
                    ignore_cache=False,
                    cancellation_token=self._cancellation_token
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
                    ignore_cache=False,
                    cancellation_token=self._cancellation_token
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
                use_test_cache=False,
                cancellation_token=self._cancellation_token
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
                    ignore_cache=False,
                    cancellation_token=self._cancellation_token
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

            # Save per-deck timestamp for future incremental imports
            if self.latest_candidate_timestamp:
                metadata_manager = MetadataManager()
                metadata = metadata_manager.load_metadata()
                metadata_manager.save_latest_vocab_builder_entry_timestamp(
                    self.latest_candidate_timestamp, 
                    metadata,
                    source_language_code=source_language_code,
                    target_language_code=target_language_code
                )

        self.after(0, lambda: self._log("Export completed successfully!"))
