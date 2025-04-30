"""
Module that provides RAG (Retrieval-Augmented Generation) capabilities
for the AI to access database content when answering questions.
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import date
import re

from .data_models import Work, Author, Topic, Jurisdiction
from . import database
from .date_provider import get_current_date
from .ai import answer_query_with_context

logger = logging.getLogger(__name__)

def generate_db_stats_context() -> str:
    """Generate context about database statistics."""
    try:
        all_works = database.get_all_works()
        all_authors = database.get_all_authors()
        all_topics = database.get_all_topics()
        jurisdictions = database.get_all_jurisdictions()
        pd_works = [w for w in all_works if w.status == "Public Domain"]
        copyrighted_works = [w for w in all_works if w.status == "Copyrighted"]
        
        context = "DATABASE STATISTICS:\n"
        context += f"- {len(all_works)} total works in database\n"
        context += f"- {len(all_authors)} authors\n"
        context += f"- {len(all_topics)} topics: {', '.join(t.name for t in all_topics)}\n"
        context += f"- {len(jurisdictions)} jurisdictions: {', '.join(j.name for j in jurisdictions)}\n"
        context += f"- {len(pd_works)} works in the public domain\n"
        context += f"- {len(copyrighted_works)} copyrighted works\n\n"
        
        return context
    except Exception as e:
        logger.error(f"Error generating DB stats context: {e}", exc_info=True)
        return "DATABASE STATISTICS: Unable to retrieve database statistics.\n\n"

def find_related_works(question: str, limit: int = 3) -> List[Work]:
    """
    Find works related to the user's question.
    Uses advanced extraction techniques to identify work titles.
    """
    try:
        # Strategy 1: Identify possible work titles in quotes (single or double)
        possible_titles = re.findall(r'"([^"]+)"|\'([^\']+)\'', question)
        # Flatten the tuple results and filter empty strings
        possible_titles = [next(t for t in title if t) for title in possible_titles if any(t for t in title)]
        
        # Strategy 2: Look for capitalized phrases that might be titles
        # This regular expression finds sequences of words where each word starts with a capital letter
        cap_phrases = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', question)
        
        # Strategy 3: Look for titles with "The", "A", "An" at the beginning
        articles_titles = re.findall(r'\b((?:The|A|An)\s+[A-Z][a-z]+(?:\s+[a-z]+){1,5})\b', question, re.IGNORECASE)
        
        # Strategy 4: Look for known literary work patterns (e.g., common formats like "Title: Subtitle")
        lit_patterns = re.findall(r'\b([A-Z][a-z]+(?:\s+[a-z]+){1,3}:\s+[A-Z][a-z]+(?:\s+[a-z]+){1,3})\b', question)
        
        # Combine all potential titles and remove duplicates
        all_potential_titles = list(set(possible_titles + cap_phrases + articles_titles + lit_patterns))
        
        logger.debug(f"Potential work titles extracted: {all_potential_titles}")
        
        works = []
        
        # Try exact title matches first
        if all_potential_titles:
            for title in all_potential_titles:
                work = database.get_work_by_title(title)
                if work:
                    works.append(work)
                    logger.debug(f"Found exact title match: '{title}'")
        
        # If we didn't find any exact matches, try substring matches
        if not works and all_potential_titles:
            potential_title_parts = [title.lower() for title in all_potential_titles]
            
            # Get all works and filter by title substring matches
            all_works = database.get_all_works()
            for work in all_works:
                work_title_lower = work.title.lower()
                if any(part in work_title_lower for part in potential_title_parts):
                    works.append(work)
                    logger.debug(f"Found partial title match: '{work.title}'")
                    if len(works) >= limit:
                        break
        
        # If we still don't have matches, fall back to general search
        if not works:
            logger.debug(f"No title matches found, falling back to general search")
            works = database.search_works(question, limit=limit)
            
        return works[:limit]  # Ensure we don't exceed the limit
    except Exception as e:
        logger.error(f"Error finding related works: {e}", exc_info=True)
        return []

def find_related_authors(question: str, limit: int = 3) -> List[Author]:
    """
    Find authors related to the user's question.
    Uses simple keyword searching for now.
    """
    try:
        # Look for author name patterns (e.g., First Last)
        possible_authors = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b', question)
        
        authors = []
        
        # Try searching for each possible author name
        if possible_authors:
            for name in possible_authors:
                # Search for authors by name
                matched_authors = database.search_authors(name, limit=1)
                if matched_authors:
                    authors.extend(matched_authors)
        
        # If we didn't find any specific authors, fall back to general search
        if not authors:
            authors = database.search_authors(question, limit=limit)
            
        return authors
    except Exception as e:
        logger.error(f"Error finding related authors: {e}", exc_info=True)
        return []

def find_jurisdictions(question: str) -> List[Jurisdiction]:
    """
    Find jurisdictions mentioned in the question.
    """
    try:
        jurisdictions = database.get_all_jurisdictions()
        mentioned_jurisdictions = []
        
        # Check for jurisdiction names or codes in the question
        for jur in jurisdictions:
            if jur.name and jur.name.lower() in question.lower():
                mentioned_jurisdictions.append(jur)
            elif jur.code and jur.code.lower() in question.lower():
                mentioned_jurisdictions.append(jur)
        
        return mentioned_jurisdictions
    except Exception as e:
        logger.error(f"Error finding jurisdictions: {e}", exc_info=True)
        return []

def format_work_for_context(work: Work) -> str:
    """Format a work object into a string for context."""
    try:
        today = get_current_date()
        
        authors = ", ".join(a.name for a in work.authors) if work.authors else "Unknown"
        topic = work.topic.name if work.topic else "Unknown"
        status = work.status or "Unknown"
        
        # Format creation and publication dates
        creation = work.creation_date.isoformat() if work.creation_date else "Unknown"
        publication = work.publication_date.isoformat() if work.publication_date else "Unknown"
        
        # Format expiry date with days remaining
        expiry = "N/A"
        days_left = "N/A"
        if work.copyright_expiry_date:
            expiry = work.copyright_expiry_date.isoformat()
            if work.copyright_expiry_date >= today:
                days_left = (work.copyright_expiry_date - today).days
        
        # Basic work info
        result = f"WORK: {work.title}\n"
        result += f"- Authors: {authors}\n"
        result += f"- Topic: {topic}\n"
        result += f"- Creation Date: {creation}\n"
        result += f"- Publication Date: {publication}\n"
        result += f"- Primary Status: {status}\n"
        result += f"- Copyright Expiry: {expiry}\n"
        result += f"- Days Until Expiry: {days_left}\n"
        
        # Add jurisdiction-specific status if available
        jurisdictions = database.get_all_jurisdictions()
        if work.id:
            result += "- Status by Jurisdiction:\n"
            for jurisdiction in jurisdictions:
                if jurisdiction.id:
                    status_info = database.get_work_copyright_status_by_jurisdiction(work.id, jurisdiction.id)
                    if status_info:
                        jur_status = status_info.get('status', 'Unknown')
                        jur_expiry = status_info.get('expiry_date', 'Unknown')
                        result += f"  - {jurisdiction.name}: {jur_status}, Expiry: {jur_expiry}\n"
        
        return result
    except Exception as e:
        logger.error(f"Error formatting work for context: {e}", exc_info=True)
        return f"WORK: {work.title} (Error formatting details)\n"

def format_author_for_context(author: Author) -> str:
    """Format an author object into a string for context."""
    try:
        birth = author.birth_date.isoformat() if author.birth_date else "Unknown"
        death = author.death_date.isoformat() if author.death_date else "Unknown"
        nationality = author.nationality if author.nationality else "Unknown"
        
        result = f"AUTHOR: {author.name}\n"
        result += f"- Birth Date: {birth}\n"
        result += f"- Death Date: {death}\n"
        result += f"- Nationality: {nationality}\n"
        
        # Add works by this author if available
        if author.id:
            works = database.get_works_by_author_id(author.id)
            if works:
                result += f"- Works ({len(works)}):\n"
                for work in works[:5]:  # Limit to 5 works
                    status = work.status or "Unknown"
                    expiry = work.copyright_expiry_date.isoformat() if work.copyright_expiry_date else "Unknown"
                    result += f"  - {work.title} (Status: {status}, Expiry: {expiry})\n"
                if len(works) > 5:
                    result += f"  - ...and {len(works) - 5} more works\n"
        
        return result
    except Exception as e:
        logger.error(f"Error formatting author for context: {e}", exc_info=True)
        return f"AUTHOR: {author.name} (Error formatting details)\n"

def format_jurisdiction_for_context(jurisdiction: Jurisdiction) -> str:
    """Format a jurisdiction object into a string for context."""
    try:
        result = f"JURISDICTION: {jurisdiction.name} ({jurisdiction.code})\n"
        result += f"- Copyright Term: life + {jurisdiction.term_years_after_death} years\n"
        
        if jurisdiction.has_special_rules:
            result += "- Has special copyright rules:\n"
            rules = database.get_copyright_rules_for_jurisdiction(jurisdiction.id)
            for rule in rules:
                result += f"  - {rule.rule_type}: {rule.term_years} years from {rule.base_date_type}\n"
                result += f"    {rule.description}\n"
        
        return result
    except Exception as e:
        logger.error(f"Error formatting jurisdiction for context: {e}", exc_info=True)
        return f"JURISDICTION: {jurisdiction.name} (Error formatting details)\n"

def get_upcoming_expirations_context(limit: int = 5) -> str:
    """Get context about upcoming copyright expirations."""
    try:
        today = get_current_date()
        expiring_works = database.get_next_expiring_works(current_date=today, limit=limit)
        
        if not expiring_works:
            return "UPCOMING EXPIRATIONS: No works expiring soon.\n\n"
        
        result = f"UPCOMING EXPIRATIONS (from {today.isoformat()}):\n"
        for work in expiring_works:
            authors = ", ".join(a.name for a in work.authors) if work.authors else "Unknown"
            expiry = work.copyright_expiry_date.isoformat() if work.copyright_expiry_date else "Unknown"
            days_left = (work.copyright_expiry_date - today).days if work.copyright_expiry_date else "Unknown"
            result += f"- {work.title} by {authors} expires on {expiry} ({days_left} days remaining)\n"
        
        return result + "\n"
    except Exception as e:
        logger.error(f"Error getting upcoming expirations context: {e}", exc_info=True)
        return "UPCOMING EXPIRATIONS: Error retrieving data.\n\n"

def generate_context_for_question(question: str) -> str:
    """
    Generate relevant context from the database based on the question.
    """
    logger.info(f"Generating context for question: '{question}'")
    
    context = "You are a copyright assistant providing information about works in our database.\n\n"
    
    # Add current date for context
    today = get_current_date()
    context += f"Current Date: {today.isoformat()}\n\n"
    
    # Find related works
    works = find_related_works(question, limit=3)
    if works:
        context += "--- RELEVANT WORKS ---\n"
        for work in works:
            context += format_work_for_context(work) + "\n"
    
    # Find related authors
    authors = find_related_authors(question, limit=3)
    if authors:
        context += "--- RELEVANT AUTHORS ---\n"
        for author in authors:
            context += format_author_for_context(author) + "\n"
    
    # Find related jurisdictions
    jurisdictions = find_jurisdictions(question)
    if jurisdictions:
        context += "--- RELEVANT JURISDICTIONS ---\n"
        for jurisdiction in jurisdictions:
            context += format_jurisdiction_for_context(jurisdiction) + "\n"
    
    # Check if the question is about upcoming expirations
    if "expir" in question.lower() or "upcoming" in question.lower() or "soon" in question.lower():
        context += get_upcoming_expirations_context(limit=5)
    
    # Add database statistics
    context += generate_db_stats_context()
    
    logger.info(f"Generated context with {len(context)} characters")
    return context

def rag_query(question: str) -> str:
    """
    Process a question using the RAG approach:
    1. Retrieve relevant context from the database
    2. Feed the context and question to the LLM
    3. Return the generated answer
    """
    try:
        logger.info(f"Processing RAG query: '{question}'")
        
        # Generate context based on the question
        context = generate_context_for_question(question)
        
        # Send to LLM for final answer
        answer = answer_query_with_context(question, context)
        
        return answer
    except Exception as e:
        logger.error(f"Error in RAG query processing: {e}", exc_info=True)
        return f"I encountered an error while retrieving information: {str(e)}"