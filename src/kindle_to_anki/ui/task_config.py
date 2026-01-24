import customtkinter as ctk
from typing import Callable
import copy

# Task metadata: display names, descriptions, and whether they're optional
TASK_METADATA = {
    "lui": {
        "name": "Lexical Unit Identification",
        "description": "Identifies the core lexical unit from context",
        "optional": False
    },
    "wsd": {
        "name": "Word Sense Disambiguation",
        "description": "Determines the correct meaning in context",
        "optional": False
    },
    "translation": {
        "name": "Translation",
        "description": "Translates the expression to target language",
        "optional": False
    },
    "hint": {
        "name": "Hint Generation",
        "description": "Creates hints for flashcard testing",
        "optional": True
    },
    "cloze_scoring": {
        "name": "Cloze Scoring",
        "description": "Scores suitability for cloze deletion",
        "optional": True
    },
    "usage_level": {
        "name": "Usage Level",
        "description": "Estimates frequency/difficulty level",
        "optional": True
    },
    "collocation": {
        "name": "Collocation",
        "description": "Generates common word combinations",
        "optional": True
    }
}

# Available models (simplified list - in production would come from ModelRegistry)
AVAILABLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gpt-5.1",
    "gpt-5-mini",
]

TASK_ORDER = ["lui", "wsd", "translation", "hint", "cloze_scoring", "usage_level", "collocation"]


class TaskConfigRow(ctk.CTkFrame):
    """A single row for configuring one task."""

    def __init__(self, parent, task_key: str, task_settings: dict, on_change: Callable = None):
        super().__init__(parent, fg_color="transparent")
        self.task_key = task_key
        self.task_settings = task_settings
        self.on_change = on_change
        self.metadata = TASK_METADATA.get(task_key, {})

        self._create_widgets()

    def _create_widgets(self):
        # Configure grid
        self.grid_columnconfigure(0, weight=0, minsize=30)   # Enable checkbox
        self.grid_columnconfigure(1, weight=1, minsize=180)  # Task name
        self.grid_columnconfigure(2, weight=0, minsize=160)  # Model dropdown
        self.grid_columnconfigure(3, weight=0, minsize=80)   # Batch size

        col = 0

        # Enable checkbox (only for optional tasks)
        if self.metadata.get("optional", False):
            self.enabled_var = ctk.BooleanVar(value=self.task_settings.get("enabled", True))
            self.enabled_cb = ctk.CTkCheckBox(
                self,
                text="",
                variable=self.enabled_var,
                width=20,
                command=self._on_enabled_change
            )
            self.enabled_cb.grid(row=0, column=col, padx=(5, 0), sticky="w")
        else:
            self.enabled_var = ctk.BooleanVar(value=True)
            # Placeholder for alignment
            ctk.CTkLabel(self, text="", width=20).grid(row=0, column=col, padx=(5, 0))

        col += 1

        # Task name and description
        name_frame = ctk.CTkFrame(self, fg_color="transparent")
        name_frame.grid(row=0, column=col, padx=5, sticky="w")

        self.name_label = ctk.CTkLabel(
            name_frame,
            text=self.metadata.get("name", self.task_key),
            font=ctk.CTkFont(size=13, weight="bold")
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

        # Model dropdown (readonly to prevent custom entries)
        current_model = self.task_settings.get("model_id", AVAILABLE_MODELS[0])
        self.model_var = ctk.StringVar(value=current_model)
        self.model_dropdown = ctk.CTkOptionMenu(
            self,
            values=AVAILABLE_MODELS,
            variable=self.model_var,
            width=150,
            command=self._on_model_change
        )
        self.model_dropdown.grid(row=0, column=col, padx=5, sticky="w")

        col += 1

        # Batch size
        batch_frame = ctk.CTkFrame(self, fg_color="transparent")
        batch_frame.grid(row=0, column=col, padx=5, sticky="w")

        ctk.CTkLabel(batch_frame, text="Batch:", font=ctk.CTkFont(size=11)).pack(side="left")
        self.batch_var = ctk.StringVar(value=str(self.task_settings.get("batch_size", 30)))
        self.batch_entry = ctk.CTkEntry(
            batch_frame,
            textvariable=self.batch_var,
            width=50
        )
        self.batch_entry.pack(side="left", padx=(3, 0))
        self.batch_var.trace_add("write", self._on_batch_change)

        # Update visual state
        self._update_enabled_state()

    def _on_enabled_change(self):
        self._update_enabled_state()
        self._notify_change()

    def _on_model_change(self, _=None):
        self._notify_change()

    def _on_batch_change(self, *args):
        self._notify_change()

    def _update_enabled_state(self):
        enabled = self.enabled_var.get()
        state = "normal" if enabled else "disabled"

        self.model_dropdown.configure(state=state)
        self.batch_entry.configure(state=state)
        # Use default color when enabled, gray when disabled
        if enabled:
            self.name_label.configure(text_color=("gray10", "gray90"))
        else:
            self.name_label.configure(text_color="gray")

    def _notify_change(self):
        if self.on_change:
            self.on_change()

    def get_settings(self) -> dict:
        """Get current settings for this task."""
        settings = {
            "runtime": f"chat_completion_{self.task_key}",
            "model_id": self.model_var.get(),
            "batch_size": int(self.batch_var.get()) if self.batch_var.get().isdigit() else 30
        }
        if self.metadata.get("optional", False):
            settings["enabled"] = self.enabled_var.get()
        return settings


class TaskConfigPanel(ctk.CTkFrame):
    """Panel for configuring all tasks for a deck."""

    def __init__(self, parent, deck_config: dict, on_save: Callable = None, on_cancel: Callable = None):
        super().__init__(parent)
        self.deck_config = deck_config
        self.task_settings = copy.deepcopy(deck_config.get("task_settings", {}))
        self.on_save = on_save
        self.on_cancel = on_cancel
        self.task_rows = {}

        self._create_widgets()

    def _create_widgets(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        source = self.deck_config.get("source_language_code", "??")
        target = self.deck_config.get("target_language_code", "??")
        deck_name = self.deck_config.get("parent_deck_name", "Unknown Deck")

        ctk.CTkLabel(
            header_frame,
            text=f"Task Configuration",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            header_frame,
            text=f"{deck_name} ({source} → {target})",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        ).pack(anchor="w")

        # Scrollable task list
        self.tasks_scroll = ctk.CTkScrollableFrame(self)
        self.tasks_scroll.pack(fill="both", expand=True, padx=10, pady=10)

        # Column headers
        header_row = ctk.CTkFrame(self.tasks_scroll, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, 10))
        header_row.grid_columnconfigure(0, weight=0, minsize=30)
        header_row.grid_columnconfigure(1, weight=1, minsize=180)
        header_row.grid_columnconfigure(2, weight=0, minsize=160)
        header_row.grid_columnconfigure(3, weight=0, minsize=80)

        ctk.CTkLabel(header_row, text="", width=20).grid(row=0, column=0)
        ctk.CTkLabel(header_row, text="Task", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, sticky="w", padx=5)
        ctk.CTkLabel(header_row, text="Model", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, sticky="w", padx=5)
        ctk.CTkLabel(header_row, text="Batch", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, sticky="w", padx=5)

        # Separator
        ctk.CTkFrame(self.tasks_scroll, height=2, fg_color="gray").pack(fill="x", pady=(0, 10))

        # Task rows
        for task_key in TASK_ORDER:
            task_settings = self.task_settings.get(task_key, {})
            row = TaskConfigRow(
                self.tasks_scroll,
                task_key,
                task_settings,
                on_change=self._on_task_change
            )
            row.pack(fill="x", pady=5)
            self.task_rows[task_key] = row

        # Bottom buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=15)

        self.cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            width=100,
            fg_color="gray",
            command=self._on_cancel
        )
        self.cancel_btn.pack(side="left")

        self.save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            width=100,
            command=self._on_save
        )
        self.save_btn.pack(side="right")

    def _on_task_change(self):
        # Could add validation or preview here
        pass

    def _on_save(self):
        # Collect all task settings
        new_settings = {}
        for task_key, row in self.task_rows.items():
            new_settings[task_key] = row.get_settings()

        if self.on_save:
            self.on_save(new_settings)

    def _on_cancel(self):
        if self.on_cancel:
            self.on_cancel()

    def get_all_settings(self) -> dict:
        """Get all current task settings."""
        return {task_key: row.get_settings() for task_key, row in self.task_rows.items()}
