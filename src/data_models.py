from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Literal, Dict

@dataclass
class Jurisdiction:
    """Represents a legal jurisdiction with its own copyright rules."""
    name: str  # e.g., "United States", "European Union", "Japan"
    id: Optional[int] = None  # Database ID
    code: Optional[str] = None  # ISO country code or region code
    term_years_after_death: int = 70  # Default copyright term in years after author's death
    has_special_rules: bool = False  # Whether this jurisdiction has special case rules
    
    def __str__(self):
        return self.name

@dataclass
class Topic:
    """Represents a category of work (e.g., Movies, Music, Books)."""
    name: str  # e.g., "Movies", "Music", "Books"
    id: Optional[int] = None # Database ID

    def __str__(self):
        return self.name

@dataclass
class Author:
    """Represents an author of a creative work."""
    name: str
    id: Optional[int] = None # Database ID
    birth_date: Optional[date] = None
    death_date: Optional[date] = None
    nationality: Optional[str] = None
    bio: Optional[str] = None # Add the bio field here
    works: List['Work'] = field(default_factory=list, repr=False) # Avoid circular repr

    def __str__(self):
        life_span = ""
        if self.birth_date or self.death_date:
            birth = self.birth_date.year if self.birth_date else "?"
            death = self.death_date.year if self.death_date else "?"
            life_span = f" ({birth}-{death})"
        return f"{self.name}{life_span}"

@dataclass
class Work:
    """Represents a creative work."""
    title: str
    id: Optional[int] = None # Database ID
    authors: List[Author] = field(default_factory=list)
    topic: Optional[Topic] = None # Link to the work's category
    creation_date: Optional[date] = None # When the work was created
    publication_date: Optional[date] = None # Publication date (alias to first_publication_date)
    first_publication_date: Optional[date] = None # Important for some copyright calculations
    source_url: Optional[str] = None # Where the info was found
    scraped_timestamp: datetime = field(default_factory=datetime.utcnow)
    copyright_expiry_date: Optional[date] = None
    primary_jurisdiction: Optional[Jurisdiction] = None # Primary jurisdiction for copyright
    status: Literal['Copyrighted', 'Public Domain', 'Unknown'] = 'Unknown'
    status_by_jurisdiction: Dict[str, Literal['Copyrighted', 'Public Domain', 'Unknown']] = field(default_factory=dict)
    is_collaborative: bool = False # Whether the work has multiple authors
    original_language: Optional[str] = None # Original language of the work
    original_publisher: Optional[str] = None # Original publisher of the work
    description: Optional[str] = None # Brief description of the work

    def __post_init__(self):
        """Handle field synchronization after initialization."""
        # Sync publication_date and first_publication_date to use same value
        if self.publication_date is not None and self.first_publication_date is None:
            self.first_publication_date = self.publication_date
        elif self.first_publication_date is not None and self.publication_date is None:
            self.publication_date = self.first_publication_date

    def __str__(self):
        author_names = ', '.join(a.name for a in self.authors) if self.authors else "Unknown Author"
        topic_name = self.topic.name if self.topic else "Uncategorized"
        jurisdiction_info = f" in {self.primary_jurisdiction.name}" if self.primary_jurisdiction else ""
        return f"'{self.title}' ({topic_name}) by {author_names} [{self.status}{jurisdiction_info}]"

@dataclass
class CopyrightRule:
    """Represents a specific copyright rule or exception."""
    jurisdiction: Jurisdiction
    rule_type: str  # e.g., "anonymous_works", "corporate_works", "sound_recordings"
    term_years: int
    base_date_type: Literal['publication', 'creation', 'author_death', 'fixed_year'] = 'publication'
    description: str = ""
    
    def __str__(self):
        return f"{self.jurisdiction.name}: {self.description} ({self.term_years} years from {self.base_date_type})"
