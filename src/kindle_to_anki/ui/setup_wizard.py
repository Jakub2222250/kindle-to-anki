import customtkinter as ctk
from tkinter import messagebox
import threading
import json
from pathlib import Path

from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.ui.task_config import TaskConfigPanel


# Common languages for vocabulary learning (subset of pycountry for usability)
COMMON_LANGUAGES = [
    ("en", "English"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("it", "Italian"),
    ("pt", "Portuguese"),
    ("pl", "Polish"),
    ("ru", "Russian"),
    ("ja", "Japanese"),
    ("zh", "Chinese"),
    ("ko", "Korean"),
    ("nl", "Dutch"),
    ("sv", "Swedish"),
    ("no", "Norwegian"),
    ("da", "Danish"),
    ("fi", "Finnish"),
    ("cs", "Czech"),
    ("uk", "Ukrainian"),
    ("tr", "Turkish"),
    ("ar", "Arabic"),
    ("he", "Hebrew"),
    ("hi", "Hindi"),
    ("th", "Thai"),
    ("vi", "Vietnamese"),
    ("id", "Indonesian"),
]

DEFAULT_ANKI_CONNECT_URL = "http://localhost:8765"

# Provider info: id -> (display_name, env_var, setup_url)
PROVIDER_INFO = {
    "gemini": ("Gemini", "GEMINI_API_KEY", "https://aistudio.google.com/apikey"),
    "openai": ("OpenAI", "OPENAI_API_KEY", "https://platform.openai.com/api-keys"),
    "grok": ("Grok (xAI)", "XAI_API_KEY", "https://console.x.ai/"),
    "deepl": ("DeepL", "DEEPL_API_KEY", "https://www.deepl.com/your-account/keys"),
}

DEFAULT_TASK_SETTINGS = {
    "lui": {"runtime": "chat_completion_lui", "model_id": "gemini-2.5-flash", "batch_size": 30},
    "wsd": {"runtime": "chat_completion_wsd", "model_id": "gemini-2.5-flash", "batch_size": 30},
    "hint": {"enabled": True, "runtime": "chat_completion_hint", "model_id": "gemini-2.5-flash", "batch_size": 30},
    "cloze_scoring": {"enabled": True, "runtime": "chat_completion_cloze_scoring", "model_id": "gemini-2.5-flash", "batch_size": 30},
    "usage_level": {"enabled": True, "runtime": "chat_completion_usage_level", "model_id": "gemini-2.5-flash", "batch_size": 30},
    "translation": {"runtime": "chat_completion_translation", "model_id": "gemini-2.5-flash", "batch_size": 30},
    "collocation": {"enabled": True, "runtime": "chat_completion_collocation", "model_id": "gemini-2.0-flash", "batch_size": 30}
}


def get_config_path() -> Path:
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent.parent.parent
    return project_root / "data" / "config" / "config.json"


def load_config() -> dict:
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Ensure anki_connect_url exists with default
            if "anki_connect_url" not in config:
                config["anki_connect_url"] = DEFAULT_ANKI_CONNECT_URL
            return config
    return {"anki_decks": [], "anki_connect_url": DEFAULT_ANKI_CONNECT_URL}


def save_config(config: dict):
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


class AnkiConnectionManager:
    """Manages AnkiConnect connection with lazy initialization."""

    _instance = None
    _anki_connect = None
    _is_connected = None
    _url = None

    @classmethod
    def get_connection(cls, url: str = None) -> tuple[AnkiConnect | None, bool]:
        """Get or create AnkiConnect instance. Returns (instance, is_connected)."""
        if url is None:
            url = load_config().get("anki_connect_url", DEFAULT_ANKI_CONNECT_URL)

        # Reset if URL changed
        if cls._url != url:
            cls.reset()
            cls._url = url

        if cls._anki_connect is None:
            try:
                from kindle_to_anki.anki.constants import NOTE_TYPE_NAME
                cls._anki_connect = object.__new__(AnkiConnect)
                cls._anki_connect.anki_url = url
                cls._anki_connect.note_type = NOTE_TYPE_NAME
                cls._is_connected = cls._anki_connect.is_reachable()
            except Exception:
                cls._is_connected = False
        return cls._anki_connect, cls._is_connected

    @classmethod
    def check_connection(cls, url: str = None) -> bool:
        """Check if Anki is reachable (refreshes connection status)."""
        if url is None:
            url = load_config().get("anki_connect_url", DEFAULT_ANKI_CONNECT_URL)

        # Reset if URL changed
        if cls._url != url:
            cls.reset()
            cls._url = url

        if cls._anki_connect is None:
            cls.get_connection(url)
        else:
            cls._is_connected = cls._anki_connect.is_reachable()
        return cls._is_connected

    @classmethod
    def reset(cls):
        """Reset connection state."""
        cls._anki_connect = None
        cls._is_connected = None
        cls._url = None


class SetupWizardFrame(ctk.CTkFrame):
    """Setup wizard frame for deck management."""

    def __init__(self, parent, on_back=None):
        super().__init__(parent)
        self.on_back = on_back
        self._anki_connected = False
        self._checking_connection = False
        self._current_deck_index = 0

        # Language options setup
        self.language_options = [f"{name} ({code})" for code, name in COMMON_LANGUAGES]
        self.language_codes = {f"{name} ({code})": code for code, name in COMMON_LANGUAGES}

        self._create_widgets()
        self._refresh_view()

    def _create_widgets(self):
        # Top bar with back button and title
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(10, 5))

        self.back_btn = ctk.CTkButton(
            top_bar,
            text="← Back",
            width=80,
            command=self._on_back
        )
        self.back_btn.pack(side="left")

        self.title_label = ctk.CTkLabel(
            top_bar,
            text="Setup",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(side="left", padx=(15, 0))

        # Scrollable content area
        self.scroll_container = ctk.CTkScrollableFrame(self)
        self.scroll_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # AnkiConnect card
        self._create_anki_connect_card()

        # Provider card (TODO)
        self._create_provider_card()

        # Decks card (main container will be inside this)
        self._create_decks_card()

        # Bottom button bar (fixed at bottom, outside scroll)
        self._create_bottom_buttons()

    def _create_bottom_buttons(self):
        """Create the global save/cancel buttons at the bottom."""
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            width=100,
            fg_color="gray",
            command=self._on_back
        )
        self.cancel_btn.pack(side="left")

        self.save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            width=100,
            command=self._save_all
        )
        self.save_btn.pack(side="right")

        # Global status label
        self.global_save_status = ctk.CTkLabel(
            button_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.global_save_status.pack(side="right", padx=20)

    def _create_anki_connect_card(self):
        """Create the AnkiConnect configuration card."""
        config = load_config()

        card = ctk.CTkFrame(self.scroll_container)
        card.pack(fill="x", pady=(0, 10))

        # Header
        ctk.CTkLabel(
            card,
            text="AnkiConnect",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # AnkiConnect URL row
        url_frame = ctk.CTkFrame(card, fg_color="transparent")
        url_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(url_frame, text="URL:").pack(side="left", padx=(0, 5))

        self.anki_url_var = ctk.StringVar(value=config.get("anki_connect_url", DEFAULT_ANKI_CONNECT_URL))
        self.anki_url_entry = ctk.CTkEntry(url_frame, textvariable=self.anki_url_var, width=220)
        self.anki_url_entry.pack(side="left", padx=(0, 10))

        self.validate_btn = ctk.CTkButton(
            url_frame,
            text="Validate",
            width=80,
            command=self._validate_anki_connection
        )
        self.validate_btn.pack(side="left", padx=(0, 10))

        self.setup_note_type_btn = ctk.CTkButton(
            url_frame,
            text="Setup/Validate Note Type",
            width=160,
            command=self._setup_note_type
        )
        self.setup_note_type_btn.pack(side="left")

        # Status/info label
        self.global_status_label = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=600,
            justify="left"
        )
        self.global_status_label.pack(fill="x", padx=10, pady=(0, 10))

    def _create_provider_card(self):
        """Create the Provider configuration card."""
        card = ctk.CTkFrame(self.scroll_container)
        card.pack(fill="x", pady=(0, 10))
        self._provider_card = card

        # Header row with title and validate button
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkLabel(
            header_frame,
            text="Providers",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        self.validate_providers_btn = ctk.CTkButton(
            header_frame,
            text="Validate",
            width=80,
            command=self._validate_providers
        )
        self.validate_providers_btn.pack(side="right")

        # Provider list container
        self.provider_list_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.provider_list_frame.pack(fill="x", padx=10, pady=(0, 10))

        self._refresh_provider_list()

    def _create_decks_card(self):
        """Create the Decks configuration card."""
        card = ctk.CTkFrame(self.scroll_container)
        card.pack(fill="both", expand=True, pady=(0, 10))

        # Header
        ctk.CTkLabel(
            card,
            text="Decks",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=10, pady=(10, 5))

        # Main container for deck content (will switch between add-deck and deck-config views)
        self.main_container = ctk.CTkFrame(card, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=5, pady=(0, 10))

    def _validate_anki_connection(self):
        """Validate AnkiConnect connection and save URL if successful."""
        if self._checking_connection:
            return

        url = self.anki_url_var.get().strip()
        if not url:
            self.global_status_label.configure(text="Please enter a URL", text_color="red")
            return

        self._checking_connection = True
        self.validate_btn.configure(state="disabled")
        self.global_status_label.configure(text="⟳ Checking connection...", text_color="gray")

        def check():
            AnkiConnectionManager.reset()
            anki, connected = AnkiConnectionManager.get_connection(url)
            self.after(0, lambda: self._on_validate_done(connected, url))

        threading.Thread(target=check, daemon=True).start()

    def _on_validate_done(self, connected: bool, url: str):
        self._checking_connection = False
        self.validate_btn.configure(state="normal")

        if connected:
            # Save the URL to config
            config = load_config()
            config["anki_connect_url"] = url
            save_config(config)
            self.global_status_label.configure(text="✓ Connected to AnkiConnect", text_color="green")
        else:
            help_text = (
                "✗ Cannot connect to AnkiConnect.\n"
                "Setup: In Anki, go to Tools → Add-ons → Get Add-ons, enter code 2055492159, "
                "restart Anki, then try again."
            )
            self.global_status_label.configure(text=help_text, text_color="red")

    def _get_used_providers(self) -> set[str]:
        """Get set of provider IDs used in current config and unsaved task panel."""
        from kindle_to_anki.core.bootstrap import bootstrap_all
        from kindle_to_anki.core.models.registry import ModelRegistry
        bootstrap_all()

        used = set()

        def extract_providers(task_settings: dict):
            for task_name, task_config in task_settings.items():
                model_id = task_config.get("model_id")
                runtime = task_config.get("runtime", "")
                if model_id:
                    try:
                        model = ModelRegistry.get(model_id)
                        used.add(model.platform_id)
                    except KeyError:
                        pass
                if "deepl" in runtime.lower():
                    used.add("deepl")

        # Check saved config for all decks
        config = load_config()
        for i, deck in enumerate(config.get("anki_decks", [])):
            # For current deck, use unsaved panel settings if available
            if hasattr(self, 'task_config_panel') and self.task_config_panel and i == self._current_deck_index:
                extract_providers(self.task_config_panel.get_all_settings())
            else:
                extract_providers(deck.get("task_settings", {}))

        return used

    def _refresh_provider_list(self):
        """Refresh the provider list display."""
        for widget in self.provider_list_frame.winfo_children():
            widget.destroy()

        used_providers = self._get_used_providers()

        for provider_id, (name, env_var, _) in PROVIDER_INFO.items():
            row = ctk.CTkFrame(self.provider_list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            is_used = provider_id in used_providers
            usage_text = "Used" if is_used else "Not used"
            usage_color = "#2a9d8f" if is_used else "gray"

            ctk.CTkLabel(row, text=name, width=100, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=f"({env_var})", width=160, anchor="w",
                         font=ctk.CTkFont(size=11), text_color="gray").pack(side="left")
            ctk.CTkLabel(row, text=usage_text, width=70, anchor="w",
                         font=ctk.CTkFont(size=11), text_color=usage_color).pack(side="left")

        # Status label for validation results
        self.provider_status_label = ctk.CTkLabel(
            self.provider_list_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=550,
            justify="left"
        )
        self.provider_status_label.pack(fill="x", pady=(5, 0))

    def _validate_providers(self):
        """Validate all used providers and show results."""
        self.validate_providers_btn.configure(state="disabled")
        self.provider_status_label.configure(text="⟳ Validating providers...", text_color="gray")

        def do_validate():
            from kindle_to_anki.core.bootstrap import bootstrap_all
            from kindle_to_anki.platforms.platform_registry import PlatformRegistry
            bootstrap_all()

            used_providers = self._get_used_providers()
            results = []

            for provider_id in used_providers:
                try:
                    platform = PlatformRegistry.get(provider_id)
                    is_valid = platform.validate_credentials()
                    results.append((provider_id, is_valid))
                except Exception:
                    results.append((provider_id, False))

            self.after(0, lambda: self._on_providers_validated(results))

        threading.Thread(target=do_validate, daemon=True).start()

    def _on_providers_validated(self, results: list[tuple[str, bool]]):
        """Handle provider validation results."""
        self.validate_providers_btn.configure(state="normal")

        if not results:
            self.provider_status_label.configure(
                text="No providers in use. Configure a deck first.",
                text_color="gray"
            )
            return

        valid = [p for p, ok in results if ok]
        invalid = [p for p, ok in results if not ok]

        lines = []
        if valid:
            names = [PROVIDER_INFO[p][0] for p in valid]
            lines.append(f"✓ Valid: {', '.join(names)}")

        if invalid:
            for provider_id in invalid:
                name, env_var, url = PROVIDER_INFO[provider_id]
                lines.append(f"✗ {name}: Set {env_var} environment variable. Get key at {url}")

        color = "green" if not invalid else ("orange" if valid else "red")
        self.provider_status_label.configure(text="\n".join(lines), text_color=color)

    def _setup_note_type(self):
        """Setup the note type in Anki."""
        if self._checking_connection:
            return

        self._checking_connection = True
        self.setup_note_type_btn.configure(state="disabled")
        self.global_status_label.configure(text="⟳ Setting up note type...", text_color="gray")

        def do_setup():
            url = self.anki_url_var.get().strip()
            AnkiConnectionManager.reset()
            anki, connected = AnkiConnectionManager.get_connection(url)

            if not connected:
                self.after(0, lambda: self._on_note_type_setup_done(False, "Cannot connect to AnkiConnect"))
                return

            try:
                from kindle_to_anki.anki.constants import NOTE_TYPE_NAME
                from kindle_to_anki.anki.setup_note_type import FIELDS, load_template, get_card_templates

                existing_models = anki.get_model_names()
                if NOTE_TYPE_NAME in existing_models:
                    self.after(0, lambda: self._on_note_type_setup_done(True, f"Note type '{NOTE_TYPE_NAME}' already exists"))
                else:
                    anki.create_model(NOTE_TYPE_NAME, FIELDS, load_template("style.css"), get_card_templates())
                    self.after(0, lambda: self._on_note_type_setup_done(True, f"Note type '{NOTE_TYPE_NAME}' created successfully"))
            except Exception as e:
                self.after(0, lambda: self._on_note_type_setup_done(False, str(e)))

        threading.Thread(target=do_setup, daemon=True).start()

    def _on_note_type_setup_done(self, success: bool, message: str):
        self._checking_connection = False
        self.setup_note_type_btn.configure(state="normal")
        color = "green" if success else "red"
        self.global_status_label.configure(text=message, text_color=color)

    def _clear_main_container(self):
        for widget in self.main_container.winfo_children():
            widget.destroy()

    def _refresh_view(self):
        """Refresh the UI based on whether decks exist."""
        config = load_config()
        decks = config.get("anki_decks", [])

        self._clear_main_container()

        if not decks:
            self._create_add_deck_view()
        else:
            self._create_deck_config_view(decks)

    def _create_add_deck_view(self):
        """View shown when no decks exist - for adding the first deck."""
        add_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        add_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            add_frame,
            text="Add New Deck",
            font=ctk.CTkFont(size=13)
        ).pack(anchor="w", pady=(5, 10))

        # Source language
        ctk.CTkLabel(add_frame, text="Source Language (learning):").pack(anchor="w")
        self.source_lang_var = ctk.StringVar(value=self.language_options[6])  # Polish
        self.source_lang_dropdown = ctk.CTkComboBox(
            add_frame,
            values=self.language_options,
            variable=self.source_lang_var,
            width=250,
            command=self._on_language_change
        )
        self.source_lang_dropdown.pack(anchor="w", pady=(0, 10))

        # Target language
        ctk.CTkLabel(add_frame, text="Target Language (native):").pack(anchor="w")
        self.target_lang_var = ctk.StringVar(value=self.language_options[0])  # English
        self.target_lang_dropdown = ctk.CTkComboBox(
            add_frame,
            values=self.language_options,
            variable=self.target_lang_var,
            width=250,
            command=self._on_language_change
        )
        self.target_lang_dropdown.pack(anchor="w", pady=(0, 10))

        # Parent deck name
        ctk.CTkLabel(add_frame, text="Parent Deck Name:").pack(anchor="w")
        self.parent_deck_var = ctk.StringVar(value="Polish Vocab Discovery")
        self.parent_deck_entry = ctk.CTkEntry(
            add_frame,
            textvariable=self.parent_deck_var,
            width=250
        )
        self.parent_deck_entry.pack(anchor="w", pady=(0, 10))

        # Auto-name import deck checkbox
        self.auto_import_var = ctk.BooleanVar(value=True)
        self.auto_import_checkbox = ctk.CTkCheckBox(
            add_frame,
            text="Auto-name import deck (Parent::Import)",
            variable=self.auto_import_var,
            command=self._on_auto_import_toggle
        )
        self.auto_import_checkbox.pack(anchor="w", pady=(0, 5))

        # Import deck name (readonly by default when auto-naming)
        ctk.CTkLabel(add_frame, text="Import Deck Name:").pack(anchor="w")
        self.import_deck_var = ctk.StringVar(value="Polish Vocab Discovery::Import")
        self.import_deck_entry = ctk.CTkEntry(
            add_frame,
            textvariable=self.import_deck_var,
            width=250,
            state="disabled"
        )
        self.import_deck_entry.pack(anchor="w", pady=(0, 10))

        # Bind parent deck change to update import deck
        self.parent_deck_var.trace_add("write", self._on_parent_deck_change)

        # Create in Anki checkbox
        self.create_in_anki_var = ctk.BooleanVar(value=True)
        self.create_in_anki_checkbox = ctk.CTkCheckBox(
            add_frame,
            text="Create deck in Anki if missing",
            variable=self.create_in_anki_var
        )
        self.create_in_anki_checkbox.pack(anchor="w", pady=(10, 5))

        # Add deck button
        self.add_deck_btn = ctk.CTkButton(
            add_frame,
            text="Add Deck",
            width=150,
            command=self._add_deck
        )
        self.add_deck_btn.pack(anchor="w", pady=10)

        # Status label
        self.status_label = ctk.CTkLabel(
            add_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.status_label.pack(pady=(0, 10))

    def _create_deck_config_view(self, decks: list):
        """View shown when decks exist - deck selector + task config."""
        # Top bar: deck selector dropdown + add/remove buttons
        top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent")
        top_bar.pack(fill="x", padx=5, pady=(5, 10))

        ctk.CTkLabel(top_bar, text="Deck:").pack(side="left", padx=(0, 5))

        # Build dropdown options
        self.deck_options = []
        for deck in decks:
            text = f"{deck['parent_deck_name']} ({deck['source_language_code']} → {deck['target_language_code']})"
            self.deck_options.append(text)

        # Ensure valid index
        if self._current_deck_index >= len(decks):
            self._current_deck_index = 0

        self.deck_selector_var = ctk.StringVar(value=self.deck_options[self._current_deck_index])
        self.deck_selector = ctk.CTkComboBox(
            top_bar,
            values=self.deck_options,
            variable=self.deck_selector_var,
            width=350,
            command=self._on_deck_selected,
            state="readonly"
        )
        self.deck_selector.pack(side="left", padx=(0, 10))

        # Add new deck button
        self.add_new_btn = ctk.CTkButton(
            top_bar,
            text="+ Add",
            width=70,
            command=self._show_add_deck_dialog
        )
        self.add_new_btn.pack(side="left", padx=(0, 5))

        # Remove deck button
        self.remove_btn = ctk.CTkButton(
            top_bar,
            text="Remove",
            width=70,
            fg_color="darkred",
            hover_color="red",
            command=self._remove_selected_deck
        )
        self.remove_btn.pack(side="left")

        # Status label (in top bar)
        self.status_label = ctk.CTkLabel(
            top_bar,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.status_label.pack(side="right", padx=10)

        # Task configuration panel (always visible)
        deck_config = decks[self._current_deck_index]
        self.task_config_panel = TaskConfigPanel(
            self.main_container,
            deck_config,
            on_change=self._on_task_config_change
        )
        self.task_config_panel.pack(fill="both", expand=True)

    def _on_task_config_change(self):
        """Called when task configuration changes - refresh provider list."""
        self._refresh_provider_list()

    def _on_deck_selected(self, selection: str):
        """Handle deck selection from dropdown."""
        try:
            self._current_deck_index = self.deck_options.index(selection)
        except ValueError:
            self._current_deck_index = 0
        self._refresh_view()

    def _show_add_deck_dialog(self):
        """Show dialog to add a new deck."""
        dialog = AddDeckDialog(self, on_add=self._on_new_deck_added)
        dialog.grab_set()

    def _on_new_deck_added(self):
        """Called when a new deck is added via dialog."""
        config = load_config()
        decks = config.get("anki_decks", [])
        self._current_deck_index = len(decks) - 1  # Select the newly added deck
        self._refresh_view()

    def _on_language_change(self, _=None):
        source = self.language_codes.get(self.source_lang_var.get(), "")
        for code, name in COMMON_LANGUAGES:
            if code == source:
                suggested_name = f"{name} Vocab Discovery"
                self.parent_deck_var.set(suggested_name)
                break

    def _on_parent_deck_change(self, *args):
        if hasattr(self, 'auto_import_var') and self.auto_import_var.get():
            parent = self.parent_deck_var.get()
            self.import_deck_var.set(f"{parent}::Import")

    def _on_auto_import_toggle(self):
        if self.auto_import_var.get():
            self.import_deck_entry.configure(state="disabled")
            self._on_parent_deck_change()
        else:
            self.import_deck_entry.configure(state="normal")

    def _add_deck(self):
        source_code = self.language_codes.get(self.source_lang_var.get())
        target_code = self.language_codes.get(self.target_lang_var.get())
        parent_deck = self.parent_deck_var.get().strip()
        import_deck = self.import_deck_var.get().strip()

        if not source_code or not target_code:
            messagebox.showerror("Error", "Please select valid languages.")
            return

        if source_code == target_code:
            messagebox.showerror("Error", "Source and target languages must be different.")
            return

        if not parent_deck:
            messagebox.showerror("Error", "Please enter a parent deck name.")
            return

        config = load_config()

        # Check for duplicate source language
        for deck in config.get("anki_decks", []):
            if deck["source_language_code"] == source_code:
                messagebox.showerror("Error", f"A deck for {self.source_lang_var.get()} already exists.")
                return

        new_deck = {
            "source_language_code": source_code,
            "target_language_code": target_code,
            "parent_deck_name": parent_deck,
            "staging_deck_name": import_deck,
            "task_settings": DEFAULT_TASK_SETTINGS.copy()
        }

        config["anki_decks"].append(new_deck)
        save_config(config)

        # Optionally create in Anki
        if hasattr(self, 'create_in_anki_var') and self.create_in_anki_var.get():
            self._create_decks_in_anki_async(parent_deck, import_deck)
        else:
            self._current_deck_index = len(config["anki_decks"]) - 1
            self._refresh_view()

    def _create_decks_in_anki_async(self, parent_deck: str, import_deck: str):
        """Create decks in Anki asynchronously."""
        if self._checking_connection:
            return

        self._checking_connection = True
        if hasattr(self, 'add_deck_btn'):
            self.add_deck_btn.configure(state="disabled")
        if hasattr(self, 'status_label'):
            self.status_label.configure(text="⟳ Creating decks in Anki...", text_color="gray")

        def check_and_create():
            AnkiConnectionManager.reset()
            anki, is_connected = AnkiConnectionManager.get_connection()

            if not is_connected:
                self.after(0, lambda: self._on_anki_create_done(False, "Cannot connect to Anki"))
                return

            try:
                existing_decks = anki.get_deck_names()
                for deck_name in [parent_deck, import_deck]:
                    if deck_name not in existing_decks:
                        anki.create_deck(deck_name)
                self.after(0, lambda: self._on_anki_create_done(True, "Decks created in Anki"))
            except Exception as e:
                self.after(0, lambda: self._on_anki_create_done(False, str(e)))

        thread = threading.Thread(target=check_and_create, daemon=True)
        thread.start()

    def _on_anki_create_done(self, success: bool, message: str):
        self._checking_connection = False
        config = load_config()
        self._current_deck_index = len(config.get("anki_decks", [])) - 1
        self._refresh_view()
        if hasattr(self, 'status_label'):
            color = "green" if success else "orange"
            self.status_label.configure(text=message, text_color=color)

    def _remove_selected_deck(self):
        config = load_config()
        decks = config.get("anki_decks", [])

        if self._current_deck_index < len(decks):
            removed = decks.pop(self._current_deck_index)
            config["anki_decks"] = decks
            save_config(config)

            # Adjust index if needed
            if self._current_deck_index >= len(decks) and len(decks) > 0:
                self._current_deck_index = len(decks) - 1
            elif len(decks) == 0:
                self._current_deck_index = 0

            self._refresh_view()
            if hasattr(self, 'status_label') and decks:
                self.status_label.configure(
                    text=f"Removed: {removed['parent_deck_name']}",
                    text_color="orange"
                )

    def _save_all(self):
        """Save all settings from all sections."""
        config = load_config()

        # Save AnkiConnect URL
        if hasattr(self, 'anki_url_var'):
            config["anki_connect_url"] = self.anki_url_var.get().strip()

        # Save task settings for current deck
        if hasattr(self, 'task_config_panel'):
            decks = config.get("anki_decks", [])
            if self._current_deck_index < len(decks):
                decks[self._current_deck_index]["task_settings"] = self.task_config_panel.get_all_settings()

        save_config(config)

        if hasattr(self, 'global_save_status'):
            self.global_save_status.configure(text="Settings saved", text_color="green")

    def _on_back(self):
        if self.on_back:
            self.on_back()


class AddDeckDialog(ctk.CTkToplevel):
    """Dialog for adding a new deck when decks already exist."""

    def __init__(self, parent, on_add=None):
        super().__init__(parent)
        self.on_add = on_add
        self._checking_connection = False

        self.title("Add New Deck")
        self.geometry("350x450")
        self.resizable(False, False)

        # Language options
        self.language_options = [f"{name} ({code})" for code, name in COMMON_LANGUAGES]
        self.language_codes = {f"{name} ({code})": code for code, name in COMMON_LANGUAGES}

        self._create_widgets()

    def _create_widgets(self):
        # Source language
        ctk.CTkLabel(self, text="Source Language (learning):").pack(anchor="w", padx=15, pady=(15, 0))
        self.source_lang_var = ctk.StringVar(value=self.language_options[6])
        self.source_lang_dropdown = ctk.CTkComboBox(
            self,
            values=self.language_options,
            variable=self.source_lang_var,
            width=300,
            command=self._on_language_change
        )
        self.source_lang_dropdown.pack(padx=15, pady=(0, 10))

        # Target language
        ctk.CTkLabel(self, text="Target Language (native):").pack(anchor="w", padx=15)
        self.target_lang_var = ctk.StringVar(value=self.language_options[0])
        self.target_lang_dropdown = ctk.CTkComboBox(
            self,
            values=self.language_options,
            variable=self.target_lang_var,
            width=300
        )
        self.target_lang_dropdown.pack(padx=15, pady=(0, 10))

        # Parent deck name
        ctk.CTkLabel(self, text="Parent Deck Name:").pack(anchor="w", padx=15)
        self.parent_deck_var = ctk.StringVar(value="Polish Vocab Discovery")
        self.parent_deck_entry = ctk.CTkEntry(self, textvariable=self.parent_deck_var, width=300)
        self.parent_deck_entry.pack(padx=15, pady=(0, 10))

        # Auto-name import deck
        self.auto_import_var = ctk.BooleanVar(value=True)
        self.auto_import_checkbox = ctk.CTkCheckBox(
            self,
            text="Auto-name import deck (Parent::Import)",
            variable=self.auto_import_var,
            command=self._on_auto_import_toggle
        )
        self.auto_import_checkbox.pack(anchor="w", padx=15, pady=(0, 5))

        # Import deck name
        ctk.CTkLabel(self, text="Import Deck Name:").pack(anchor="w", padx=15)
        self.import_deck_var = ctk.StringVar(value="Polish Vocab Discovery::Import")
        self.import_deck_entry = ctk.CTkEntry(self, textvariable=self.import_deck_var, width=300, state="disabled")
        self.import_deck_entry.pack(padx=15, pady=(0, 10))

        self.parent_deck_var.trace_add("write", self._on_parent_deck_change)

        # Create in Anki checkbox
        self.create_in_anki_var = ctk.BooleanVar(value=True)
        self.create_in_anki_checkbox = ctk.CTkCheckBox(
            self,
            text="Create deck in Anki if missing",
            variable=self.create_in_anki_var
        )
        self.create_in_anki_checkbox.pack(anchor="w", padx=15, pady=(10, 5))

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=15)

        self.cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", width=100, fg_color="gray", command=self.destroy)
        self.cancel_btn.pack(side="left")

        self.add_btn = ctk.CTkButton(btn_frame, text="Add Deck", width=100, command=self._add_deck)
        self.add_btn.pack(side="right")

        # Status
        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11), text_color="gray")
        self.status_label.pack(pady=(0, 10))

    def _on_language_change(self, _=None):
        source = self.language_codes.get(self.source_lang_var.get(), "")
        for code, name in COMMON_LANGUAGES:
            if code == source:
                self.parent_deck_var.set(f"{name} Vocab Discovery")
                break

    def _on_parent_deck_change(self, *args):
        if self.auto_import_var.get():
            self.import_deck_var.set(f"{self.parent_deck_var.get()}::Import")

    def _on_auto_import_toggle(self):
        if self.auto_import_var.get():
            self.import_deck_entry.configure(state="disabled")
            self._on_parent_deck_change()
        else:
            self.import_deck_entry.configure(state="normal")

    def _add_deck(self):
        source_code = self.language_codes.get(self.source_lang_var.get())
        target_code = self.language_codes.get(self.target_lang_var.get())
        parent_deck = self.parent_deck_var.get().strip()
        import_deck = self.import_deck_var.get().strip()

        if not source_code or not target_code:
            messagebox.showerror("Error", "Please select valid languages.")
            return
        if source_code == target_code:
            messagebox.showerror("Error", "Source and target languages must be different.")
            return
        if not parent_deck:
            messagebox.showerror("Error", "Please enter a parent deck name.")
            return

        config = load_config()
        for deck in config.get("anki_decks", []):
            if deck["source_language_code"] == source_code:
                messagebox.showerror("Error", f"A deck for {self.source_lang_var.get()} already exists.")
                return

        new_deck = {
            "source_language_code": source_code,
            "target_language_code": target_code,
            "parent_deck_name": parent_deck,
            "staging_deck_name": import_deck,
            "task_settings": DEFAULT_TASK_SETTINGS.copy()
        }
        config["anki_decks"].append(new_deck)
        save_config(config)

        if self.create_in_anki_var.get():
            self._create_in_anki_async(parent_deck, import_deck)
        else:
            self._finish()

    def _create_in_anki_async(self, parent_deck: str, import_deck: str):
        if self._checking_connection:
            return
        self._checking_connection = True
        self.add_btn.configure(state="disabled")
        self.status_label.configure(text="⟳ Creating in Anki...", text_color="gray")

        def do_create():
            AnkiConnectionManager.reset()
            anki, connected = AnkiConnectionManager.get_connection()
            if connected:
                try:
                    existing = anki.get_deck_names()
                    for deck in [parent_deck, import_deck]:
                        if deck not in existing:
                            anki.create_deck(deck)
                except Exception:
                    pass
            self.after(0, self._finish)

        threading.Thread(target=do_create, daemon=True).start()

    def _finish(self):
        self._checking_connection = False
        if self.on_add:
            self.on_add()
        self.destroy()


class SetupWizardWindow(ctk.CTkToplevel):
    """Standalone setup wizard window."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.title("Kindle to Anki - Setup Wizard")
        self.geometry("700x500")

        self.wizard_frame = SetupWizardFrame(self, on_back=self.destroy)
        self.wizard_frame.pack(fill="both", expand=True, padx=10, pady=10)


def main():
    """Run setup wizard as standalone window."""
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.withdraw()

    wizard = SetupWizardWindow()
    wizard.protocol("WM_DELETE_WINDOW", root.quit)
    wizard.mainloop()


if __name__ == "__main__":
    main()
