import customtkinter as ctk
from tkinter import messagebox
import threading
import json
from pathlib import Path

from kindle_to_anki.anki.anki_connect import AnkiConnect


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
            return json.load(f)
    return {"anki_decks": []}


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

    @classmethod
    def get_connection(cls) -> tuple[AnkiConnect | None, bool]:
        """Get or create AnkiConnect instance. Returns (instance, is_connected)."""
        if cls._anki_connect is None:
            try:
                # Create without auto-exit on failure
                cls._anki_connect = object.__new__(AnkiConnect)
                cls._anki_connect.anki_url = "http://localhost:8765"
                cls._anki_connect.note_type = "Polish Vocab Discovery"
                cls._is_connected = cls._anki_connect.is_reachable()
            except Exception:
                cls._is_connected = False
        return cls._anki_connect, cls._is_connected

    @classmethod
    def check_connection(cls) -> bool:
        """Check if Anki is reachable (refreshes connection status)."""
        if cls._anki_connect is None:
            cls.get_connection()
        else:
            cls._is_connected = cls._anki_connect.is_reachable()
        return cls._is_connected

    @classmethod
    def reset(cls):
        """Reset connection state."""
        cls._anki_connect = None
        cls._is_connected = None


class SetupWizardFrame(ctk.CTkFrame):
    """Setup wizard frame for deck management."""

    def __init__(self, parent, on_back=None):
        super().__init__(parent)
        self.on_back = on_back
        self._anki_connected = False
        self._checking_connection = False

        self._create_widgets()
        self._load_existing_decks()

    def _create_widgets(self):
        # Title (fixed at top)
        self.title_label = ctk.CTkLabel(
            self,
            text="Deck Setup",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(pady=(10, 10))

        # Scrollable container for main content
        self.scroll_container = ctk.CTkScrollableFrame(self)
        self.scroll_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Main content in two columns
        self.content_frame = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(1, weight=1)

        # Left column: Add new deck
        self._create_add_deck_panel()

        # Right column: Existing decks list
        self._create_decks_list_panel()

        # Bottom: Back button (fixed at bottom)
        self.back_btn = ctk.CTkButton(
            self,
            text="← Back",
            width=100,
            command=self._on_back
        )
        self.back_btn.pack(side="bottom", pady=10, anchor="w", padx=10)

    def _create_add_deck_panel(self):
        add_frame = ctk.CTkFrame(self.content_frame)
        add_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)

        ctk.CTkLabel(
            add_frame,
            text="Add New Deck",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(10, 15))

        # Language names for dropdown
        self.language_options = [f"{name} ({code})" for code, name in COMMON_LANGUAGES]
        self.language_codes = {f"{name} ({code})": code for code, name in COMMON_LANGUAGES}

        # Source language
        ctk.CTkLabel(add_frame, text="Source Language (learning):").pack(anchor="w", padx=15)
        self.source_lang_var = ctk.StringVar(value=self.language_options[6])  # Polish
        self.source_lang_dropdown = ctk.CTkComboBox(
            add_frame,
            values=self.language_options,
            variable=self.source_lang_var,
            width=250,
            command=self._on_language_change
        )
        self.source_lang_dropdown.pack(padx=15, pady=(0, 10))

        # Target language
        ctk.CTkLabel(add_frame, text="Target Language (native):").pack(anchor="w", padx=15)
        self.target_lang_var = ctk.StringVar(value=self.language_options[0])  # English
        self.target_lang_dropdown = ctk.CTkComboBox(
            add_frame,
            values=self.language_options,
            variable=self.target_lang_var,
            width=250,
            command=self._on_language_change
        )
        self.target_lang_dropdown.pack(padx=15, pady=(0, 10))

        # Parent deck name
        ctk.CTkLabel(add_frame, text="Parent Deck Name:").pack(anchor="w", padx=15)
        self.parent_deck_var = ctk.StringVar(value="Polish Vocab Discovery")
        self.parent_deck_entry = ctk.CTkEntry(
            add_frame,
            textvariable=self.parent_deck_var,
            width=250
        )
        self.parent_deck_entry.pack(padx=15, pady=(0, 10))

        # Auto-name import deck checkbox
        self.auto_import_var = ctk.BooleanVar(value=True)
        self.auto_import_checkbox = ctk.CTkCheckBox(
            add_frame,
            text="Auto-name import deck (Parent::Import)",
            variable=self.auto_import_var,
            command=self._on_auto_import_toggle
        )
        self.auto_import_checkbox.pack(anchor="w", padx=15, pady=(0, 5))

        # Import deck name (readonly by default when auto-naming)
        ctk.CTkLabel(add_frame, text="Import Deck Name:").pack(anchor="w", padx=15)
        self.import_deck_var = ctk.StringVar(value="Polish Vocab Discovery::Import")
        self.import_deck_entry = ctk.CTkEntry(
            add_frame,
            textvariable=self.import_deck_var,
            width=250,
            state="disabled"
        )
        self.import_deck_entry.pack(padx=15, pady=(0, 10))

        # Bind parent deck change to update import deck
        self.parent_deck_var.trace_add("write", self._on_parent_deck_change)

        # Add deck button
        self.add_deck_btn = ctk.CTkButton(
            add_frame,
            text="Add Deck",
            width=150,
            command=self._add_deck
        )
        self.add_deck_btn.pack(pady=15)

        # Create in Anki button
        self.create_anki_btn = ctk.CTkButton(
            add_frame,
            text="Create Decks in Anki",
            width=150,
            command=self._create_decks_in_anki
        )
        self.create_anki_btn.pack(pady=(0, 15))

        # Status label
        self.status_label = ctk.CTkLabel(
            add_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.status_label.pack(pady=(0, 10))

    def _create_decks_list_panel(self):
        list_frame = ctk.CTkFrame(self.content_frame)
        list_frame.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)

        ctk.CTkLabel(
            list_frame,
            text="Configured Decks",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(10, 15))

        # Scrollable frame for deck list
        self.decks_scroll = ctk.CTkScrollableFrame(list_frame, height=250)
        self.decks_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Remove selected button
        self.remove_btn = ctk.CTkButton(
            list_frame,
            text="Remove Selected",
            width=150,
            fg_color="darkred",
            hover_color="red",
            command=self._remove_selected_deck
        )
        self.remove_btn.pack(pady=(0, 15))

        self.deck_checkboxes = []

    def _on_language_change(self, _=None):
        source = self.language_codes.get(self.source_lang_var.get(), "")
        # Update suggested parent deck name
        for code, name in COMMON_LANGUAGES:
            if code == source:
                suggested_name = f"{name} Vocab Discovery"
                self.parent_deck_var.set(suggested_name)
                break

    def _on_parent_deck_change(self, *args):
        if self.auto_import_var.get():
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

        self._load_existing_decks()
        self.status_label.configure(text=f"Added: {parent_deck}", text_color="green")

    def _create_decks_in_anki(self):
        if self._checking_connection:
            return

        parent_deck = self.parent_deck_var.get().strip()
        import_deck = self.import_deck_var.get().strip()

        if not parent_deck:
            messagebox.showerror("Error", "Please enter a parent deck name.")
            return

        # Show loading state
        self._checking_connection = True
        self.create_anki_btn.configure(state="disabled")
        self.status_label.configure(text="⟳ Connecting to Anki...", text_color="gray")

        def check_and_create():
            # Reset cached connection to force fresh check
            AnkiConnectionManager.reset()
            anki, is_connected = AnkiConnectionManager.get_connection()

            if not is_connected:
                self.after(0, lambda: self._on_anki_connection_failed())
                return

            try:
                existing_decks = anki.get_deck_names()
                created = []
                already_exist = []

                for deck_name in [parent_deck, import_deck]:
                    if deck_name in existing_decks:
                        already_exist.append(deck_name)
                    else:
                        if anki.create_deck(deck_name):
                            created.append(deck_name)

                self.after(0, lambda: self._on_decks_created(created, already_exist))
            except Exception as e:
                self.after(0, lambda: self._on_anki_error(str(e)))

        thread = threading.Thread(target=check_and_create, daemon=True)
        thread.start()

    def _on_anki_connection_failed(self):
        self._checking_connection = False
        self.create_anki_btn.configure(state="normal")
        self.status_label.configure(text="", text_color="gray")
        messagebox.showerror("Error", "Cannot connect to Anki.\nMake sure Anki is running with AnkiConnect.")

    def _on_anki_error(self, error_msg: str):
        self._checking_connection = False
        self.create_anki_btn.configure(state="normal")
        self.status_label.configure(text=f"Error: {error_msg}", text_color="red")

    def _on_decks_created(self, created: list, already_exist: list):
        self._checking_connection = False
        self.create_anki_btn.configure(state="normal")

        msg_parts = []
        if created:
            msg_parts.append(f"Created: {', '.join(created)}")
        if already_exist:
            msg_parts.append(f"Already exist: {', '.join(already_exist)}")

        if msg_parts:
            self.status_label.configure(text="\n".join(msg_parts), text_color="green")
        else:
            self.status_label.configure(text="No decks created", text_color="orange")

    def _load_existing_decks(self):
        # Clear existing checkboxes
        for cb, var in self.deck_checkboxes:
            cb.destroy()
        self.deck_checkboxes.clear()

        config = load_config()
        decks = config.get("anki_decks", [])

        if not decks:
            no_decks_label = ctk.CTkLabel(
                self.decks_scroll,
                text="No decks configured",
                text_color="gray"
            )
            no_decks_label.pack(pady=20)
            self.deck_checkboxes.append((no_decks_label, None))
            return

        for deck in decks:
            var = ctk.BooleanVar(value=False)
            text = f"{deck['source_language_code']} → {deck['target_language_code']}\n{deck['parent_deck_name']}"
            cb = ctk.CTkCheckBox(
                self.decks_scroll,
                text=text,
                variable=var,
                font=ctk.CTkFont(size=12)
            )
            cb.pack(anchor="w", pady=5, padx=5)
            self.deck_checkboxes.append((cb, var))

    def _remove_selected_deck(self):
        config = load_config()
        decks = config.get("anki_decks", [])

        indices_to_remove = []
        for i, (cb, var) in enumerate(self.deck_checkboxes):
            if var and var.get():
                indices_to_remove.append(i)

        if not indices_to_remove:
            messagebox.showinfo("Info", "No decks selected.")
            return

        # Remove in reverse order to maintain indices
        for i in reversed(indices_to_remove):
            if i < len(decks):
                decks.pop(i)

        config["anki_decks"] = decks
        save_config(config)
        self._load_existing_decks()
        self.status_label.configure(text="Deck(s) removed", text_color="orange")

    def _on_back(self):
        if self.on_back:
            self.on_back()


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
