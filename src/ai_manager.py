"""
AI-enhanced data collection and processing for author rights management.
This script provides a command-line interface for AI-powered scraping and database operations.
"""
import argparse
import logging
import os
import sys
from datetime import date
from typing import List
from .knowledge_generator import (
    generate_knowledge_by_topic,
    import_knowledge_to_db,
    ensure_knowledge_dirs
)

# Add parent directory to path to ensure imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_models import Work, Author, Topic
from src import database
from src import scheduler
from src.ai import enhance_work_with_llm, enhance_author_with_llm, process_batch, verify_copyright_status
from src.scraper.spiders import gutenberg_spider
from src.config import BATCH_SIZE, GEMINI_API_KEY

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def init_system():
    """Initialize the system."""
    logger.info("Initializing system...")
    database.init_db()
    database.initialize_default_jurisdictions()
    logger.info("System initialized successfully.")

def validate_gemini_api_key():
    """Validate that the Gemini API key is set and valid."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_API_KEY":
        logger.error("Gemini API key not set. Please add your key to the .env file.")
        sys.exit(1)
    logger.info("Gemini API key validated.")

def scrape_and_enhance(source: str, query: str = "", max_works: int = 10) -> List[Work]:
    """
    Scrape works from the specified source and enhance them with AI.
    
    Args:
        source: The source to scrape from ('gutenberg', 'archive', etc.)
        query: Optional search query to filter results
        max_works: Maximum number of works to scrape
        
    Returns:
        List of enhanced Work objects
    """
    logger.info(f"Starting scraping from {source} with query: '{query}'")
    
    works = []
    
    if source.lower() == "gutenberg":
        works = gutenberg_spider.scrape_gutenberg_batch(query=query, max_works=max_works)
    # Add more sources here as they're implemented
    else:
        logger.error(f"Unknown source: {source}")
        return []
    
    logger.info(f"Scraped and enhanced {len(works)} works from {source}")
    return works

def save_works_to_database(works: List[Work]) -> int:
    """
    Save a list of works to the database.
    
    Args:
        works: List of Work objects to save
        
    Returns:
        Number of successfully saved works
    """
    logger.info(f"Saving {len(works)} works to database...")
    
    saved_count = 0
    for work in works:
        # Update copyright status with scheduler
        work = scheduler.update_work_status(work)
        
        # Ensure topic exists in database
        if work.topic:
            logger.info(f"Work '{work.title}' has topic: {work.topic.name}")
            topic = database.get_topic_by_name(work.topic.name)
            if not topic:
                logger.info(f"Topic '{work.topic.name}' not found in database, adding it")
                topic = database.add_topic(work.topic.name)
                logger.info(f"Added topic '{topic.name}' with ID: {topic.id if topic else 'None'}")
            else:
                logger.info(f"Found existing topic '{topic.name}' with ID: {topic.id}")
            work.topic = topic
        else:
            # If work has no topic, assign a default 'Books' topic
            logger.info(f"Work '{work.title}' has no topic, assigning default 'Books' topic")
            topic = database.get_topic_by_name('Books')
            if not topic:
                topic = database.add_topic('Books')
                logger.info(f"Added default 'Books' topic with ID: {topic.id if topic else 'None'}")
            else:
                logger.info(f"Using existing 'Books' topic with ID: {topic.id}")
            work.topic = topic
        
        # Save work
        saved_work = database.save_work(work)
        if saved_work:
            saved_count += 1
            logger.info(f"Saved work: {saved_work.title} with topic: {saved_work.topic.name if saved_work.topic else 'None'}")
        else:
            logger.warning(f"Failed to save work: {work.title}")
    
    logger.info(f"Successfully saved {saved_count} out of {len(works)} works")
    return saved_count

def enhance_existing_works(topic_name: str = None, limit: int = 10) -> int:
    """
    Enhance existing works in the database with AI.
    
    Args:
        topic_name: Optional topic to filter works by
        limit: Maximum number of works to enhance
        
    Returns:
        Number of successfully enhanced works
    """
    logger.info(f"Enhancing existing works{' for topic: ' + topic_name if topic_name else ''}...")
    
    # Get works to enhance
    works = []
    if topic_name:
        works = database.get_works_by_topic(topic_name)
    else:
        works = database.get_all_works()
    
    # Limit the number of works
    works = works[:limit]
    
    logger.info(f"Found {len(works)} works to enhance")
    
    # Process in batches
    enhanced_count = 0
    for i in range(0, len(works), BATCH_SIZE):
        batch = works[i:i+BATCH_SIZE]
        logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(works)-1)//BATCH_SIZE + 1} with {len(batch)} works")
        
        # Enhance the batch
        enhanced_batch = process_batch(batch)
        
        # Save enhanced works back to database
        for work in enhanced_batch:
            # Update the work's copyright status
            work = scheduler.update_work_status(work)
            
            # Save the enhanced work
            saved_work = database.save_work(work)
            if saved_work:
                enhanced_count += 1
    
    logger.info(f"Successfully enhanced {enhanced_count} out of {len(works)} works")
    return enhanced_count

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="AI-enhanced copyright data collection")
    
    # Main command
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Initialize command
    init_parser = subparsers.add_parser("init", help="Initialize the system")
    
    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape and enhance works")
    scrape_parser.add_argument("--source", default="gutenberg", help="Source to scrape from")
    scrape_parser.add_argument("--query", default="", help="Search query to filter results")
    scrape_parser.add_argument("--max", type=int, default=10, help="Maximum number of works to scrape")
    
    # Enhance command
    enhance_parser = subparsers.add_parser("enhance", help="Enhance existing works in the database")
    enhance_parser.add_argument("--topic", help="Topic to filter works by")
    enhance_parser.add_argument("--limit", type=int, default=10, help="Maximum number of works to enhance")
    # Generate knowledge command
    generate_parser = subparsers.add_parser("generate", help="Generate knowledge using LLM")
    generate_parser.add_argument("--topics", nargs="+", required=True, help="Topics to generate knowledge for")
    generate_parser.add_argument("--count", type=int, default=5, help="Number of works per topic")
    
    # Import knowledge command  
    import_parser = subparsers.add_parser("import", help="Import generated knowledge to database")
    import_parser.add_argument("--topic", help="Topic to filter works by")
    import_parser.add_argument("--limit", type=int, default=100, help="Maximum number of works to import")
 
    # Parse arguments
    args = parser.parse_args()
    
    # Validate that the API key is set and valid
    validate_gemini_api_key()
    
    # Process commands
    if args.command == "init":
        init_system()
        ensure_knowledge_dirs() # Initialize knowledge directories
        
    elif args.command == "scrape":
        works = scrape_and_enhance(args.source, args.query, args.max)
        save_works_to_database(works)
        
    elif args.command == "enhance":
        enhance_existing_works(args.topic, args.limit)
 
    elif args.command == "generate":
        generate_knowledge_by_topic(args.topics, args.count)
        
    elif args.command == "import":
        import_knowledge_to_db(args.topic, args.limit)
        
    else:
        parser.print_help()
    
    logger.info("Script completed successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())