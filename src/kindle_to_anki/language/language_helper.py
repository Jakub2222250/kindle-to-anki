import pycountry


def get_language_name_in_english(language_code: str) -> str:
    """Get the English name of a language given its language code"""
    lang = pycountry.languages.get(alpha_2=language_code)
    if lang:
        return lang.name
    raise KeyError(f"Unknown language code: {language_code}")
