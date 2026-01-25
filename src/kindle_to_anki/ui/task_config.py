import customtkinter as ctk
from typing import Callable
import copy

from kindle_to_anki.core.bootstrap import bootstrap_all
from kindle_to_anki.core.runtimes.runtime_registry import RuntimeRegistry
from kindle_to_anki.core.models.registry import ModelRegistry
from kindle_to_anki.core.prompts import list_prompts, get_default_prompt_id, get_lui_default_prompt_id

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

# Language restrictions for certain runtimes (runtime_id -> list of supported source languages)
RUNTIME_LANGUAGE_RESTRICTIONS = {
    "polish_ma_llm_hybrid_lui": ["pl"],
    "polish_local_translation": ["pl"],
}

TASK_ORDER = ["lui", "wsd", "translation", "hint", "cloze_scoring", "usage_level", "collocation"]


def get_runtimes_for_task(task: str, source_language_code: str = None) -> list:
    """Get available runtimes for a task, optionally filtered by language."""
    bootstrap_all()
    runtimes = RuntimeRegistry.find_by_task(task)

    if source_language_code:
        filtered = []
        for rt in runtimes:
            restrictions = RUNTIME_LANGUAGE_RESTRICTIONS.get(rt.id)
            if restrictions is None or source_language_code in restrictions:
                filtered.append(rt)
        return filtered
    return list(runtimes)


def get_models_for_runtime(runtime) -> list[str]:
    """Get available model IDs for a runtime based on its supported model families."""
    if not runtime.supported_model_families:
        return []

    bootstrap_all()
    models = []
    for model in ModelRegistry.list():
        if model.family in runtime.supported_model_families:
            models.append(model.id)
    return models


def get_prompts_for_task(task_key: str, source_language_code: str = None) -> list[str]:
    """Get available prompt IDs for a task, filtered by language compatibility."""
    prompts = list_prompts(task_key, source_language_code)
    return prompts if prompts else []


def get_default_prompt_for_task(task_key: str, source_language_code: str = None) -> str | None:
    """Get the default prompt ID for a task."""
    if task_key == "lui" and source_language_code:
        return get_lui_default_prompt_id(source_language_code)
    return get_default_prompt_id(task_key)


class TaskConfigRow(ctk.CTkFrame):
    """A single row for configuring one task."""

    def __init__(self, parent, task_key: str, task_settings: dict, 
                 source_language_code: str = None, on_change: Callable = None):
        super().__init__(parent, fg_color="transparent")
        self.task_key = task_key
        self.task_settings = task_settings
        self.source_language_code = source_language_code
        self.on_change = on_change
        self.metadata = TASK_METADATA.get(task_key, {})

        # Get available runtimes for this task
        self.available_runtimes = get_runtimes_for_task(task_key, source_language_code)
        self.runtime_map = {rt.id: rt for rt in self.available_runtimes}

        self._create_widgets()

    def _create_widgets(self):
        # Configure grid columns
        self.grid_columnconfigure(0, weight=0, minsize=30)   # Enable checkbox
        self.grid_columnconfigure(1, weight=1, minsize=160)  # Task name
        self.grid_columnconfigure(2, weight=0, minsize=180)  # Runtime dropdown
        self.grid_columnconfigure(3, weight=0, minsize=150)  # Model dropdown
        self.grid_columnconfigure(4, weight=0, minsize=140)  # Prompt dropdown
        self.grid_columnconfigure(5, weight=0, minsize=80)   # Batch size

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
            command=self._on_runtime_change
        )
        self.runtime_dropdown.grid(row=0, column=col, padx=5, sticky="w")

        col += 1

        # Model dropdown (will be updated based on runtime)
        self.model_var = ctk.StringVar(value=self.task_settings.get("model_id", ""))
        self.model_dropdown = ctk.CTkOptionMenu(
            self,
            values=["(none)"],
            variable=self.model_var,
            width=140,
            command=self._on_model_change
        )
        self.model_dropdown.grid(row=0, column=col, padx=5, sticky="w")

        col += 1

        # Prompt dropdown
        available_prompts = get_prompts_for_task(self.task_key, self.source_language_code)
        default_prompt = get_default_prompt_for_task(self.task_key, self.source_language_code)
        current_prompt = self.task_settings.get("prompt_id") or default_prompt or ""
        if available_prompts and current_prompt not in available_prompts:
            current_prompt = available_prompts[0] if available_prompts else ""

        self.prompt_var = ctk.StringVar(value=current_prompt)
        self.prompt_dropdown = ctk.CTkOptionMenu(
            self,
            values=available_prompts if available_prompts else ["(none)"],
            variable=self.prompt_var,
            width=130,
            command=self._on_prompt_change
        )
        self.prompt_dropdown.grid(row=0, column=col, padx=5, sticky="w")
        if not available_prompts:
            self.prompt_dropdown.configure(state="disabled")

        col += 1

        # Batch size
        self.batch_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.batch_frame.grid(row=0, column=col, padx=5, sticky="w")

        self.batch_label = ctk.CTkLabel(self.batch_frame, text="Batch:", font=ctk.CTkFont(size=11))
        self.batch_label.pack(side="left")
        self.batch_var = ctk.StringVar(value=str(self.task_settings.get("batch_size", 30)))
        self.batch_entry = ctk.CTkEntry(
            self.batch_frame,
            textvariable=self.batch_var,
            width=50
        )
        self.batch_entry.pack(side="left", padx=(3, 0))
        self.batch_var.trace_add("write", self._on_batch_change)

        # Update model options based on current runtime
        self._update_model_options()
        # Update visual state
        self._update_enabled_state()

    def _on_runtime_change(self, _=None):
        self._update_model_options()
        self._notify_change()

    def _update_model_options(self):
        """Update model dropdown and batch visibility based on selected runtime."""
        runtime_id = self.runtime_var.get()
        runtime = self.runtime_map.get(runtime_id)

        if not runtime:
            self._set_model_state(False, [])
            self._set_prompt_state(False)
            self._set_batch_state(False)
            return

        # Update model dropdown
        models = get_models_for_runtime(runtime)
        has_models = len(models) > 0
        self._set_model_state(has_models, models)

        # Update prompt dropdown - only enable if runtime uses models (LLM-based)
        has_prompts = has_models and len(get_prompts_for_task(self.task_key, self.source_language_code)) > 0
        self._set_prompt_state(has_prompts)

        # Update batch visibility
        has_batching = getattr(runtime, 'supports_batching', True)
        self._set_batch_state(has_batching)

    def _set_model_state(self, enabled: bool, models: list):
        """Enable/disable model dropdown and update options."""
        if enabled and models:
            self.model_dropdown.configure(state="normal", values=models)
            current = self.model_var.get()
            if current not in models:
                self.model_var.set(models[0])
        else:
            self.model_dropdown.configure(state="disabled", values=["(n/a)"])
            self.model_var.set("(n/a)")

    def _set_batch_state(self, enabled: bool):
        """Enable/disable batch size input."""
        state = "normal" if enabled else "disabled"
        self.batch_entry.configure(state=state)
        color = ("gray10", "gray90") if enabled else "gray"
        self.batch_label.configure(text_color=color)

    def _set_prompt_state(self, enabled: bool):
        """Enable/disable prompt dropdown."""
        if enabled:
            prompts = get_prompts_for_task(self.task_key, self.source_language_code)
            self.prompt_dropdown.configure(state="normal", values=prompts if prompts else ["(n/a)"])
            current = self.prompt_var.get()
            if current == "(n/a)" or (prompts and current not in prompts):
                default_prompt = get_default_prompt_for_task(self.task_key, self.source_language_code)
                self.prompt_var.set(default_prompt if default_prompt in prompts else (prompts[0] if prompts else "(n/a)"))
        else:
            self.prompt_dropdown.configure(state="disabled", values=["(n/a)"])
            self.prompt_var.set("(n/a)")

    def _on_enabled_change(self):
        self._update_enabled_state()
        self._notify_change()

    def _on_model_change(self, _=None):
        self._notify_change()

    def _on_prompt_change(self, _=None):
        self._notify_change()

    def _on_batch_change(self, *args):
        self._notify_change()

    def _update_enabled_state(self):
        enabled = self.enabled_var.get()

        if enabled:
            self.name_label.configure(text_color=("gray10", "gray90"))
            self.runtime_dropdown.configure(state="normal")
            # Re-apply model/batch/prompt state based on runtime
            self._update_model_options()
        else:
            self.name_label.configure(text_color="gray")
            self.runtime_dropdown.configure(state="disabled")
            self.model_dropdown.configure(state="disabled")
            self.prompt_dropdown.configure(state="disabled")
            self.batch_entry.configure(state="disabled")

    def _notify_change(self):
        if self.on_change:
            self.on_change()

    def get_settings(self) -> dict:
        """Get current settings for this task."""
        model_val = self.model_var.get()
        prompt_val = self.prompt_var.get()
        # Only save prompt_id if it differs from the default
        default_prompt = get_default_prompt_for_task(self.task_key, self.source_language_code)
        settings = {
            "runtime": self.runtime_var.get(),
            "model_id": model_val if model_val not in ("(n/a)", "(none)") else None,
            "batch_size": int(self.batch_var.get()) if self.batch_var.get().isdigit() else 30
        }
        # Only include prompt_id if non-default and not a placeholder
        if prompt_val and prompt_val not in ("(n/a)", "(none)", "") and prompt_val != default_prompt:
            settings["prompt_id"] = prompt_val
        if self.metadata.get("optional", False):
            settings["enabled"] = self.enabled_var.get()
        return settings


class TaskConfigPanel(ctk.CTkFrame):
    """Panel for configuring all tasks for a deck."""

    def __init__(self, parent, deck_config: dict, on_save: Callable = None, on_cancel: Callable = None):
        super().__init__(parent)
        self.deck_config = deck_config
        self.task_settings = copy.deepcopy(deck_config.get("task_settings", {}))
        self.source_language_code = deck_config.get("source_language_code")
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
        header_row.grid_columnconfigure(1, weight=1, minsize=160)
        header_row.grid_columnconfigure(2, weight=0, minsize=180)
        header_row.grid_columnconfigure(3, weight=0, minsize=150)
        header_row.grid_columnconfigure(4, weight=0, minsize=140)
        header_row.grid_columnconfigure(5, weight=0, minsize=80)

        ctk.CTkLabel(header_row, text="", width=20).grid(row=0, column=0)
        ctk.CTkLabel(header_row, text="Task", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, sticky="w", padx=5)
        ctk.CTkLabel(header_row, text="Runtime", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, sticky="w", padx=5)
        ctk.CTkLabel(header_row, text="Model", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, sticky="w", padx=5)
        ctk.CTkLabel(header_row, text="Prompt", font=ctk.CTkFont(weight="bold")).grid(row=0, column=4, sticky="w", padx=5)
        ctk.CTkLabel(header_row, text="Batch", font=ctk.CTkFont(weight="bold")).grid(row=0, column=5, sticky="w", padx=5)

        # Separator
        ctk.CTkFrame(self.tasks_scroll, height=2, fg_color="gray").pack(fill="x", pady=(0, 10))

        # Task rows
        for task_key in TASK_ORDER:
            task_settings = self.task_settings.get(task_key, {})
            row = TaskConfigRow(
                self.tasks_scroll,
                task_key,
                task_settings,
                source_language_code=self.source_language_code,
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
