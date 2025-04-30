"""
Module for generating structured knowledge using LLM capabilities.
"""
import json
import os
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, date

from .config import DATA_DIR, BATCH_SIZE
from .templates import AUTHOR_TEMPLATE, WORK_TEMPLATE, INDEX_TEMPLATE
from .ai import query_llm
from .data_models import Work, Author, Topic
from . import database

# Set up logging
logger = logging.getLogger(__name__)

# Path to store generated knowledge
KNOWLEDGE_DIR = os.path.join(DATA_DIR, "knowledge")
INDEX_PATH = os.path.join(KNOWLEDGE_DIR, "index.json")

def ensure_knowledge_dirs():
    """Ensure knowledge directories exist."""
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    
    # Create subdirectories for organizing data
    os.makedirs(os.path.join(KNOWLEDGE_DIR, "authors"), exist_ok=True)
    os.makedirs(os.path.join(KNOWLEDGE_DIR, "works"), exist_ok=True)
    os.makedirs(os.path.join(KNOWLEDGE_DIR, "topics"), exist_ok=True)
    
    # Initialize index if it doesn't exist
    if not os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, 'w') as f:
            json.dump({"authors": {}, "works": {}, "topics": {}}, f, indent=2)
        logger.info(f"Created new knowledge index at {INDEX_PATH}")

def load_index():
    """Load the current knowledge index."""
    ensure_knowledge_dirs()
    try:
        with open(INDEX_PATH, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        logger.warning("Could not load index, creating new one")
        index = {"authors": {}, "works": {}, "topics": {}}
        with open(INDEX_PATH, 'w') as f:
            json.dump(index, f, indent=2)
        return index

def save_index(index):
    """Save the updated knowledge index."""
    with open(INDEX_PATH, 'w') as f:
        json.dump(index, f, indent=2)
    logger.debug("Knowledge index updated")

def generate_topic_knowledge(topic_name: str, count: int = 10, time_period: Optional[str] = None) -> List[Dict]:
    """
    Generate knowledge about works in a specific topic, optionally from a time period.
    
    Args:
        topic_name: The topic/genre to generate knowledge about
        count: Number of works to generate
        time_period: Optional time period (e.g., "19th century", "1920s", "Ancient Greece")
        
    Returns:
        List of generated work dictionaries
    """
    logger.info(f"Generating knowledge about {count} {topic_name} works{' from ' + time_period if time_period else ''}")
    
    # Load existing index to avoid duplicates
    index = load_index()
    
    # Build prompt for the LLM
    prompt = f"""Generate detailed information about {count} important {topic_name} works"""
    
    if time_period:
        prompt += f" from {time_period}"
    
    prompt += """. 
    
For each work, provide complete information following this exact JSON structure:
```
{work_template}
```

Include all necessary dates in ISO format (YYYY-MM-DD), using approximations when exact dates are unknown.
For each author, include complete birth and death dates if available.
Ensure all facts are historically accurate and based on reliable information.
DO NOT include any works or authors already in this list: {existing_works}.
The response should be a valid JSON array of work objects that can be parsed directly.
"""
    
    # Get existing works to avoid duplicates
    existing_works = list(index.get("works", {}).keys())
    existing_works_str = ", ".join(existing_works[:20])  # Limit list length in prompt
    if len(existing_works) > 20:
        existing_works_str += f" and {len(existing_works) - 20} more"
    
    # Replace placeholders in the prompt
    prompt = prompt.replace("{work_template}", json.dumps(WORK_TEMPLATE, indent=2))
    prompt = prompt.replace("{existing_works}", existing_works_str)
    
    # Query the LLM
    response = query_llm(prompt)
    
    # Extract JSON from response
    try:
        # Find JSON content between triple backticks if present
        if "```json" in response and "```" in response.split("```json", 1)[1]:
            json_str = response.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in response and "```" in response.split("```", 1)[1]:
            json_str = response.split("```", 1)[1].split("```", 1)[0].strip()
        else:
            # Just try to parse the whole response
            json_str = response
            
        generated_works = json.loads(json_str)
        logger.info(f"Successfully parsed {len(generated_works)} works from LLM response")
        return generated_works
    
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.debug(f"Raw response: {response}")
        return []

def process_generated_works(generated_works: List[Dict]) -> List[Work]:
    """
    Process generated work dictionaries into Work objects and save to JSON.
    Also extracts and saves authors.
    
    Args:
        generated_works: List of work dictionaries from LLM
        
    Returns:
        List of Work objects ready for database insertion
    """
    index = load_index()
    processed_works = []
    
    for work_dict in generated_works:
        # Check if work already exists (by title)
        title = work_dict.get("title")
        if not title:
            logger.warning(f"Skipping work with missing title: {work_dict}")
            continue
            
        if title in index.get("works", {}):
            logger.info(f"Skipping duplicate work: {title}")
            continue
        
        # Process authors first so we can link them to the work
        author_objects = []
        for author_name in work_dict.get("authors", []):
            # Check if author exists in index
            author_obj = None
            if author_name in index.get("authors", {}):
                # Author exists, load from file
                author_id = index["authors"][author_name]["id"]
                author_path = os.path.join(KNOWLEDGE_DIR, "authors", f"{author_id}.json")
                try:
                    with open(author_path, 'r') as f:
                        author_data = json.load(f)
                        author_obj = Author(
                            name=author_data["name"],
                            birth_date=author_data.get("birth_date"),
                            death_date=author_data.get("death_date"),
                            nationality=author_data.get("nationality"),
                            bio=author_data.get("bio"),
                            id=author_id
                        )
                except (json.JSONDecodeError, FileNotFoundError):
                    logger.warning(f"Could not load author {author_name} from file, will recreate")
                    author_obj = None
            
            if not author_obj:
                # Create new author with minimal info
                author_obj = Author(
                    name=author_name,
                    birth_date=None,
                    death_date=None
                )
                
                # Generate author details using LLM

                author_detail_prompt = f"""Generate detailed information about the author {author_name} in this JSON structure:
```
{json.dumps(AUTHOR_TEMPLATE, indent=2)}
```
Include accurate birth and death dates in ISO format (YYYY-MM-DD) if known.
The response should be a valid JSON object that can be parsed directly.
"""
                author_detail_prompt = author_detail_prompt.replace("{author_template}", 
                                                                   json.dumps(AUTHOR_TEMPLATE, indent=2))
                
                try:
                    author_response = query_llm(author_detail_prompt)
                    
                    # Extract JSON
                    if "```json" in author_response:
                        author_json_str = author_response.split("```json", 1)[1].split("```", 1)[0].strip()
                    elif "```" in author_response:
                        author_json_str = author_response.split("```", 1)[1].split("```", 1)[0].strip()
                    else:
                        author_json_str = author_response
                        
                    author_data = json.loads(author_json_str)
                    
                    # Update author object with details
                    author_obj.birth_date = author_data.get("birth_date")
                    author_obj.death_date = author_data.get("death_date")
                    author_obj.nationality = author_data.get("nationality")
                    author_obj.bio = author_data.get("bio")
                    
                    # Save to index and file
                    next_id = len(index.get("authors", {})) + 1
                    author_obj.id = next_id
                    
                    # Save to index
                    if "authors" not in index:
                        index["authors"] = {}
                    index["authors"][author_name] = {"id": next_id, "works": []}
                    
                    # Save to file
                    author_path = os.path.join(KNOWLEDGE_DIR, "authors", f"{next_id}.json")
                    with open(author_path, 'w') as f:
                        json.dump({
                            "id": next_id,
                            "name": author_obj.name,
                            "birth_date": author_obj.birth_date,
                            "death_date": author_obj.death_date,
                            "nationality": author_obj.nationality,
                            "bio": author_obj.bio,
                            "works": []
                        }, f, indent=2)
                    
                    logger.info(f"Created and saved new author: {author_name} (ID: {next_id})")
                    
                except Exception as e:
                    logger.error(f"Failed to generate author details for {author_name}: {e}")
            
            author_objects.append(author_obj)
        
        # Process topic
        topic_name = work_dict.get("topic", "Uncategorized")
        if topic_name not in index.get("topics", {}):
            # Add new topic
            next_topic_id = len(index.get("topics", {})) + 1
            if "topics" not in index:
                index["topics"] = {}
            index["topics"][topic_name] = {"id": next_topic_id, "work_count": 0}
            
            # Save topic file
            topic_path = os.path.join(KNOWLEDGE_DIR, "topics", f"{next_topic_id}.json")
            with open(topic_path, 'w') as f:
                json.dump({
                    "id": next_topic_id,
                    "name": topic_name,
                    "works": []
                }, f, indent=2)
            
            logger.info(f"Created new topic: {topic_name} (ID: {next_topic_id})")
        
        topic_id = index["topics"][topic_name]["id"]
        topic_obj = Topic(name=topic_name, id=topic_id)
        
        # Create work object
        next_work_id = len(index.get("works", {})) + 1
        work_obj = Work(
            id=next_work_id,
            title=title,
            authors=author_objects,
            creation_date=work_dict.get("creation_date"),
            publication_date=work_dict.get("publication_date"),
            topic=topic_obj,
            description=work_dict.get("description"),
            is_collaborative=work_dict.get("is_collaborative", False),
            original_language=work_dict.get("original_language"),
            original_publisher=work_dict.get("original_publisher"),
            source_url=work_dict.get("source_url")
        )
        
        # Save work to file
        work_path = os.path.join(KNOWLEDGE_DIR, "works", f"{next_work_id}.json")
        with open(work_path, 'w') as f:
            json.dump({
                "id": next_work_id,
                "title": work_obj.title,
                "authors": [a.name for a in work_obj.authors],
                "creation_date": work_obj.creation_date,
                "publication_date": work_obj.publication_date,
                "topic": work_obj.topic.name if work_obj.topic else None,
                "secondary_topics": work_dict.get("secondary_topics", []),
                "description": work_obj.description,
                "is_collaborative": work_obj.is_collaborative,
                "original_language": work_obj.original_language,
                "original_publisher": work_obj.original_publisher,
                "source_url": work_obj.source_url
            }, f, indent=2)
        
        # Update index
        if "works" not in index:
            index["works"] = {}
        index["works"][title] = {
            "id": next_work_id,
            "authors": [a.name for a in work_obj.authors]
        }
        
        # Update author index to include this work
        for author in work_obj.authors:
            if author.name in index.get("authors", {}):
                if title not in index["authors"][author.name].get("works", []):
                    if "works" not in index["authors"][author.name]:
                        index["authors"][author.name]["works"] = []
                    index["authors"][author.name]["works"].append(title)
        
        # Update topic index
        index["topics"][topic_name]["work_count"] = index["topics"][topic_name].get("work_count", 0) + 1
        
        # Append to processed works
        processed_works.append(work_obj)
        logger.info(f"Processed work: {title} (ID: {next_work_id})")
    
    # Save updated index
    save_index(index)
    
    return processed_works

def _parse_date_string(date_str: Optional[str]) -> Optional[date]:
    """Safely parse an ISO date string (YYYY-MM-DD) into a date object."""
    if not date_str:
        return None
    try:
        # Attempt to parse the full date
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        try:
            # If full date fails, try parsing just the year (treat as Jan 1st)
            # This handles cases where LLM might only provide the year
            year = int(date_str)
            # Basic validation for plausible years
            if 0 < year < 3000:
                 logger.warning(f"Parsing date string '{date_str}' as year only. Assuming YYYY-01-01.")
                 return date(year, 1, 1)
            else:
                 logger.warning(f"Invalid year '{date_str}' found. Ignoring date.")
                 return None
        except (ValueError, TypeError):
             logger.warning(f"Could not parse date string: '{date_str}'. Ignoring date.")
             return None


def import_knowledge_to_db(topic_filter: Optional[str] = None, limit: int = 100) -> int:
    """
    Import knowledge from JSON files to database.

    Args:
        topic_filter: Optional topic to filter works by
        limit: Maximum number of works to import

    Returns:
        Number of works imported
    """
    logger.info(f"Importing knowledge to database{' for topic: ' + topic_filter if topic_filter else ''}")

    index = load_index()
    imported_count = 0

    # Get works to import
    work_ids = []
    # ... (rest of the work ID gathering logic remains the same) ...
    if topic_filter:
        # Filter by topic
        if topic_filter in index.get("topics", {}):
            topic_id = index["topics"][topic_filter]["id"]
            topic_path = os.path.join(KNOWLEDGE_DIR, "topics", f"{topic_id}.json")
            try:
                with open(topic_path, 'r') as f:
                    topic_data = json.load(f)
                    # Get work titles from this topic's file (assuming they are stored there)
                    # Note: The index structure might need adjustment if topic files don't list works
                    # Let's assume the index itself is the source of truth for work IDs by topic for now
                    # We need to iterate through works and check their topic
                    for work_title, work_info in index.get("works", {}).items():
                         work_file_path = os.path.join(KNOWLEDGE_DIR, "works", f"{work_info['id']}.json")
                         try:
                             with open(work_file_path, 'r') as wf:
                                 work_file_data = json.load(wf)
                                 if work_file_data.get("topic") == topic_filter:
                                     work_ids.append(work_info["id"])
                         except (json.JSONDecodeError, FileNotFoundError):
                             logger.warning(f"Could not load work file for {work_title} while filtering by topic.")

            except (json.JSONDecodeError, FileNotFoundError):
                logger.warning(f"Could not load topic file for {topic_filter}")
    else:
        # Get all work IDs
        for work_title, work_data in index.get("works", {}).items():
            work_ids.append(work_data["id"])


    # Limit the number of works
    work_ids = work_ids[:limit]
    logger.info(f"Found {len(work_ids)} works to import")

    # Load and import each work
    for work_id in work_ids:
        work_path = os.path.join(KNOWLEDGE_DIR, "works", f"{work_id}.json")
        try:
            with open(work_path, 'r') as f:
                work_data = json.load(f)

                # Load authors
                author_objects = []
                for author_name in work_data.get("authors", []):
                    if author_name in index.get("authors", {}):
                        author_id = index["authors"][author_name]["id"]
                        author_path = os.path.join(KNOWLEDGE_DIR, "authors", f"{author_id}.json")

                        try:
                            with open(author_path, 'r') as author_file:
                                author_data = json.load(author_file)
                                # *** Convert date strings to date objects here ***
                                birth_date_obj = _parse_date_string(author_data.get("birth_date"))
                                death_date_obj = _parse_date_string(author_data.get("death_date"))

                                author_obj = Author(
                                    name=author_data["name"],
                                    birth_date=birth_date_obj, # Use converted date object
                                    death_date=death_date_obj, # Use converted date object
                                    nationality=author_data.get("nationality"),
                                    bio=author_data.get("bio") # Bio field added previously
                                )
                                # Save author to DB and get DB ID
                                saved_author = database.get_or_save_author(author_obj)
                                if saved_author:
                                    author_objects.append(saved_author)
                                else:
                                    logger.warning(f"Failed to save author {author_name} to database")
                        except (json.JSONDecodeError, FileNotFoundError):
                            logger.warning(f"Could not load author file for {author_name}")
                    else:
                         logger.warning(f"Author '{author_name}' listed in work '{work_data['title']}' but not found in index.")


                # Get or create topic
                topic_name = work_data.get("topic", "Uncategorized")
                topic_obj = database.get_topic_by_name(topic_name)
                if not topic_obj:
                    topic_obj = database.add_topic(topic_name)
                    if not topic_obj:
                        logger.warning(f"Failed to add topic {topic_name} to database, skipping work.")
                        continue # Skip this work if topic fails

                # *** Convert work date strings to date objects ***
                creation_date_obj = _parse_date_string(work_data.get("creation_date"))
                publication_date_obj = _parse_date_string(work_data.get("publication_date")) # Use the field name from JSON

                # Create work object
                work_obj = Work(
                    title=work_data["title"],
                    authors=author_objects,
                    creation_date=creation_date_obj, # Use converted date object
                    # Use publication_date which syncs with first_publication_date via __post_init__
                    publication_date=publication_date_obj,
                    topic=topic_obj,
                    description=work_data.get("description"),
                    is_collaborative=work_data.get("is_collaborative", False),
                    original_language=work_data.get("original_language"),
                    original_publisher=work_data.get("original_publisher"),
                    source_url=work_data.get("source_url")
                )

                # Save work to database
                # Check if work already exists by title before saving
                existing_work = database.get_work_by_title(work_obj.title)
                if existing_work:
                     logger.info(f"Work '{work_obj.title}' already exists in database (ID: {existing_work.id}). Skipping import.")
                     continue

                saved_work = database.save_work(work_obj)
                if saved_work:
                    imported_count += 1
                    logger.info(f"Imported work to database: {saved_work.title} (ID: {saved_work.id})")
                else:
                    logger.warning(f"Failed to import work {work_data['title']} to database")

        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.warning(f"Could not load work file for ID {work_id}: {e}")
        except Exception as e:
             logger.error(f"Unexpected error processing work ID {work_id}: {e}", exc_info=True)


    logger.info(f"Successfully imported {imported_count} out of {len(work_ids)} considered works to database")
    return imported_count

def generate_knowledge_by_topic(topics: List[str], works_per_topic: int = 10) -> None:
    """
    Generate knowledge for multiple topics.
    
    Args:
        topics: List of topics to generate knowledge for
        works_per_topic: Number of works to generate per topic
    """
    logger.info(f"Generating knowledge for {len(topics)} topics")
    
    all_processed_works = []
    for topic in topics:
        logger.info(f"Generating knowledge for topic: {topic}")
        generated_works = generate_topic_knowledge(topic, count=works_per_topic)
        processed_works = process_generated_works(generated_works)
        all_processed_works.extend(processed_works)
        logger.info(f"Generated and processed {len(processed_works)} works for topic {topic}")
    
    logger.info(f"Generated a total of {len(all_processed_works)} works across {len(topics)} topics")

