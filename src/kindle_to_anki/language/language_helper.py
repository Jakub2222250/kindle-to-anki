def get_language_name_in_english(language_code: str) -> str:
    """Get the English name of a language given its language code"""
    language_names = {
        'en': 'English',
        'pl': 'Polish',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'ru': 'Russian',
        'zh': 'Chinese',
        'ja': 'Japanese',
        'ko': 'Korean',
        # Add more language codes and names as needed
    }
    return language_names[language_code]
