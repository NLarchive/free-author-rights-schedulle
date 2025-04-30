"""Templates for LLM-based data generation."""

AUTHOR_TEMPLATE = {
    "name": "Full Name",
    "birth_date": "YYYY-MM-DD",  # ISO format date or None if unknown
    "death_date": "YYYY-MM-DD",  # ISO format date or None if unknown
    "nationality": "Country of citizenship",
    "bio": "Brief biography (1-3 sentences)",
    "notable_works": ["Work Title 1", "Work Title 2"]  # List of notable works by title
}

WORK_TEMPLATE = {
    "title": "Full Title",
    "authors": ["Author Full Name 1", "Author Full Name 2"],  # List of author names
    "creation_date": "YYYY-MM-DD",  # ISO format date or None if only year is known
    "publication_date": "YYYY-MM-DD",  # ISO format date of first publication
    "topic": "Primary Topic/Genre",  # Single topic/genre
    "secondary_topics": ["Topic 1", "Topic 2"],  # Additional topics/genres
    "description": "Brief description (2-4 sentences)",
    "original_language": "Language of original publication",
    "is_collaborative": False,  # True if multiple authors contributed
    "original_publisher": "Name of first publisher",
    "source_url": "URL to reliable source about this work (if available)"
}

# Example index structure that will be maintained
INDEX_TEMPLATE = {
    "authors": {
        "Author Name": {
            "id": 1,
            "works": ["Work Title 1", "Work Title 2"]
        }
    },
    "works": {
        "Work Title": {
            "id": 1,
            "authors": ["Author Name 1"]
        }
    },
    "topics": {
        "Topic Name": {
            "id": 1,
            "work_count": 5
        }
    }
}