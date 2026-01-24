import customtkinter as ctk


class KindleToAnkiApp(ctk.CTk):
    """Main application window for Kindle to Anki."""

    def __init__(self):
        super().__init__()

        self.title("Kindle to Anki")
        self.geometry("600x400")

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self._create_widgets()

    def _create_widgets(self):
        # Main container
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

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
        self.status_label.configure(text="Setup Wizard clicked - not yet implemented")

    def _on_export(self):
        self.status_label.configure(text="Export clicked - not yet implemented")


def main():
    app = KindleToAnkiApp()
    app.mainloop()


if __name__ == "__main__":
    main()
