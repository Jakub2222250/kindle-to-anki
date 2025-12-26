from .providers.vocab_kindle import KindleVocabProvider


def get_vocab_provider(provider_type='kindle'):
    """Get vocab provider instance based on type"""
    if provider_type == 'kindle':
        return KindleVocabProvider()
    else:
        raise ValueError(f"Unsupported vocab provider type: {provider_type}")


def get_vocab_db():
    """Get vocab database using default provider"""
    provider = get_vocab_provider()
    return provider.get_vocab_db()


def get_latest_vocab_data(db_path, metadata):
    """Get latest vocab data using default provider"""
    provider = get_vocab_provider()
    return provider.get_latest_vocab_data(db_path, metadata)
