import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
from datetime import datetime, date

from ...data_models import Work, Author
from ...config import USER_AGENT

logger = logging.getLogger(__name__)

def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Helper function to parse date strings (add more formats as needed)."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y", "%B %d, %Y"): # Add more formats found on target sites
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            # If only year is parsed, maybe default to Jan 1st or handle differently
            if fmt == "%Y":
                 # Be careful making assumptions. Maybe return None or store year only?
                 # For simplicity here, let's assume Jan 1st if only year is known.
                 return date(dt.year, 1, 1)
            return dt.date()
        except ValueError:
            continue
    logger.warning(f"Could not parse date string: {date_str}")
    return None

def scrape(url: str) -> List[Work]:
    """
    Scrapes a specific URL (example.com structure assumed) for works.
    This needs to be adapted for the actual structure of each target website.
    """
    logger.info(f"Attempting to scrape URL: {url}")
    works: List[Work] = []
    headers = {'User-Agent': USER_AGENT}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch URL {url}: {e}")
        return works # Return empty list on failure

    soup = BeautifulSoup(response.content, 'html.parser')

    # --- Website-Specific Scraping Logic ---
    # This is highly dependent on the target website's HTML structure.
    # You'll need to inspect the HTML of each target site and write
    # selectors (CSS selectors or XPath) to extract the desired data.

    # Example: Assume the site has a table with class 'works-list'
    # where each row represents a work.
    # <table>
    #   <tr class="work-item">
    #     <td class="title">Example Book</td>
    #     <td class="author">John Doe</td>
    #     <td class="author-death-date">1950-01-15</td>
    #     <td class="publication-date">1920</td>
    #   </tr>
    # </table>

    work_table = soup.find('table', class_='works-list') # Adjust selector
    if not work_table:
        logger.warning(f"Could not find work table with class 'works-list' on {url}")
        return works

    for row in work_table.find_all('tr', class_='work-item'): # Adjust selector
        try:
            title_tag = row.find('td', class_='title') # Adjust selector
            author_tag = row.find('td', class_='author') # Adjust selector
            death_date_tag = row.find('td', class_='author-death-date') # Adjust selector
            pub_date_tag = row.find('td', class_='publication-date') # Adjust selector

            title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
            author_name = author_tag.get_text(strip=True) if author_tag else None
            death_date_str = death_date_tag.get_text(strip=True) if death_date_tag else None
            pub_date_str = pub_date_tag.get_text(strip=True) if pub_date_tag else None

            if not title or not author_name:
                logger.warning(f"Skipping row due to missing title or author: {row.prettify()}")
                continue

            # Create Author object
            author = Author(
                name=author_name,
                death_date=parse_date(death_date_str)
                # Add birth date parsing if available
            )

            # Create Work object
            work = Work(
                title=title,
                authors=[author],
                creation_date=parse_date(pub_date_str),
                source_url=url # Or a more specific URL if available per work
            )
            works.append(work)
            logger.debug(f"Successfully parsed work: {work}")

        except Exception as e:
            logger.error(f"Error parsing row on {url}: {e}\nRow HTML:\n{row.prettify()}", exc_info=True)
            continue # Skip to the next row if one fails

    logger.info(f"Finished scraping {url}. Found {len(works)} works.")
    return works

# You would create more files like this (e.g., `gutenberg_spider.py`, `archiveorg_spider.py`)
# each tailored to a specific website's structure.
