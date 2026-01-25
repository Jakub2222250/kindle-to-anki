import customtkinter as ctk
from typing import Callable

from kindle_to_anki.anki.constants import NOTE_TYPE_NAME
from kindle_to_anki.configuration.config_manager import ConfigManager


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
            command=self._on_filter_change
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

        # Task Options Section (placeholder)
        task_section = ctk.CTkFrame(content_frame)
        task_section.pack(fill="x", pady=(0, 15))

        task_title = ctk.CTkLabel(
            task_section,
            text="Task Options",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        task_title.pack(anchor="w", padx=15, pady=(15, 10))

        placeholder_label = ctk.CTkLabel(
            task_section,
            text="Task selection and execution options will be implemented here.",
            font=ctk.CTkFont(size=12),
            text_color=("gray50", "gray60")
        )
        placeholder_label.pack(padx=15, pady=(0, 15))

    def _on_filter_change(self, *args):
        """Called when any filter option changes."""
        self._update_filter_preview()

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
