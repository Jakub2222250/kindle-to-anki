import customtkinter as ctk
from typing import Callable
import json
import threading

from kindle_to_anki.anki.constants import NOTE_TYPE_NAME
from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.configuration.config_manager import ConfigManager
from kindle_to_anki.ui.task_config import TASK_ORDER, TASK_METADATA, get_runtimes_for_task, get_models_for_runtime, get_prompts_for_task, get_default_prompt_for_task
from kindle_to_anki.core.bootstrap import bootstrap_all


class UpdateTaskRow(ctk.CTkFrame):
    """A task row for Update Notes view - with enable checkbox and config options."""

    def __init__(self, parent, task_key: str, task_settings: dict, source_language_code: str = None):
        super().__init__(parent, fg_color="transparent")
        self.task_key = task_key
        self.task_settings = task_settings
        self.source_language_code = source_language_code
        self.metadata = TASK_METADATA.get(task_key, {})

        # Get available runtimes for this task
        self.available_runtimes = get_runtimes_for_task(task_key, source_language_code)
        self.runtime_map = {rt.id: rt for rt in self.available_runtimes}

        self._create_widgets()

    def _create_widgets(self):
        self.grid_columnconfigure(0, weight=0, minsize=30)
        self.grid_columnconfigure(1, weight=1, minsize=160)
        self.grid_columnconfigure(2, weight=0, minsize=180)
        self.grid_columnconfigure(3, weight=0, minsize=150)
        self.grid_columnconfigure(4, weight=0, minsize=140)
        self.grid_columnconfigure(5, weight=0, minsize=80)

        col = 0

        # Enable checkbox - all tasks start disabled
        self.enabled_var = ctk.BooleanVar(value=False)
        self.enabled_cb = ctk.CTkCheckBox(
            self,
            text="",
            variable=self.enabled_var,
            width=20,
            command=self._on_enabled_change
        )
        self.enabled_cb.grid(row=0, column=col, padx=(5, 0), sticky="w")
        col += 1

        # Task name and description
        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.grid(row=0, column=col, padx=5, sticky="w")

        self.name_label = ctk.CTkLabel(
            name_frame,
            text=self.metadata.get("name", self.task_key),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray"
        )
        self.name_label.pack(anchor="w")

        self.desc_label = ctk.CTkLabel(
            name_frame,
            text=self.metadata.get("description", ""),
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.desc_label.pack(anchor="w")
        col += 1

        # Runtime dropdown
        runtime_ids = [rt.id for rt in self.available_runtimes]
        current_runtime = self.task_settings.get("runtime", runtime_ids[0] if runtime_ids else "")
        if current_runtime not in runtime_ids and runtime_ids:
            current_runtime = runtime_ids[0]

        self.runtime_var = ctk.StringVar(value=current_runtime)
        self.runtime_dropdown = ctk.CTkOptionMenu(
            self,
            values=runtime_ids if runtime_ids else ["(none)"],
            variable=self.runtime_var,
            width=170,
            command=self._on_runtime_change,
            state="disabled"
        )
        self.runtime_dropdown.grid(row=0, column=col, padx=5, sticky="w")
        col += 1

        # Model dropdown
        self.model_var = ctk.StringVar(value=self.task_settings.get("model_id", ""))
        self.model_dropdown = ctk.CTkOptionMenu(
            self,
            values=["(none)"],
            variable=self.model_var,
            width=140,
            state="disabled"
        )
        self.model_dropdown.grid(row=0, column=col, padx=5, sticky="w")
        col += 1

        # Prompt dropdown
        self.available_prompts = get_prompts_for_task(self.task_key, self.source_language_code)
        default_prompt = get_default_prompt_for_task(self.task_key, self.source_language_code)
        current_prompt = self.task_settings.get("prompt_id") or default_prompt or ""
        if self.available_prompts and current_prompt not in self.available_prompts:
            current_prompt = self.available_prompts[0] if self.available_prompts else ""

        self.prompt_var = ctk.StringVar(value=current_prompt)
        self.prompt_dropdown = ctk.CTkOptionMenu(
            self,
            values=self.available_prompts if self.available_prompts else ["(none)"],
            variable=self.prompt_var,
            width=130,
            state="disabled"
        )
        self.prompt_dropdown.grid(row=0, column=col, padx=5, sticky="w")
        col += 1

        # Batch size
        self.batch_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.batch_frame.grid(row=0, column=col, padx=5, sticky="w")

        self.batch_label = ctk.CTkLabel(self.batch_frame, text="Batch:", font=ctk.CTkFont(size=11), text_color="gray")
        self.batch_label.pack(side="left")
        self.batch_var = ctk.StringVar(value=str(self.task_settings.get("batch_size", 30)))
        self.batch_entry = ctk.CTkEntry(
            self.batch_frame,
            textvariable=self.batch_var,
            width=50,
            state="disabled"
        )
        self.batch_entry.pack(side="left", padx=(3, 0))

        # Initialize model options (but keep disabled)
        self._update_model_options(update_state=False)

    def _on_runtime_change(self, _=None):
        self._update_model_options()

    def _update_model_options(self, update_state=True):
        """Update model dropdown based on selected runtime."""
        runtime_id = self.runtime_var.get()
        runtime = self.runtime_map.get(runtime_id)

        if not runtime:
            self.model_dropdown.configure(values=["(n/a)"])
            self.model_var.set("(n/a)")
            return

        models = get_models_for_runtime(runtime)
        if models:
            self.model_dropdown.configure(values=models)
            current = self.model_var.get()
            if current not in models:
                self.model_var.set(models[0])
        else:
            self.model_dropdown.configure(values=["(n/a)"])
            self.model_var.set("(n/a)")

        if update_state:
            self._update_enabled_state()

    def _on_enabled_change(self):
        self._update_enabled_state()

    def _update_enabled_state(self):
        enabled = self.enabled_var.get()
        runtime_id = self.runtime_var.get()
        runtime = self.runtime_map.get(runtime_id)

        if enabled:
            self.name_label.configure(text_color=("gray10", "gray90"))
            self.runtime_dropdown.configure(state="normal")

            # Enable model if runtime supports it
            models = get_models_for_runtime(runtime) if runtime else []
            has_models = len(models) > 0
            if has_models:
                self.model_dropdown.configure(state="normal")
            else:
                self.model_dropdown.configure(state="disabled")

            # Enable prompt dropdown only if runtime uses models (LLM-based) and prompts exist
            has_prompts = has_models and len(self.available_prompts) > 0
            self.prompt_dropdown.configure(state="normal" if has_prompts else "disabled")

            # Enable batch if runtime supports it
            has_batching = getattr(runtime, 'supports_batching', True) if runtime else True
            self.batch_entry.configure(state="normal" if has_batching else "disabled")
            self.batch_label.configure(text_color=("gray10", "gray90") if has_batching else "gray")
        else:
            self.name_label.configure(text_color="gray")
            self.runtime_dropdown.configure(state="disabled")
            self.model_dropdown.configure(state="disabled")
            self.prompt_dropdown.configure(state="disabled")
            self.batch_entry.configure(state="disabled")
            self.batch_label.configure(text_color="gray")

    def is_enabled(self) -> bool:
        return self.enabled_var.get()

    def get_settings(self) -> dict:
        """Get current settings for this task."""
        model_val = self.model_var.get()
        prompt_val = self.prompt_var.get()
        return {
            "enabled": self.enabled_var.get(),
            "runtime": self.runtime_var.get(),
            "model_id": model_val if model_val != "(n/a)" else None,
            "prompt_id": prompt_val if prompt_val and prompt_val != "(none)" else None,
            "batch_size": int(self.batch_var.get()) if self.batch_var.get().isdigit() else 30
        }


class UpdateNotesView(ctk.CTkFrame):
    """Update Notes view - filter builder for selecting cards to update."""

    def __init__(self, master, on_back: Callable):
        super().__init__(master)
        self.on_back = on_back
        self.config_manager = ConfigManager()
        self.anki_decks = self.config_manager.get_anki_decks_by_source_language()

        self._create_widgets()
        self._update_filter_preview()

    def _create_widgets(self):
        # Header with back button
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        back_btn = ctk.CTkButton(
            header,
            text="← Back",
            width=80,
            command=self.on_back
        )
        back_btn.pack(side="left")

        title = ctk.CTkLabel(
            header,
            text="Update Notes",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(side="left", padx=20)

        # Main content - scrollable
        content_frame = ctk.CTkScrollableFrame(self)
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Filter Builder Section
        filter_section = ctk.CTkFrame(content_frame)
        filter_section.pack(fill="x", pady=(0, 15))

        filter_title = ctk.CTkLabel(
            filter_section,
            text="Filter Builder",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        filter_title.pack(anchor="w", padx=15, pady=(15, 10))

        # Deck selection
        deck_frame = ctk.CTkFrame(filter_section, fg_color="transparent")
        deck_frame.pack(fill="x", padx=15, pady=5)

        deck_label = ctk.CTkLabel(deck_frame, text="Parent Deck:", width=120, anchor="w")
        deck_label.pack(side="left")

        # Build display names: "lang_code - parent_deck_name"
        self.deck_display_to_lang = {}
        deck_display_names = []
        for lang_code, deck in self.anki_decks.items():
            display = f"{lang_code} - {deck.parent_deck_name}"
            deck_display_names.append(display)
            self.deck_display_to_lang[display] = lang_code

        self.deck_var = ctk.StringVar(value=deck_display_names[0] if deck_display_names else "")
        self.deck_dropdown = ctk.CTkOptionMenu(
            deck_frame,
            variable=self.deck_var,
            values=deck_display_names,
            width=400,
            command=self._on_deck_change
        )
        self.deck_dropdown.pack(side="left", padx=(10, 0))

        # Deck type filter (parent/import/not import)
        deck_type_frame = ctk.CTkFrame(filter_section, fg_color="transparent")
        deck_type_frame.pack(fill="x", padx=15, pady=10)

        deck_type_label = ctk.CTkLabel(deck_type_frame, text="Deck Scope:", width=120, anchor="w")
        deck_type_label.pack(side="left")

        self.deck_type_var = ctk.StringVar(value="parent")

        radio_container = ctk.CTkFrame(deck_type_frame, fg_color="transparent")
        radio_container.pack(side="left", padx=(10, 0))

        parent_radio = ctk.CTkRadioButton(
            radio_container,
            text="Parent Deck",
            variable=self.deck_type_var,
            value="parent",
            command=self._on_filter_change
        )
        parent_radio.pack(side="left", padx=(0, 15))

        import_radio = ctk.CTkRadioButton(
            radio_container,
            text="Import Deck",
            variable=self.deck_type_var,
            value="import",
            command=self._on_filter_change
        )
        import_radio.pack(side="left", padx=(0, 15))

        not_import_radio = ctk.CTkRadioButton(
            radio_container,
            text="Not Import Deck",
            variable=self.deck_type_var,
            value="not_import",
            command=self._on_filter_change
        )
        not_import_radio.pack(side="left")

        # Card state filter (new/not new/neither)
        card_state_frame = ctk.CTkFrame(filter_section, fg_color="transparent")
        card_state_frame.pack(fill="x", padx=15, pady=10)

        card_state_label = ctk.CTkLabel(card_state_frame, text="Card State:", width=120, anchor="w")
        card_state_label.pack(side="left")

        self.card_state_var = ctk.StringVar(value="any")

        state_container = ctk.CTkFrame(card_state_frame, fg_color="transparent")
        state_container.pack(side="left", padx=(10, 0))

        any_radio = ctk.CTkRadioButton(
            state_container,
            text="Any",
            variable=self.card_state_var,
            value="any",
            command=self._on_filter_change
        )
        any_radio.pack(side="left", padx=(0, 15))

        new_radio = ctk.CTkRadioButton(
            state_container,
            text="New Cards",
            variable=self.card_state_var,
            value="new",
            command=self._on_filter_change
        )
        new_radio.pack(side="left", padx=(0, 15))

        not_new_radio = ctk.CTkRadioButton(
            state_container,
            text="Not New Cards",
            variable=self.card_state_var,
            value="not_new",
            command=self._on_filter_change
        )
        not_new_radio.pack(side="left")

        # Additional filter text box
        additional_frame = ctk.CTkFrame(filter_section, fg_color="transparent")
        additional_frame.pack(fill="x", padx=15, pady=10)

        additional_label = ctk.CTkLabel(additional_frame, text="Additional Filter:", width=120, anchor="w")
        additional_label.pack(side="left")

        self.additional_filter_var = ctk.StringVar(value="")
        self.additional_filter_entry = ctk.CTkEntry(
            additional_frame,
            textvariable=self.additional_filter_var,
            width=400,
            placeholder_text="e.g. prop:ivl>=100"
        )
        self.additional_filter_entry.pack(side="left", padx=(10, 0))
        self.additional_filter_var.trace_add("write", lambda *args: self._on_filter_change())

        # Filter Preview Section
        preview_section = ctk.CTkFrame(content_frame)
        preview_section.pack(fill="x", pady=(0, 15))

        preview_title = ctk.CTkLabel(
            preview_section,
            text="Filter Preview",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        preview_title.pack(anchor="w", padx=15, pady=(15, 10))

        preview_container = ctk.CTkFrame(preview_section, fg_color=("gray90", "gray17"))
        preview_container.pack(fill="x", padx=15, pady=(0, 15))

        self.filter_preview_label = ctk.CTkLabel(
            preview_container,
            text="",
            font=ctk.CTkFont(family="Consolas", size=12),
            wraplength=900,
            justify="left"
        )
        self.filter_preview_label.pack(padx=15, pady=15, anchor="w")

        # Task Options Section
        self.task_section = ctk.CTkFrame(content_frame)
        self.task_section.pack(fill="x", pady=(0, 15))

        task_title = ctk.CTkLabel(
            self.task_section,
            text="Task Options",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        task_title.pack(anchor="w", padx=15, pady=(15, 10))

        # Header row for task config
        header_frame = ctk.CTkFrame(self.task_section, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(0, 5))
        header_frame.grid_columnconfigure(0, weight=0, minsize=30)
        header_frame.grid_columnconfigure(1, weight=1, minsize=160)
        header_frame.grid_columnconfigure(2, weight=0, minsize=180)
        header_frame.grid_columnconfigure(3, weight=0, minsize=150)
        header_frame.grid_columnconfigure(4, weight=0, minsize=140)
        header_frame.grid_columnconfigure(5, weight=0, minsize=80)

        ctk.CTkLabel(header_frame, text="", width=30).grid(row=0, column=0)
        ctk.CTkLabel(header_frame, text="Task", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=1, sticky="w", padx=5)
        ctk.CTkLabel(header_frame, text="Runtime", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=2, sticky="w", padx=5)
        ctk.CTkLabel(header_frame, text="Model", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=3, sticky="w", padx=5)
        ctk.CTkLabel(header_frame, text="Prompt", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=4, sticky="w", padx=5)
        ctk.CTkLabel(header_frame, text="Batch", font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=5, sticky="w", padx=5)

        # Task rows container
        self.task_rows_frame = ctk.CTkFrame(self.task_section, fg_color="transparent")
        self.task_rows_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.task_rows = {}
        self._build_task_rows()

        # Processing Options Section
        options_section = ctk.CTkFrame(content_frame)
        options_section.pack(fill="x", pady=(0, 15))

        options_title = ctk.CTkLabel(
            options_section,
            text="Processing Options",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        options_title.pack(anchor="w", padx=15, pady=(15, 10))

        options_frame = ctk.CTkFrame(options_section, fg_color="transparent")
        options_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.skip_matching_metadata_var = ctk.BooleanVar(value=True)
        self.skip_matching_metadata_cb = ctk.CTkCheckBox(
            options_frame,
            text="Skip cards with matching task metadata (already processed with same config)",
            variable=self.skip_matching_metadata_var
        )
        self.skip_matching_metadata_cb.pack(anchor="w")

        # Query Preview Section
        query_section = ctk.CTkFrame(content_frame)
        query_section.pack(fill="x", pady=(0, 15))

        query_title = ctk.CTkLabel(
            query_section,
            text="Query Preview",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        query_title.pack(anchor="w", padx=15, pady=(15, 10))

        query_btn_frame = ctk.CTkFrame(query_section, fg_color="transparent")
        query_btn_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.query_btn = ctk.CTkButton(
            query_btn_frame,
            text="Query Cards",
            width=150,
            command=self._on_query_cards
        )
        self.query_btn.pack(side="left")

        self.query_status_label = ctk.CTkLabel(
            query_btn_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        )
        self.query_status_label.pack(side="left", padx=(15, 0))

        # Statistics display
        stats_frame = ctk.CTkFrame(query_section, fg_color=("gray90", "gray17"))
        stats_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.stats_total_label = ctk.CTkLabel(
            stats_frame,
            text="Total matching cards: —",
            font=ctk.CTkFont(size=12)
        )
        self.stats_total_label.pack(anchor="w", padx=15, pady=(10, 5))

        self.stats_to_process_label = ctk.CTkLabel(
            stats_frame,
            text="Cards to process: —",
            font=ctk.CTkFont(size=12)
        )
        self.stats_to_process_label.pack(anchor="w", padx=15, pady=(0, 5))

        self.stats_skipped_label = ctk.CTkLabel(
            stats_frame,
            text="Cards to skip (matching metadata): —",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        )
        self.stats_skipped_label.pack(anchor="w", padx=15, pady=(0, 10))

        # Run button
        run_frame = ctk.CTkFrame(query_section, fg_color="transparent")
        run_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.run_btn = ctk.CTkButton(
            run_frame,
            text="Run Selected Tasks",
            width=180,
            state="disabled"
        )
        self.run_btn.pack(side="left")

    def _on_filter_change(self, *args):
        """Called when any filter option changes."""
        self._update_filter_preview()
        self._reset_query_stats()

    def _on_deck_change(self, *args):
        """Called when deck selection changes - rebuild task rows."""
        self._update_filter_preview()
        self._build_task_rows()
        self._reset_query_stats()

    def _build_task_rows(self):
        """Build task configuration rows based on selected deck."""
        # Clear existing rows
        for widget in self.task_rows_frame.winfo_children():
            widget.destroy()
        self.task_rows.clear()

        # Get current deck for task settings
        deck = self.get_selected_deck()
        source_lang = deck.source_language_code if deck else None

        bootstrap_all()

        for task_key in TASK_ORDER:
            task_settings = deck.get_task_setting(task_key) if deck else {}
            row = UpdateTaskRow(
                self.task_rows_frame,
                task_key=task_key,
                task_settings=task_settings,
                source_language_code=source_lang
            )
            row.pack(fill="x", pady=2)
            self.task_rows[task_key] = row

    def _build_filter_query(self) -> str:
        """Build the Anki search query based on current filter selections."""
        parts = []

        # Get selected deck
        selected_display = self.deck_var.get()
        selected_lang = self.deck_display_to_lang.get(selected_display)
        deck = self.anki_decks.get(selected_lang) if selected_lang else None
        if not deck:
            return "(no deck selected)"

        # Deck scope filter
        deck_type = self.deck_type_var.get()
        if deck_type == "parent":
            parts.append(f'"deck:{deck.parent_deck_name}"')
        elif deck_type == "import":
            parts.append(f'"deck:{deck.staging_deck_name}"')
        elif deck_type == "not_import":
            parts.append(f'"deck:{deck.parent_deck_name}" -"deck:{deck.staging_deck_name}"')

        # Note type filter
        parts.append(f'"note:{NOTE_TYPE_NAME}"')

        # Card state filter
        card_state = self.card_state_var.get()
        if card_state == "new":
            parts.append("is:new")
        elif card_state == "not_new":
            parts.append("-is:new")

        # Additional filter
        additional = self.additional_filter_var.get().strip()
        if additional:
            parts.append(additional)

        return " ".join(parts)

    def _update_filter_preview(self):
        """Update the filter preview label with the current query."""
        query = self._build_filter_query()
        self.filter_preview_label.configure(text=query)

    def get_current_filter(self) -> str:
        """Get the current filter query string."""
        return self._build_filter_query()

    def get_selected_deck(self):
        """Get the currently selected deck object."""
        selected_display = self.deck_var.get()
        selected_lang = self.deck_display_to_lang.get(selected_display)
        return self.anki_decks.get(selected_lang) if selected_lang else None

    def get_selected_tasks(self) -> list[str]:
        """Get list of task keys that are currently enabled."""
        return [key for key, row in self.task_rows.items() if row.is_enabled()]

    def get_task_settings(self) -> dict[str, dict]:
        """Get settings for all enabled tasks."""
        return {key: row.get_settings() for key, row in self.task_rows.items() if row.is_enabled()}

    def get_skip_matching_metadata(self) -> bool:
        """Get whether to skip cards with matching task metadata."""
        return self.skip_matching_metadata_var.get()

    def _reset_query_stats(self):
        """Reset the query statistics display."""
        self.stats_total_label.configure(text="Total matching cards: —")
        self.stats_to_process_label.configure(text="Cards to process: —")
        self.stats_skipped_label.configure(text="Cards to skip (matching metadata): —")
        self.query_status_label.configure(text="")

    def _on_query_cards(self):
        """Query Anki for cards matching the filter and compute statistics."""
        selected_tasks = self.get_selected_tasks()
        if not selected_tasks:
            self.query_status_label.configure(text="No tasks selected", text_color="orange")
            return

        self.query_btn.configure(state="disabled")
        self.query_status_label.configure(text="Querying...", text_color=("gray50", "gray60"))

        # Run query in background thread
        thread = threading.Thread(target=self._run_query_thread, daemon=True)
        thread.start()

    def _run_query_thread(self):
        """Background thread to query Anki and compute statistics."""
        try:
            anki = AnkiConnect()
            query = self.get_current_filter()

            # Find matching notes
            note_ids = anki._invoke("findNotes", {"query": query})
            total_count = len(note_ids)

            if total_count == 0:
                self.after(0, lambda: self._update_query_stats(0, 0, 0, "No cards found"))
                return

            # Get note info for metadata checking
            notes_info = anki._invoke("notesInfo", {"notes": note_ids})

            # Compute statistics based on selected tasks and skip option
            task_settings = self.get_task_settings()
            skip_matching = self.get_skip_matching_metadata()

            if skip_matching and task_settings:
                # Count how many notes would be skipped per task
                to_process = 0
                for note in notes_info:
                    note_needs_processing = False
                    for task_key, settings in task_settings.items():
                        if not self._metadata_matches(note, task_key, settings):
                            note_needs_processing = True
                            break
                    if note_needs_processing:
                        to_process += 1
                skipped = total_count - to_process
            else:
                to_process = total_count
                skipped = 0

            self.after(0, lambda: self._update_query_stats(total_count, to_process, skipped, "Query complete"))

        except Exception as e:
            self.after(0, lambda: self._update_query_stats(0, 0, 0, f"Error: {str(e)[:50]}"))

    def _metadata_matches(self, note: dict, task_key: str, settings: dict) -> bool:
        """Check if note's metadata matches the task settings."""
        fields = note.get('fields', {})
        metadata_str = fields.get('Generation_Metadata', {}).get('value', '').strip()
        if not metadata_str:
            return False
        try:
            metadata = json.loads(metadata_str)
            task_meta = metadata.get(task_key)
            if not task_meta:
                return False
            stored_prompt = task_meta.get("prompt")
            return (
                task_meta.get("runtime") == settings.get("runtime")
                and task_meta.get("model") == settings.get("model_id")
                and stored_prompt == settings.get("prompt_id")
            )
        except json.JSONDecodeError:
            return False

    def _update_query_stats(self, total: int, to_process: int, skipped: int, status: str):
        """Update the query statistics display (called from main thread)."""
        self.stats_total_label.configure(text=f"Total matching cards: {total}")
        self.stats_to_process_label.configure(text=f"Cards to process: {to_process}")
        self.stats_skipped_label.configure(text=f"Cards to skip (matching metadata): {skipped}")

        if "Error" in status:
            self.query_status_label.configure(text=status, text_color="red")
        else:
            self.query_status_label.configure(text=status, text_color=("gray50", "gray60"))

        self.query_btn.configure(state="normal")
