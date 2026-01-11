"""Shared interactive prompting utilities."""


def prompt_yes_no(prompt: str, default: bool = True) -> bool:
    """Prompt user for yes/no."""
    hint = "[Y/n]" if default else "[y/N]"
    response = input(f"{prompt} {hint}: ").strip().lower()
    if not response:
        return default
    return response in ("y", "yes")


def prompt_int(prompt: str, default: int) -> int:
    """Prompt user for an integer."""
    response = input(f"{prompt} [{default}]: ").strip()
    if not response:
        return default
    try:
        return int(response)
    except ValueError:
        print(f"Invalid number, using default: {default}")
        return default


def prompt_choice_by_index(prompt: str, options: list, default: int = 1) -> int:
    """Prompt user to select from numbered options, returns 1-based index."""
    while True:
        response = input(f"{prompt} [default={default}]: ").strip()
        if not response:
            return default
        try:
            choice = int(response)
            if 1 <= choice <= len(options):
                return choice
        except ValueError:
            pass
        print(f"Please enter a number between 1 and {len(options)}")


def prompt_choice(prompt: str, options: list[str], default: str = None) -> str:
    """Prompt user to choose from a list of string options, returns the selected string."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        marker = " (default)" if opt == default else ""
        print(f"  {i}. {opt}{marker}")

    while True:
        choice = input("Enter choice (number or name): ").strip()
        if not choice and default:
            return default
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(options):
                return options[idx]
        elif choice in options:
            return choice
        print("Invalid choice, try again.")
