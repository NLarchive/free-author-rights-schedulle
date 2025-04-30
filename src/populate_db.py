"""
Script to populate the database with additional famous works.
Focus is on works that are already in the public domain or will enter it soon.
"""
import logging
import os
import sys
from datetime import date

# Add parent directory to path to ensure imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_models import Jurisdiction, Work, Author
from src import database
from src import scheduler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_jurisdictions():
    """Get all jurisdictions for referencing in the work data."""
    us_jurisdiction = database.get_jurisdiction_by_name("United States")
    uk_jurisdiction = database.get_jurisdiction_by_name("United Kingdom")
    eu_jurisdiction = database.get_jurisdiction_by_name("European Union")
    ca_jurisdiction = database.get_jurisdiction_by_name("Canada")
    jp_jurisdiction = database.get_jurisdiction_by_name("Japan")
    mx_jurisdiction = database.get_jurisdiction_by_name("Mexico")
    
    return {
        "US": us_jurisdiction,
        "UK": uk_jurisdiction,
        "EU": eu_jurisdiction,
        "CA": ca_jurisdiction,
        "JP": jp_jurisdiction,
        "MX": mx_jurisdiction
    }

def populate_literature():
    """Add famous literature works to the database."""
    logger.info("Adding famous literature works to the database...")
    
    jurisdictions = get_jurisdictions()
    
    # Collection of famous literary works
    famous_literature = [
        # Public domain or soon to be
        {
            "title": "The Adventures of Sherlock Holmes",
            "authors": [{"name": "Arthur Conan Doyle", "birth_date": "1859-05-22", "death_date": "1930-07-07", "nationality": "GB"}],
            "creation_date": "1892-10-14",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["UK"],
            "source_url": "https://www.gutenberg.org/ebooks/1661"
        },
        {
            "title": "The Picture of Dorian Gray",
            "authors": [{"name": "Oscar Wilde", "birth_date": "1854-10-16", "death_date": "1900-11-30", "nationality": "GB"}],
            "creation_date": "1890-07-01",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["UK"],
            "source_url": "https://www.gutenberg.org/ebooks/174"
        },
        {
            "title": "Moby-Dick",
            "authors": [{"name": "Herman Melville", "birth_date": "1819-08-01", "death_date": "1891-09-28", "nationality": "US"}],
            "creation_date": "1851-10-18",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://www.gutenberg.org/ebooks/2701"
        },
        {
            "title": "The Brothers Karamazov",
            "authors": [{"name": "Fyodor Dostoevsky", "birth_date": "1821-11-11", "death_date": "1881-02-09", "nationality": "EU"}],
            "creation_date": "1880-11-01",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://www.gutenberg.org/ebooks/28054"
        },
        {
            "title": "Ulysses",
            "authors": [{"name": "James Joyce", "birth_date": "1882-02-02", "death_date": "1941-01-13", "nationality": "GB"}],
            "creation_date": "1922-02-02",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://www.gutenberg.org/ebooks/4300"
        },
        {
            "title": "War and Peace",
            "authors": [{"name": "Leo Tolstoy", "birth_date": "1828-09-09", "death_date": "1910-11-20", "nationality": "EU"}],
            "creation_date": "1869-01-01",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://www.gutenberg.org/ebooks/2600"
        },
        {
            "title": "The Scarlet Letter",
            "authors": [{"name": "Nathaniel Hawthorne", "birth_date": "1804-07-04", "death_date": "1864-05-19", "nationality": "US"}],
            "creation_date": "1850-03-16",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://www.gutenberg.org/ebooks/33"
        },
        {
            "title": "Winnie-the-Pooh",
            "authors": [{"name": "A. A. Milne", "birth_date": "1882-01-18", "death_date": "1956-01-31", "nationality": "GB"}],
            "creation_date": "1926-10-14",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["UK"],
            "source_url": "https://en.wikipedia.org/wiki/Winnie-the-Pooh"
        },
        # Works nearing public domain (based on the current date in 2025)
        {
            "title": "The Hobbit",
            "authors": [{"name": "J. R. R. Tolkien", "birth_date": "1892-01-03", "death_date": "1973-09-02", "nationality": "GB"}],
            "creation_date": "1937-09-21",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["UK"],
            "source_url": "https://en.wikipedia.org/wiki/The_Hobbit"
        },
        {
            "title": "The Grapes of Wrath",
            "authors": [{"name": "John Steinbeck", "birth_date": "1902-02-27", "death_date": "1968-12-20", "nationality": "US"}],
            "creation_date": "1939-04-14",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://en.wikipedia.org/wiki/The_Grapes_of_Wrath"
        },
        {
            "title": "To the Lighthouse",
            "authors": [{"name": "Virginia Woolf", "birth_date": "1882-01-25", "death_date": "1941-03-28", "nationality": "GB"}],
            "creation_date": "1927-05-05",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["UK"],
            "source_url": "https://en.wikipedia.org/wiki/To_the_Lighthouse"
        }
    ]
    
    count = database.add_famous_works("Books", famous_literature)
    logger.info(f"Added {count} literature works to the database")
    return count

def populate_films():
    """Add famous films to the database."""
    logger.info("Adding famous films to the database...")
    
    jurisdictions = get_jurisdictions()
    
    # Collection of famous films
    famous_films = [
        # Public domain or soon to be
        {
            "title": "The Gold Rush",
            "authors": [{"name": "Charlie Chaplin", "birth_date": "1889-04-16", "death_date": "1977-12-25", "nationality": "GB"}],
            "creation_date": "1925-06-26",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://archive.org/details/CC_1925_01_01_TheGoldRush"
        },
        {
            "title": "The General",
            "authors": [
                {"name": "Buster Keaton", "birth_date": "1895-10-04", "death_date": "1966-02-01", "nationality": "US"},
                {"name": "Clyde Bruckman", "birth_date": "1894-09-20", "death_date": "1955-01-04", "nationality": "US"}
            ],
            "creation_date": "1926-12-31",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://archive.org/details/TheGeneral_798"
        },
        {
            "title": "The Cabinet of Dr. Caligari",
            "authors": [{"name": "Robert Wiene", "birth_date": "1873-04-27", "death_date": "1938-07-17", "nationality": "EU"}],
            "creation_date": "1920-02-26",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://archive.org/details/TheCabinetOfDr.Caligari1920"
        },
        {
            "title": "The Phantom of the Opera",
            "authors": [{"name": "Rupert Julian", "birth_date": "1879-01-25", "death_date": "1943-12-27", "nationality": "US"}],
            "creation_date": "1925-09-06",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://archive.org/details/ThePhantomOfTheOpera"
        },
        {
            "title": "Battleship Potemkin",
            "authors": [{"name": "Sergei Eisenstein", "birth_date": "1898-01-22", "death_date": "1948-02-11", "nationality": "EU"}],
            "creation_date": "1925-12-21",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://archive.org/details/BattleshipPotemkin_201504"
        },
        # Works nearing public domain (based on current date in 2025)
        {
            "title": "Gone with the Wind",
            "authors": [{"name": "Victor Fleming", "birth_date": "1889-02-23", "death_date": "1949-01-06", "nationality": "US"}],
            "creation_date": "1939-12-15",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://en.wikipedia.org/wiki/Gone_with_the_Wind_(film)"
        },
        {
            "title": "Citizen Kane",
            "authors": [{"name": "Orson Welles", "birth_date": "1915-05-06", "death_date": "1985-10-10", "nationality": "US"}],
            "creation_date": "1941-05-01",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://en.wikipedia.org/wiki/Citizen_Kane"
        },
        {
            "title": "Snow White and the Seven Dwarfs",
            "authors": [{"name": "Walt Disney", "birth_date": "1901-12-05", "death_date": "1966-12-15", "nationality": "US"}],
            "creation_date": "1937-12-21",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://en.wikipedia.org/wiki/Snow_White_and_the_Seven_Dwarfs_(1937_film)"
        }
    ]
    
    count = database.add_famous_works("Movies", famous_films)
    logger.info(f"Added {count} films to the database")
    return count

def populate_music():
    """Add famous music compositions to the database."""
    logger.info("Adding famous music compositions to the database...")
    
    jurisdictions = get_jurisdictions()
    
    # Collection of famous music compositions
    famous_music = [
        # Public domain or soon to be
        {
            "title": "The Four Seasons",
            "authors": [{"name": "Antonio Vivaldi", "birth_date": "1678-03-04", "death_date": "1741-07-28", "nationality": "EU"}],
            "creation_date": "1725-01-01",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://en.wikipedia.org/wiki/The_Four_Seasons_(Vivaldi)"
        },
        {
            "title": "Symphony No. 9",
            "authors": [{"name": "Ludwig van Beethoven", "birth_date": "1770-12-17", "death_date": "1827-03-26", "nationality": "EU"}],
            "creation_date": "1824-05-07",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://en.wikipedia.org/wiki/Symphony_No._9_(Beethoven)"
        },
        {
            "title": "Prélude à l'après-midi d'un faune",
            "authors": [{"name": "Claude Debussy", "birth_date": "1862-08-22", "death_date": "1918-03-25", "nationality": "EU"}],
            "creation_date": "1894-12-22",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://en.wikipedia.org/wiki/Pr%C3%A9lude_%C3%A0_l%27apr%C3%A8s-midi_d%27un_faune"
        },
        {
            "title": "Die Walküre",
            "authors": [{"name": "Richard Wagner", "birth_date": "1813-05-22", "death_date": "1883-02-13", "nationality": "EU"}],
            "creation_date": "1870-06-26",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://en.wikipedia.org/wiki/Die_Walk%C3%BCre"
        },
        {
            "title": "Gymnopédies",
            "authors": [{"name": "Erik Satie", "birth_date": "1866-05-17", "death_date": "1925-07-01", "nationality": "EU"}],
            "creation_date": "1888-01-01",
            "status": "Public Domain",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://en.wikipedia.org/wiki/Gymnop%C3%A9dies"
        },
        # Works nearing public domain
        {
            "title": "Porgy and Bess",
            "authors": [{"name": "George Gershwin", "birth_date": "1898-09-26", "death_date": "1937-07-11", "nationality": "US"}],
            "creation_date": "1935-10-10",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["US"],
            "source_url": "https://en.wikipedia.org/wiki/Porgy_and_Bess"
        },
        {
            "title": "Peter and the Wolf",
            "authors": [{"name": "Sergei Prokofiev", "birth_date": "1891-04-23", "death_date": "1953-03-05", "nationality": "EU"}],
            "creation_date": "1936-05-02",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://en.wikipedia.org/wiki/Peter_and_the_Wolf"
        },
        {
            "title": "Carmina Burana",
            "authors": [{"name": "Carl Orff", "birth_date": "1895-07-10", "death_date": "1982-03-29", "nationality": "EU"}],
            "creation_date": "1937-06-08",
            "status": "Copyrighted",
            "primary_jurisdiction": jurisdictions["EU"],
            "source_url": "https://en.wikipedia.org/wiki/Carmina_Burana_(Orff)"
        }
    ]
    
    count = database.add_famous_works("Music", famous_music)
    logger.info(f"Added {count} music compositions to the database")
    return count

def main():
    """Main entry point for populating the database."""
    try:
        # Check if database has already been initialized
        logger.info("Starting database population...")
        current_works = database.get_all_works()
        
        # Add works
        books_added = populate_literature()
        movies_added = populate_films()
        music_added = populate_music()
        
        logger.info(f"Successfully added {books_added} books, {movies_added} movies, and {music_added} music compositions")
        logger.info("Database population complete!")
        
    except Exception as e:
        logger.error(f"Error during database population: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())