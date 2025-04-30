"""
Spider specifically designed for scraping public domain works from Project Gutenberg.
Integrates with the AI module to enhance and validate the data.
"""
import logging
import requests
import re
import time
from typing import List, Optional
from datetime import datetime, date
from bs4 import BeautifulSoup

from ...data_models import Work, Author, Topic
from ...config import USER_AGENT, REQUEST_DELAY_SECONDS
from ... import ai

logger = logging.getLogger(__name__)

# Constants specific to Project Gutenberg
GUTENBERG_BASE_URL = "https://www.gutenberg.org"
GUTENBERG_CATALOG = f"{GUTENBERG_BASE_URL}/ebooks/search/"

def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Helper function to parse date strings in various formats."""
    if not date_str:
        return None
    
    # Remove any extraneous text
    date_str = re.sub(r'\(.*?\)', '', date_str).strip()
    
    # Try different date formats common in Gutenberg
    for fmt in ("%Y-%m-%d", "%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt == "%Y":
                # If only year is provided, default to January 1st
                return date(dt.year, 1, 1)
            return dt.date()
        except ValueError:
            continue
    
    # Try to extract year only if nothing else works
    year_match = re.search(r'\b(\d{4})\b', date_str)
    if year_match:
        year = int(year_match.group(1))
        if 1400 <= year <= datetime.now().year:  # Sanity check for valid year
            return date(year, 1, 1)
    
    logger.warning(f"Could not parse date string: {date_str}")
    return None

def scrape_catalog(max_pages: int = 5, query: str = "") -> List[Work]:
    """
    Scrapes the Project Gutenberg catalog pages.
    
    Args:
        max_pages: Maximum number of pages to scrape
        query: Optional search query to filter results
        
    Returns:
        List of Work objects with basic information
    """
    logger.info(f"Starting to scrape Project Gutenberg catalog: {GUTENBERG_CATALOG}")
    works = []
    
    # Construct search URL if query is provided
    search_url = GUTENBERG_CATALOG
    if query:
        search_url = f"{search_url}?query={query}"
    
    headers = {'User-Agent': USER_AGENT}
    
    for page_num in range(1, max_pages + 1):
        page_url = f"{search_url}&page={page_num}" if page_num > 1 else search_url
        logger.info(f"Scraping catalog page {page_num}: {page_url}")
        
        try:
            response = requests.get(page_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all book entries
            book_elements = soup.select('li.booklink')
            
            if not book_elements:
                logger.warning(f"No book elements found on page {page_num}")
                break
            
            logger.info(f"Found {len(book_elements)} book entries on page {page_num}")
            
            for book_element in book_elements:
                try:
                    # Extract book ID and title
                    title_element = book_element.select_one('span.title')
                    if not title_element:
                        continue
                    
                    title = title_element.get_text(strip=True)
                    
                    # Get the book ID from the link
                    link_element = book_element.select_one('a')
                    if not link_element or not link_element.has_attr('href'):
                        continue
                    
                    book_url = link_element['href']
                    book_id_match = re.search(r'/ebooks/(\d+)', book_url)
                    if not book_id_match:
                        continue
                    
                    book_id = book_id_match.group(1)
                    full_book_url = f"{GUTENBERG_BASE_URL}{book_url}"
                    
                    # Extract author(s)
                    author_element = book_element.select_one('span.subtitle')
                    author_name = "Unknown"
                    if author_element:
                        author_text = author_element.get_text(strip=True)
                        # Typically in format "by Author Name"
                        if author_text.startswith("by "):
                            author_name = author_text[3:].strip()
                    
                    # Add the basic work info
                    work = Work(
                        title=title,
                        authors=[Author(name=author_name)],
                        source_url=full_book_url,
                        status="Public Domain"  # Default for Gutenberg
                    )
                    
                    works.append(work)
                    
                except Exception as e:
                    logger.error(f"Error parsing book element: {e}")
                    continue
            
            # Be polite and respect the server
            time.sleep(REQUEST_DELAY_SECONDS)
            
        except Exception as e:
            logger.error(f"Error scraping catalog page {page_url}: {e}")
            break
    
    logger.info(f"Found {len(works)} works in Project Gutenberg catalog")
    return works

def enhance_work_details(work: Work) -> Work:
    """
    Scrapes detailed information for a work and enhances it with AI.
    
    Args:
        work: Work object with basic information
        
    Returns:
        Enhanced Work object with detailed information
    """
    if not work.source_url:
        logger.warning(f"No source URL for work: {work.title}")
        return work
    
    logger.info(f"Enhancing work details for: {work.title}")
    headers = {'User-Agent': USER_AGENT}
    
    try:
        response = requests.get(work.source_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract publication date
        pub_date_element = soup.select_one('th:-soup-contains("Release Date") + td')
        if pub_date_element:
            pub_date_text = pub_date_element.get_text(strip=True)
            work.first_publication_date = parse_date(pub_date_text)
        
        # Look for more detailed author information
        author_element = soup.select_one('th:-soup-contains("Author") + td')
        if author_element and work.authors:
            author_text = author_element.get_text(strip=True)
            
            # Check if we have dates in parentheses
            birth_death_match = re.search(r'\((\d{4})-(\d{4})\)', author_text)
            if birth_death_match:
                birth_year = int(birth_death_match.group(1))
                death_year = int(birth_death_match.group(2))
                
                # Update author information
                work.authors[0].birth_date = date(birth_year, 1, 1)
                work.authors[0].death_date = date(death_year, 1, 1)
            
            # Extract just the name without dates
            clean_name = re.sub(r'\s*\(.*?\)\s*', '', author_text).strip()
            if clean_name:
                work.authors[0].name = clean_name
        
        # Look for language
        language_element = soup.select_one('th:-soup-contains("Language") + td')
        if language_element:
            language = language_element.get_text(strip=True)
            # Could store this in a custom field if needed
        
        # Look for subject/topic
        subject_elements = soup.select('th:-soup-contains("Subject") + td a')
        if subject_elements:
            # Get the first subject as the topic
            topic_name = subject_elements[0].get_text(strip=True)
            work.topic = Topic(name=topic_name)
        
        # Now use AI to enhance the work with any missing details
        work = ai.enhance_work_with_llm(work)
        
        # After AI enhancement, use another AI call specifically for copyright status
        copyright_status = ai.verify_copyright_status(work)
        if copyright_status:
            for jur_code, status in copyright_status.items():
                work.status_by_jurisdiction[jur_code] = status
        
        # Be polite and respect the server
        time.sleep(REQUEST_DELAY_SECONDS)
        
        logger.info(f"Successfully enhanced work: {work.title}")
        return work
        
    except Exception as e:
        logger.error(f"Error enhancing work details for {work.title}: {e}")
        return work

def scrape_gutenberg_batch(query: str = "", max_works: int = 10) -> List[Work]:
    """
    Scrapes a batch of works from Project Gutenberg, complete with details.
    
    Args:
        query: Optional search query to filter works
        max_works: Maximum number of works to scrape
        
    Returns:
        List of fully enhanced Work objects ready for database insertion
    """
    # Calculate required pages based on typically 25 works per page
    estimated_pages = (max_works // 25) + 1
    
    # Scrape the catalog to get basic work information
    works = scrape_catalog(max_pages=estimated_pages, query=query)
    
    # Limit to requested number
    works = works[:max_works]
    
    # Process in batches according to config
    enhanced_works = []
    current_batch = []
    
    for i, work in enumerate(works):
        logger.info(f"Processing work {i+1}/{len(works)}: {work.title}")
        
        # Enhance the individual work with detailed scraping
        detailed_work = enhance_work_details(work)
        current_batch.append(detailed_work)
        
        # When batch is full or we're at the end, process with AI
        if len(current_batch) >= 5 or i == len(works) - 1:
            # Process the current batch with AI
            batch_results = ai.process_batch(current_batch)
            enhanced_works.extend(batch_results)
            current_batch = []
    
    logger.info(f"Scraped and enhanced {len(enhanced_works)} works from Project Gutenberg")
    return enhanced_works

if __name__ == "__main__":
    # For testing directly
    logging.basicConfig(level=logging.INFO)
    works = scrape_gutenberg_batch(max_works=3)
    for work in works:
        print(f"Work: {work.title}")
        print(f"Authors: {', '.join(str(a) for a in work.authors)}")
        print(f"Topic: {work.topic.name if work.topic else 'Unknown'}")
        print(f"Publication date: {work.first_publication_date}")
        print(f"Status: {work.status}")
        print(f"Status by jurisdiction: {work.status_by_jurisdiction}")
        print("---")