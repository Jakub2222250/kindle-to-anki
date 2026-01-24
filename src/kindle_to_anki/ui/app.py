import customtkinter as ctk
from kindle_to_anki.ui.setup_wizard import SetupWizardFrame


class KindleToAnkiApp(ctk.CTk):
    """Main application window for Kindle to Anki."""

    def __init__(self):
        super().__init__()

        self.title("Kindle to Anki")
        self.geometry("1050x700")

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.current_frame = None
        self._show_main_view()

    def _show_main_view(self):
        if self.current_frame:
            self.current_frame.destroy()

        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        self.current_frame = self.main_frame

        # Title label
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="Kindle to Anki",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(pady=(20, 10))

        # Subtitle
        self.subtitle_label = ctk.CTkLabel(
            self.main_frame,
            text="Convert Kindle vocabulary to Anki flashcards",
            font=ctk.CTkFont(size=14)
        )
        self.subtitle_label.pack(pady=(0, 30))

        # Buttons frame
        self.buttons_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.buttons_frame.pack(pady=20)

        # Setup Wizard button
        self.setup_btn = ctk.CTkButton(
            self.buttons_frame,
            text="Setup Wizard",
            width=200,
            height=40,
            command=self._on_setup_wizard
        )
        self.setup_btn.pack(pady=10)

        # Export button
        self.export_btn = ctk.CTkButton(
            self.buttons_frame,
            text="Export Vocabulary",
            width=200,
            height=40,
            command=self._on_export
        )
        self.export_btn.pack(pady=10)

        # Status label
        self.status_label = ctk.CTkLabel(
            self.main_frame,
            text="Ready",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="bottom", pady=10)

    def _on_setup_wizard(self):
        if self.current_frame:
            self.current_frame.destroy()

        self.wizard_frame = SetupWizardFrame(self, on_back=self._show_main_view)
        self.wizard_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.current_frame = self.wizard_frame

    def _on_export(self):
        self.status_label.configure(text="Export clicked - not yet implemented")


def main():
    app = KindleToAnkiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
