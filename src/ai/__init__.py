"""
AI module for enhancing author rights data with Google Gemini API.

This module provides tools to interact with the Google Gemini API for:
1. Validating copyright status of works
2. Enriching author information (birth/death dates, nationality)
3. Categorizing works into appropriate topics
4. Processing batches of works efficiently
5. Answering user questions about copyright data
"""
import os
import logging
import time
from datetime import date, datetime
from typing import List, Dict, Any, Optional
import json

import google.generativeai as genai
from ..config import GEMINI_API_KEY, GEMINI_MODEL, BATCH_SIZE, API_RATE_LIMIT
from ..data_models import Work, Author, Topic

# Set up logging
logger = logging.getLogger(__name__)

# Initialize the Gemini API client
try:
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info(f"Initialized Google Generative AI with model: {GEMINI_MODEL}")
except Exception as e:
    logger.error(f"Failed to initialize Google Generative AI: {e}")

def enhance_work_with_llm(work: Work) -> Work:
    """
    Use Google Gemini to enhance a work with missing information.
    
    Args:
        work: The Work object to enhance
        
    Returns:
        Enhanced Work object with additional information
    """
    try:
        # Create a prompt with work info
        prompt = _create_work_prompt(work)
        
        # Call Gemini API
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        
        # Parse response and update work
        enhanced_work = _parse_llm_response(work, response.text)
        logger.info(f"Enhanced work: {enhanced_work.title}")
        return enhanced_work
    
    except Exception as e:
        logger.error(f"Error enhancing work '{work.title}' with LLM: {e}")
        return work

def enhance_author_with_llm(author: Author) -> Author:
    """
    Use Google Gemini to enhance author information.
    
    Args:
        author: The Author object to enhance
        
    Returns:
        Enhanced Author object with additional information
    """
    try:
        # Create a prompt with author info
        prompt = _create_author_prompt(author)
        
        # Call Gemini API
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        
        # Parse response and update author
        enhanced_author = _parse_author_response(author, response.text)
        logger.info(f"Enhanced author: {enhanced_author.name}")
        return enhanced_author
    
    except Exception as e:
        logger.error(f"Error enhancing author '{author.name}' with LLM: {e}")
        return author

def process_batch(works: List[Work]) -> List[Work]:
    """
    Process a batch of works with the LLM, respecting rate limits.
    
    Args:
        works: List of Work objects to enhance
        
    Returns:
        List of enhanced Work objects
    """
    enhanced_works = []
    
    for i, work in enumerate(works):
        logger.info(f"Processing work {i+1}/{len(works)}: {work.title}")
        
        # Enhance the work
        enhanced_work = enhance_work_with_llm(work)
        enhanced_works.append(enhanced_work)
        
        # Respect API rate limits
        if i < len(works) - 1:  # Don't wait after the last item
            sleep_time = 60 / API_RATE_LIMIT
            logger.debug(f"Waiting {sleep_time:.2f} seconds for rate limiting")
            time.sleep(sleep_time)
    
    return enhanced_works

def verify_copyright_status(work: Work) -> Dict[str, str]:
    """
    Verify the copyright status of a work across multiple jurisdictions.
    
    Args:
        work: The Work object to verify
        
    Returns:
        Dictionary mapping jurisdiction codes to status values
    """
    try:
        # Create a prompt focused on copyright status
        prompt = _create_copyright_prompt(work)
        
        # Call Gemini API
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        
        # Parse response for copyright status
        status_by_jurisdiction = _parse_copyright_response(response.text)
        logger.info(f"Verified copyright status for: {work.title}")
        return status_by_jurisdiction
    
    except Exception as e:
        logger.error(f"Error verifying copyright status for '{work.title}': {e}")
        return {}

def _create_work_prompt(work: Work) -> str:
    """Create a detailed prompt for work enhancement."""
    author_info = ""
    for author in work.authors:
        birth = f", born: {author.birth_date}" if author.birth_date else ""
        death = f", died: {author.death_date}" if author.death_date else ""
        nationality = f", nationality: {author.nationality}" if author.nationality else ""
        author_info += f"- {author.name}{birth}{death}{nationality}\n"
    
    topic = work.topic.name if work.topic else "Unknown"
    creation_date = work.creation_date.isoformat() if work.creation_date else "Unknown"
    pub_date = work.first_publication_date.isoformat() if work.first_publication_date else "Unknown"
    
    return f"""
Given this partial information about a creative work:

Title: {work.title}
Author(s): 
{author_info}
Topic/Category: {topic}
Creation date: {creation_date}
First publication date: {pub_date}
Copyright status: {work.status}

Please analyze and provide:
1. Complete author information (birth date, death date, nationality) for any missing details
2. Verification of copyright status across major jurisdictions (US, EU, UK, Canada, Japan)
3. Proper categorization if not already specified
4. Any missing dates or details

Respond with ONLY a valid JSON object containing:
{{
  "authors": [
    {{
      "name": "Author Name",
      "birth_date": "YYYY-MM-DD",
      "death_date": "YYYY-MM-DD",
      "nationality": "Country Code"
    }}
  ],
  "topic": "Best category",
  "creation_date": "YYYY-MM-DD",
  "first_publication_date": "YYYY-MM-DD",
  "copyright_status": {{
    "US": "Copyrighted or Public Domain",
    "EU": "Copyrighted or Public Domain",
    "UK": "Copyrighted or Public Domain",
    "CA": "Copyrighted or Public Domain",
    "JP": "Copyrighted or Public Domain"
  }}
}}

DO NOT include explanations, just the JSON object. Use null for unknown values.
"""

def _create_author_prompt(author: Author) -> str:
    """Create a detailed prompt for author information enhancement."""
    birth = f", born: {author.birth_date}" if author.birth_date else ""
    death = f", died: {author.death_date}" if author.death_date else ""
    nationality = f", nationality: {author.nationality}" if author.nationality else ""
    
    return f"""
Given this partial information about an author:

Name: {author.name}{birth}{death}{nationality}

Please research and provide complete biographical details:
1. Birth date (specific day if possible, otherwise year)
2. Death date (if applicable)
3. Nationality/country of origin
4. Other relevant details (keep it brief)

Respond with ONLY a valid JSON object containing:
{{
  "name": "Author's full name",
  "birth_date": "YYYY-MM-DD",
  "death_date": "YYYY-MM-DD or null if still alive",
  "nationality": "Country Code",
  "notable_works": ["Work 1", "Work 2"]
}}

DO NOT include explanations, just the JSON object. Use null for unknown values.
"""

def _create_copyright_prompt(work: Work) -> str:
    """Create a detailed prompt focused on copyright status."""
    author_info = ""
    for author in work.authors:
        birth = f", born: {author.birth_date}" if author.birth_date else ""
        death = f", died: {author.death_date}" if author.death_date else ""
        nationality = f", nationality: {author.nationality}" if author.nationality else ""
        author_info += f"- {author.name}{birth}{death}{nationality}\n"
    
    creation_date = work.creation_date.isoformat() if work.creation_date else "Unknown"
    pub_date = work.first_publication_date.isoformat() if work.first_publication_date else "Unknown"
    
    return f"""
Determine the copyright status of the following work across different jurisdictions.

Work: {work.title}
Author(s): 
{author_info}
Creation date: {creation_date}
First publication date: {pub_date}
Current status: {work.status}

Today's date: {date.today().isoformat()}

Please analyze the copyright status in:
1. United States (US)
2. European Union (EU)
3. United Kingdom (UK)
4. Canada (CA)
5. Japan (JP)
6. Mexico (MX)

Consider these copyright rules:
- US: Life + 70 years; works published before 1927 are in public domain
- EU: Life + 70 years
- UK: Life + 70 years
- Canada: Life + 50 years
- Japan: Life + 70 years
- Mexico: Life + 100 years

Respond with ONLY a valid JSON object:
{{
  "copyright_status": {{
    "US": "Copyrighted or Public Domain",
    "EU": "Copyrighted or Public Domain",
    "UK": "Copyrighted or Public Domain",
    "CA": "Copyrighted or Public Domain",
    "JP": "Copyrighted or Public Domain",
    "MX": "Copyrighted or Public Domain"
  }},
  "reasoning": {{
    "US": "Brief explanation",
    "EU": "Brief explanation",
    "UK": "Brief explanation",
    "CA": "Brief explanation",
    "JP": "Brief explanation",
    "MX": "Brief explanation"
  }}
}}

DO NOT include explanations outside the JSON, just the JSON object.
"""

def _parse_llm_response(work: Work, response_text: str) -> Work:
    """Parse LLM response and update work with enhanced information."""
    try:
        # Extract JSON from response (in case the LLM added any extra text)
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            logger.warning(f"Failed to find JSON in response: {response_text}")
            return work
        
        json_str = response_text[json_start:json_end]
        data = json.loads(json_str)
        
        # Update work with enhanced information
        if "authors" in data and data["authors"]:
            for i, author_data in enumerate(data["authors"]):
                if i < len(work.authors):
                    # Update existing authors
                    if "birth_date" in author_data and author_data["birth_date"] and not work.authors[i].birth_date:
                        try:
                            work.authors[i].birth_date = date.fromisoformat(author_data["birth_date"])
                        except ValueError:
                            logger.warning(f"Invalid birth date format: {author_data['birth_date']}")
                    
                    if "death_date" in author_data and author_data["death_date"] and not work.authors[i].death_date:
                        try:
                            if author_data["death_date"] and author_data["death_date"].lower() != "null":
                                work.authors[i].death_date = date.fromisoformat(author_data["death_date"])
                        except ValueError:
                            logger.warning(f"Invalid death date format: {author_data['death_date']}")
                    
                    if "nationality" in author_data and author_data["nationality"] and not work.authors[i].nationality:
                        work.authors[i].nationality = author_data["nationality"]
        
        # Update topic if provided
        if "topic" in data and data["topic"] and not work.topic:
            # Note: This only sets the name, the actual Topic object should be
            # retrieved or created in the database before saving
            work.topic = Topic(name=data["topic"])
        
        # Update dates if provided
        if "creation_date" in data and data["creation_date"] and not work.creation_date:
            try:
                work.creation_date = date.fromisoformat(data["creation_date"])
            except ValueError:
                logger.warning(f"Invalid creation date format: {data['creation_date']}")
        
        if "first_publication_date" in data and data["first_publication_date"] and not work.first_publication_date:
            try:
                work.first_publication_date = date.fromisoformat(data["first_publication_date"])
            except ValueError:
                logger.warning(f"Invalid publication date format: {data['first_publication_date']}")
        
        # Update copyright status by jurisdiction
        if "copyright_status" in data and isinstance(data["copyright_status"], dict):
            for jur_code, status in data["copyright_status"].items():
                if jur_code and status:
                    work.status_by_jurisdiction[jur_code] = status
        
        return work
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from response: {e}")
        logger.debug(f"Response text: {response_text}")
        return work
    except Exception as e:
        logger.error(f"Error parsing LLM response: {e}")
        return work

def _parse_author_response(author: Author, response_text: str) -> Author:
    """Parse LLM response and update author with enhanced information."""
    try:
        # Extract JSON from response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            logger.warning(f"Failed to find JSON in response: {response_text}")
            return author
        
        json_str = response_text[json_start:json_end]
        data = json.loads(json_str)
        
        # Update author with enhanced information
        if "birth_date" in data and data["birth_date"] and not author.birth_date:
            try:
                author.birth_date = date.fromisoformat(data["birth_date"])
            except ValueError:
                logger.warning(f"Invalid birth date format: {data['birth_date']}")
        
        if "death_date" in data and data["death_date"] and not author.death_date:
            try:
                if data["death_date"] and data["death_date"].lower() != "null":
                    author.death_date = date.fromisoformat(data["death_date"])
            except ValueError:
                logger.warning(f"Invalid death date format: {data['death_date']}")
        
        if "nationality" in data and data["nationality"] and not author.nationality:
            author.nationality = data["nationality"]
        
        return author
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from response: {e}")
        return author
    except Exception as e:
        logger.error(f"Error parsing author response: {e}")
        return author

def _parse_copyright_response(response_text: str) -> Dict[str, str]:
    """Parse copyright status response from LLM."""
    try:
        # Extract JSON from response
        json_start = response_text.find('{')
        json_end = response_text.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            logger.warning(f"Failed to find JSON in response: {response_text}")
            return {}
        
        json_str = response_text[json_start:json_end]
        data = json.loads(json_str)
        
        # Extract copyright status by jurisdiction
        if "copyright_status" in data and isinstance(data["copyright_status"], dict):
            return data["copyright_status"]
        
        return {}
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from response: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error parsing copyright response: {e}")
        return {}

def query_llm(prompt: str) -> str:
    """
    Generic function to query the LLM with any prompt.
    
    Args:
        prompt: The prompt to send to the LLM
        
    Returns:
        String response from the LLM
    """
    try:
        # Call Gemini API
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        
        # Rate limiting
        sleep_time = 60 / API_RATE_LIMIT
        time.sleep(sleep_time)
        
        return response.text
    except Exception as e:
        logger.error(f"Error querying LLM: {e}")
        return f"Error: {str(e)}"

def answer_query_with_context(question: str, context: str = "") -> str:
    """
    Answer a user's question using the provided context.
    
    Args:
        question: The user's question
        context: Contextual information to help answer the question
        
    Returns:
        The AI's response
    """
    logger.info(f"Answering query with {len(context)} chars of context")
    
    # Apply rate limiting
    _rate_limit()
    
    # Create a prompt that includes both the question and context
    prompt = f"""You are a helpful copyright and public domain assistant. Answer the following question 
based ONLY on the context provided below. If the context doesn't contain enough information to answer
completely, acknowledge what you know and what you don't.

CURRENT CONTEXT:
{context}

USER QUESTION: {question}

Please provide a clear, concise answer using only the information in the context above.
If you can't find the answer to any part of the question in the context, say so clearly.
Do not make up information that isn't in the context.
"""
    
    # Call the general query function with our constructed prompt
    try:
        response = query_llm(prompt)
        return response
    except Exception as e:
        logger.error(f"Error answering query with context: {e}", exc_info=True)
        return f"I encountered an error when trying to answer your question: {str(e)}"

# Rate limiting helper function
def _rate_limit():
    """Apply rate limiting for API calls."""
    global _last_api_call_time
    
    if not hasattr(_rate_limit, "_last_api_call_time"):
        _rate_limit._last_api_call_time = 0
        
    if API_RATE_LIMIT > 0:
        now = time.time()
        elapsed = now - _rate_limit._last_api_call_time
        wait_time = (60.0 / API_RATE_LIMIT) - elapsed
        
        if wait_time > 0:
            logger.debug(f"Rate limiting: waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)
            
        _rate_limit._last_api_call_time = time.time()