from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class LanguagePair:
    """Represents a language pair with source and target languages."""
    source: str
    target: str
    
    def __str__(self) -> str:
        return f"{self.source}-{self.target}"


class Provider(ABC):
    """
    Generic base class for all providers in the kindle-to-anki system.
    
    This class defines the common interface and properties that all providers
    (WSD, translation, lexical unit identification, etc.) should implement.
    """
    
    def __init__(
        self,
        provider_id: str,
        name: str,
        description: str,
        limited_language_pair_support: Optional[List[LanguagePair]] = None
    ):
        """
        Initialize the provider with basic metadata.
        
        Args:
            provider_id: Unique identifier for the provider
            name: Human-readable name of the provider
            description: Description of what the provider does
            limited_language_pair_support: List of supported language pairs, None means supports all
        """
        self._id = provider_id
        self._name = name
        self._description = description
        self._limited_language_pair_support = limited_language_pair_support or []
    
    @property
    def id(self) -> str:
        """Get the unique identifier of the provider."""
        return self._id
    
    @property
    def name(self) -> str:
        """Get the human-readable name of the provider."""
        return self._name
    
    @property
    def description(self) -> str:
        """Get the description of the provider."""
        return self._description
    
    @property
    def limited_language_pair_support(self) -> List[LanguagePair]:
        """Get the list of supported language pairs."""
        return self._limited_language_pair_support
    
    def supports_language_pair(self, source_language: str, target_language: str) -> bool:
        """
        Check if the provider supports a specific language pair.
        
        Args:
            source_language: Source language code
            target_language: Target language code
            
        Returns:
            True if the language pair is supported, False otherwise.
            If no language pairs are specified, returns True (supports all).
        """
        if not self._limited_language_pair_support:
            # Empty list means supports all language pairs
            return True
        
        return any(
            pair.source == source_language and pair.target == target_language
            for pair in self._limited_language_pair_support
        )
    
    def get_supported_language_pairs(self) -> List[str]:
        """
        Get a list of supported language pairs as strings.
        
        Returns:
            List of language pair strings in format "source-target"
        """
        return [str(pair) for pair in self._limited_language_pair_support]
    
    def add_limited_language_pair_support(self, source_language: str, target_language: str) -> None:
        """
        Add support for a new language pair.
        
        Args:
            source_language: Source language code
            target_language: Target language code
        """
        new_pair = LanguagePair(source_language, target_language)
        if new_pair not in self._limited_language_pair_support:
            self._limited_language_pair_support.append(new_pair)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the provider to a dictionary representation.
        
        Returns:
            Dictionary containing provider metadata
        """
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'limited_language_pair_support': self.get_supported_language_pairs()
        }
    
    def __repr__(self) -> str:
        """String representation of the provider."""
        return f"{self.__class__.__name__}(id='{self.id}', name='{self.name}')"
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"{self.name} ({self.id})"
    
    @abstractmethod
    def process(self, *args, **kwargs) -> Any:
        """
        Abstract method that each provider must implement.
        
        This method should contain the main processing logic for the provider.
        The signature and return type will vary based on the specific provider type.
        """
        pass
