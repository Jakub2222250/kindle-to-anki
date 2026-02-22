import customtkinter as ctk
import threading

from kindle_to_anki.anki.anki_connect import AnkiConnect
from kindle_to_anki.anki.constants import NOTE_TYPE_NAME
from kindle_to_anki.configuration.config_manager import ConfigManager
from kindle_to_anki.ui.setup_wizard import AnkiConnectionManager


class ScheduleView(ctk.CTkFrame):
    """View for scheduling cards from Import into the Ready deck."""

    def __init__(self, parent, on_back=None):
        super().__init__(parent)
        self.on_back = on_back
        self._working = False

        self._load_decks()
        self._create_widgets()

    def _load_decks(self):
        """Load deck configurations."""
        try:
            cm = ConfigManager()
            self._decks = list(cm.get_anki_decks_by_source_language().values())
        except Exception:
            self._decks = []

    def _create_widgets(self):
        # Top bar
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=10, pady=(10, 5))

        ctk.CTkButton(top_bar, text="← Back", width=80, command=self._on_back).pack(side="left")
        ctk.CTkLabel(top_bar, text="Schedule Cards", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=(15, 0))

        # Content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=10)

        # Deck selector
        ctk.CTkLabel(content, text="Deck:", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(0, 3))

        deck_options = []
        for d in self._decks:
            deck_options.append(f"{d.parent_deck_name} ({d.source_language_code} → {d.target_language_code})")

        self.deck_var = ctk.StringVar(value=deck_options[0] if deck_options else "")
        self.deck_selector = ctk.CTkComboBox(content, values=deck_options, variable=self.deck_var, width=400, state="readonly")
        self.deck_selector.pack(anchor="w", pady=(0, 15))

        # Settings row
        settings_frame = ctk.CTkFrame(content, fg_color="transparent")
        settings_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(settings_frame, text="Usage level threshold:").pack(side="left", padx=(0, 5))
        self.threshold_var = ctk.StringVar(value="3")
        self.threshold_entry = ctk.CTkComboBox(
            settings_frame, values=["1", "2", "3", "4", "5"],
            variable=self.threshold_var, width=60, state="readonly"
        )
        self.threshold_entry.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(settings_frame, text="Note limit (at/below threshold):").pack(side="left", padx=(0, 5))
        self.limit_var = ctk.StringVar(value="20")
        self.limit_entry = ctk.CTkEntry(settings_frame, textvariable=self.limit_var, width=70)
        self.limit_entry.pack(side="left")

        # Info text
        info = ctk.CTkLabel(
            content,
            text=(
                "Cards with usage level ABOVE the threshold are always moved to Ready (no limit).\n"
                "Cards AT or BELOW the threshold are moved up to the limit, prioritized by highest usage level, then oldest first.\n"
                "Only unsuspended cards not already in the Ready deck are considered."
            ),
            font=ctk.CTkFont(size=11),
            text_color="gray",
            wraplength=650,
            justify="left"
        )
        info.pack(anchor="w", pady=(0, 15))

        # Buttons
        btn_frame = ctk.CTkFrame(content, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0, 10))

        self.preview_btn = ctk.CTkButton(btn_frame, text="Preview", width=120, command=self._preview)
        self.preview_btn.pack(side="left", padx=(0, 10))

        self.schedule_btn = ctk.CTkButton(btn_frame, text="Schedule Cards", width=150, command=self._schedule)
        self.schedule_btn.pack(side="left")

        # Status
        self.status_label = ctk.CTkLabel(content, text="", font=ctk.CTkFont(size=12), text_color="gray", wraplength=650, justify="left")
        self.status_label.pack(anchor="w", pady=(10, 5))

        # Results text
        self.results_text = ctk.CTkTextbox(content, height=300, state="disabled", font=ctk.CTkFont(family="Consolas", size=12))
        self.results_text.pack(fill="both", expand=True, pady=(5, 0))

    def _get_selected_deck(self):
        idx = 0
        sel = self.deck_var.get()
        for i, d in enumerate(self._decks):
            label = f"{d.parent_deck_name} ({d.source_language_code} → {d.target_language_code})"
            if label == sel:
                idx = i
                break
        return self._decks[idx] if self._decks else None

    def _get_params(self):
        try:
            threshold = int(self.threshold_var.get())
        except ValueError:
            threshold = 3
        try:
            limit = int(self.limit_var.get())
        except ValueError:
            limit = 20
        return threshold, limit

    def _set_working(self, working: bool):
        self._working = working
        state = "disabled" if working else "normal"
        self.preview_btn.configure(state=state)
        self.schedule_btn.configure(state=state)

    def _log(self, text: str):
        self.results_text.configure(state="normal")
        self.results_text.insert("end", text + "\n")
        self.results_text.configure(state="disabled")
        self.results_text.see("end")

    def _clear_log(self):
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.configure(state="disabled")

    def _fetch_candidates(self, anki: AnkiConnect, deck, threshold: int, limit: int):
        """Fetch and sort candidate notes. Returns (above_threshold, limited_below, total_notes)."""
        ready_deck = deck.ready_deck_name
        parent_deck = deck.parent_deck_name

        # Find unsuspended cards in the parent deck but NOT in the ready deck
        query = f'"deck:{parent_deck}" -"deck:{ready_deck}" -is:suspended "note:{NOTE_TYPE_NAME}"'
        card_ids = anki.find_cards(query)

        if not card_ids:
            return [], [], 0

        cards_info = anki.get_cards_info(card_ids)

        # Deduplicate cards into notes (a note can have multiple cards)
        notes = {}  # noteId -> note entry
        for card in cards_info:
            note_id = card.get("note")
            if note_id in notes:
                notes[note_id]["card_ids"].append(card["cardId"])
                continue

            fields = card.get("fields", {})
            usage_str = fields.get("Usage_Level", {}).get("value", "").strip()

            try:
                usage_level = int(usage_str)
            except (ValueError, TypeError):
                usage_level = 0

            # Note ID in Anki is epoch milliseconds — use as creation time
            from datetime import datetime
            try:
                created = datetime.fromtimestamp(note_id / 1000).strftime("%Y-%m-%d %H:%M")
            except Exception:
                created = ""

            notes[note_id] = {
                "note_id": note_id,
                "card_ids": [card["cardId"]],
                "expression": fields.get("Expression", {}).get("value", "").strip(),
                "usage_level": usage_level,
                "created": created,
            }

        # Split into above/at-or-below threshold
        above = []
        at_or_below = []
        for entry in notes.values():
            if entry["usage_level"] > threshold:
                above.append(entry)
            else:
                at_or_below.append(entry)

        # Sort at_or_below: highest usage_level first, then oldest created first
        at_or_below.sort(key=lambda n: (-n["usage_level"], n["note_id"]))
        limited = at_or_below[:limit]

        return above, limited, len(notes)

    def _preview(self):
        if self._working or not self._decks:
            return

        deck = self._get_selected_deck()
        if not deck:
            return

        threshold, limit = self._get_params()
        self._set_working(True)
        self._clear_log()
        self.status_label.configure(text="⟳ Previewing...", text_color="gray")

        def do_preview():
            try:
                AnkiConnectionManager.reset()
                anki, connected = AnkiConnectionManager.get_connection()
                if not connected:
                    self.after(0, lambda: self._on_preview_done(None, None, 0, "Cannot connect to AnkiConnect"))
                    return

                above, limited, total = self._fetch_candidates(anki, deck, threshold, limit)
                self.after(0, lambda: self._on_preview_done(above, limited, total, None))
            except Exception as e:
                self.after(0, lambda: self._on_preview_done(None, None, 0, str(e)))

        threading.Thread(target=do_preview, daemon=True).start()

    def _on_preview_done(self, above, limited, total, error):
        self._set_working(False)
        if error:
            self.status_label.configure(text=f"✗ {error}", text_color="red")
            return

        to_move = len(above) + len(limited)
        self.status_label.configure(
            text=f"Found {total} candidate notes. Will move {to_move} to Ready ({len(above)} above threshold, {len(limited)} at/below).",
            text_color="green"
        )

        if above:
            self._log(f"--- Above threshold ({len(above)} notes, all moved) ---")
            col = max(len(n['expression']) for n in above) + 4
            for n in above:
                self._log(f"  [{n['usage_level']}] {n['expression']:<{col}}")

        if limited:
            self._log(f"\n--- At/below threshold ({len(limited)}/{self.limit_var.get()} limit) ---")
            col = max(len(n['expression']) for n in limited) + 4
            for n in limited:
                self._log(f"  [{n['usage_level']}] {n['expression']:<{col}} (created: {n['created']})")

        if not above and not limited:
            self._log("No notes to schedule.")

    def _schedule(self):
        if self._working or not self._decks:
            return

        deck = self._get_selected_deck()
        if not deck:
            return

        threshold, limit = self._get_params()
        self._set_working(True)
        self._clear_log()
        self.status_label.configure(text="⟳ Scheduling cards...", text_color="gray")

        def do_schedule():
            try:
                AnkiConnectionManager.reset()
                anki, connected = AnkiConnectionManager.get_connection()
                if not connected:
                    self.after(0, lambda: self._on_schedule_done(0, "Cannot connect to AnkiConnect"))
                    return

                above, limited, total = self._fetch_candidates(anki, deck, threshold, limit)
                to_move_ids = []
                for n in above + limited:
                    to_move_ids.extend(n["card_ids"])

                if to_move_ids:
                    anki.change_deck(to_move_ids, deck.ready_deck_name)

                note_count = len(above) + len(limited)
                self.after(0, lambda: self._on_schedule_done(note_count, None))
            except Exception as e:
                self.after(0, lambda: self._on_schedule_done(0, str(e)))

        threading.Thread(target=do_schedule, daemon=True).start()

    def _on_schedule_done(self, count, error):
        self._set_working(False)
        if error:
            self.status_label.configure(text=f"✗ {error}", text_color="red")
            return

        self.status_label.configure(text=f"✓ Moved {count} notes to Ready.", text_color="green")
        self._log(f"Moved {count} notes to Ready deck.")

    def _on_back(self):
        if self.on_back:
            self.on_back()
