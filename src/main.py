import logging
import time
import os
from datetime import date, datetime
from typing import List
from .config import LOG_FILE, LOG_LEVEL, REQUEST_DELAY_SECONDS, TARGET_URLS, DATA_DIR
from .scraper.spiders import example_spider # Import specific spiders
from . import database
from . import scheduler
from .data_models import Topic, Work, Author, Jurisdiction, CopyrightRule
from .date_provider import get_current_date

# --- Logging Setup ---
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # Also print logs to console
    ]
)
logger = logging.getLogger(__name__)

# Predefined topics for the system
PREDEFINED_TOPICS = ["Books", "Movies", "Music"]

def initialize_system():
    """Initialize the database and add predefined topics and jurisdictions."""
    logger.info("Initializing system...")
    
    # Ensure data directory exists
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Initialize database tables
    database.init_db()
    
    # Add predefined topics
    for topic_name in PREDEFINED_TOPICS:
        topic = database.add_topic(topic_name)
        if topic:
            logger.info(f"Added/verified topic: {topic.name}")
        else:
            logger.warning(f"Failed to add topic: {topic_name}")
    
    # Initialize jurisdictions and copyright rules
    database.initialize_default_jurisdictions()
    
    logger.info("System initialized.")

# --- Main Execution ---
def run_scraper():
    """Runs the web scraping process."""
    logger.info("Starting scraper...")
    
    # --- Instantiate and run spiders ---
    # This is a basic example; a more robust system might use Scrapy or similar
    scraped_count = 0
    for url in TARGET_URLS:
        try:
            # In a real scenario, you'd select the appropriate spider based on the URL
            # For now, we just use the example spider if the URL matches its domain
            if "example.com" in url: # Replace with actual domain check
                 logger.info(f"Scraping URL: {url} with example_spider")
                 works = example_spider.scrape(url) # Assuming spider has a 'scrape' method
                 for work in works:
                     # Assign a topic (in a real system, the spider might determine this)
                     # This is just a placeholder example
                     if "books" in url.lower():
                         topic = database.get_topic_by_name("Books")
                     elif "movies" in url.lower():
                         topic = database.get_topic_by_name("Movies")
                     elif "music" in url.lower():
                         topic = database.get_topic_by_name("Music")
                     else:
                         topic = database.get_topic_by_name("Books")  # Default to Books
                     
                     if topic:
                         work.topic = topic
                     
                     # Update work with international copyright status
                     work = scheduler.update_work_status(work)
                     
                     # Save to database
                     saved_work = database.save_work(work)
                     if saved_work:
                         scraped_count += 1
                         logger.info(f"Saved work: {saved_work.title} (Status: {saved_work.status})")
                     else:
                         logger.warning(f"Failed to save work: {work.title}")
                 
                 time.sleep(REQUEST_DELAY_SECONDS) # Be polite
            else:
                 logger.warning(f"No specific spider found for URL: {url}. Skipping.")

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}", exc_info=True) # Log traceback

    logger.info(f"Scraping finished. Found {scraped_count} potential works.")

def add_sample_data():
    """
    Adds sample data for popular works in Books, Movies, and Music.
    This helps bootstrap the database with some initial data.
    """
    logger.info("Adding sample data for popular works...")
    
    # Get US jurisdiction for primary jurisdiction
    us_jurisdiction = database.get_jurisdiction_by_name("United States")
    uk_jurisdiction = database.get_jurisdiction_by_name("United Kingdom")
    eu_jurisdiction = database.get_jurisdiction_by_name("European Union")
    
    # --- Add famous books ---
    famous_books = [
        {
            "title": "The Great Gatsby",
            "authors": [{"name": "F. Scott Fitzgerald", "birth_date": "1896-09-24", "death_date": "1940-12-21", "nationality": "US"}],
            "creation_date": "1925-04-10",
            "status": "Copyrighted",
            "primary_jurisdiction": us_jurisdiction
        },
        {
            "title": "Dracula",
            "authors": [{"name": "Bram Stoker", "birth_date": "1847-11-08", "death_date": "1912-04-20", "nationality": "GB"}],
            "creation_date": "1897-05-26",
            "status": "Public Domain",
            "primary_jurisdiction": uk_jurisdiction
        },
        {
            "title": "Pride and Prejudice",
            "authors": [{"name": "Jane Austen", "birth_date": "1775-12-16", "death_date": "1817-07-18", "nationality": "GB"}],
            "creation_date": "1813-01-28",
            "status": "Public Domain",
            "primary_jurisdiction": uk_jurisdiction
        },
        {
            "title": "1984",
            "authors": [{"name": "George Orwell", "birth_date": "1903-06-25", "death_date": "1950-01-21", "nationality": "GB"}],
            "creation_date": "1949-06-08",
            "status": "Copyrighted",
            "primary_jurisdiction": uk_jurisdiction
        }
    ]
    
    # --- Add famous movies ---
    famous_movies = [
        {
            "title": "The Wizard of Oz",
            "authors": [{"name": "Victor Fleming", "birth_date": "1889-02-23", "death_date": "1949-01-06", "nationality": "US"}],
            "creation_date": "1939-08-25",
            "status": "Copyrighted",
            "primary_jurisdiction": us_jurisdiction
        },
        {
            "title": "Metropolis",
            "authors": [{"name": "Fritz Lang", "birth_date": "1890-12-05", "death_date": "1976-08-02", "nationality": "DE"}],
            "creation_date": "1927-01-10",
            "status": "Copyrighted",
            "primary_jurisdiction": eu_jurisdiction
        },
        {
            "title": "Nosferatu",
            "authors": [{"name": "F. W. Murnau", "birth_date": "1888-12-28", "death_date": "1931-03-11", "nationality": "DE"}],
            "creation_date": "1922-03-04",
            "status": "Public Domain",
            "primary_jurisdiction": eu_jurisdiction
        }
    ]
    
    # --- Add famous music ---
    famous_music = [
        {
            "title": "Rhapsody in Blue",
            "authors": [{"name": "George Gershwin", "birth_date": "1898-09-26", "death_date": "1937-07-11", "nationality": "US"}],
            "creation_date": "1924-02-12",
            "status": "Copyrighted",
            "primary_jurisdiction": us_jurisdiction
        },
        {
            "title": "The Planets",
            "authors": [{"name": "Gustav Holst", "birth_date": "1874-09-21", "death_date": "1934-05-25", "nationality": "GB"}],
            "creation_date": "1916-09-29",
            "status": "Public Domain",
            "primary_jurisdiction": uk_jurisdiction
        }
    ]
    
    # Add to database
    books_added = database.add_famous_works("Books", famous_books)
    movies_added = database.add_famous_works("Movies", famous_movies)
    music_added = database.add_famous_works("Music", famous_music)
    
    logger.info(f"Sample data added: {books_added} books, {movies_added} movies, {music_added} music works")

def display_schedule():
    """Displays the upcoming copyright expirations."""
    logger.info("Generating schedule...")
    today = get_current_date()
    limit = 20  # Show up to 20 nearest expirations

    # Get works expiring on or after today, sorted by nearest expiry date
    expiring_works = database.get_next_expiring_works(current_date=today, limit=limit)

    if not expiring_works:
        print("\nNo upcoming copyright expirations found from today onwards.")
    else:
        print(f"\n--- Upcoming Copyright Expirations (from {today}) ---")
        # No need to sort, the works are already sorted by expiry date from the DB
        for work in expiring_works:
            expiry_str = work.copyright_expiry_date.strftime('%Y-%m-%d') if work.copyright_expiry_date else "Unknown"
            days_left = scheduler.get_days_until_expiry(work)
            days_str = f"({days_left} days remaining)" if days_left is not None else ""
            print(f"- {expiry_str} {days_str}: {work}")
        print("--------------------------------------------------")
    
    # Also display a summary of public domain works
    public_domain_works = database.get_public_domain_works()
    if public_domain_works:
        print("\n--- Works Already in Public Domain ---")
        # Group by topic
        by_topic = {}
        for work in public_domain_works:
            topic_name = work.topic.name if work.topic else "Uncategorized"
            if topic_name not in by_topic:
                by_topic[topic_name] = []
            by_topic[topic_name].append(work)
        
        # Display by topic
        for topic_name, works in by_topic.items():
            print(f"\n{topic_name}:")
            for work in sorted(works, key=lambda w: w.title):
                print(f"- {work}")
        print("--------------------------------------------------")

def display_international_status(works: List[Work], jurisdictions: List[Jurisdiction]):
    """Displays the copyright status of works across different jurisdictions."""
    print("\n--- International Copyright Status by Jurisdiction ---")
    
    if not works:
        print("No works available to display.")
        return
        
    if not jurisdictions:
        print("No jurisdictions available to display status for.")
        return

    current_date = get_current_date()

    for jurisdiction in jurisdictions:
        if not jurisdiction.id or not jurisdiction.code: # Ensure jurisdiction has ID and code
            continue

        # Construct the term description string using available attributes
        term_desc = f"life + {jurisdiction.term_years_after_death} years"
        if jurisdiction.has_special_rules:
            term_desc += " (with special rules)" # Indicate special rules exist

        # Print the correctly formatted string
        print(f"\n{jurisdiction.name} (Copyright term: {term_desc}):")

        public_domain_works = []
        copyrighted_works = []
        unknown_works = []

        for work in works:
            if not work.id: # Ensure work has an ID
                unknown_works.append(work)
                continue

            # --- Refactoring Start ---
            # Retrieve pre-calculated status and expiry date from the database
            status_info = database.get_work_copyright_status_by_jurisdiction(work.id, jurisdiction.id)
            
            status = "Unknown"
            expiry_date_str = None
            
            if status_info:
                status = status_info.get('status', 'Unknown')
                expiry_date_str = status_info.get('expiry_date') # Keep as string for now

            # Log the retrieved status for debugging if needed
            # logger.debug(f"Retrieved status for '{work.title}' in {jurisdiction.code}: {status}, Expiry: {expiry_date_str}")

            # --- Refactoring End ---

            # Categorize based on retrieved status
            if status == 'Public Domain':
                public_domain_works.append(work)
            elif status == 'Copyrighted':
                copyrighted_works.append(work)
            else: # Includes 'Unknown' or any other unexpected status
                unknown_works.append(work)

        # Display Public Domain works for this jurisdiction
        if public_domain_works:
            print("  Public Domain Works:")
            for work in sorted(public_domain_works, key=lambda w: w.title):
                 # Display author info if available
                author_str = f" by {', '.join(a.name for a in work.authors)}" if work.authors else ""
                print(f"  - {work.title}{author_str}")
        else:
             print("  No works found in Public Domain for this jurisdiction.")

        # Optionally display Copyrighted or Unknown works if desired
        # if copyrighted_works:
        #     print("\n  Copyrighted Works:")
        #     for work in sorted(copyrighted_works, key=lambda w: w.title):
        #         author_str = f" by {', '.join(a.name for a in work.authors)}" if work.authors else ""
        #         # Optionally show expiry date if available and needed
        #         expiry_info = ""
        #         if expiry_date_str:
        #             try:
        #                 expiry_dt = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        #                 if expiry_dt > current_date:
        #                     expiry_info = f" (Expires: {expiry_date_str})"
        #             except ValueError:
        #                 pass # Ignore invalid date format
        #         print(f"  - {work.title}{author_str}{expiry_info}")

        # if unknown_works:
        #     print("\n  Unknown Status Works:")
        #     for work in sorted(unknown_works, key=lambda w: w.title):
        #         author_str = f" by {', '.join(a.name for a in work.authors)}" if work.authors else ""
        #         print(f"  - {work.title}{author_str}")

    print("--------------------------------------------------")

def main():
    """Main entry point for the application."""
    logger.info("Application started.")
    
    # 1. Initialize the system (database, topics, jurisdictions)
    initialize_system()
    
    # 2. Check if we should add sample data (if the database is empty)
    if not database.get_all_works():
        logger.info("No existing works found in database, adding sample data.")
        add_sample_data()
    
    # 3. Run the scraper to gather/update data (optional based on the URLs in config.py)
    if TARGET_URLS:
        run_scraper()

    # 4. Process data and display the schedules
    display_schedule()
    
    # 5. Display international copyright status
    # Fetch all works and jurisdictions needed for the international report
    all_works = database.get_all_works()
    jurisdictions = database.get_all_jurisdictions()
    display_international_status(all_works, jurisdictions) # <--- Pass arguments

    logger.info("Application finished.")



if __name__ == "__main__":
    main()
