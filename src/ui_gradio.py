import gradio as gr
import pandas as pd
from datetime import date, datetime

import logging
import sys
import os
import random # For showing random examples
import json # For LLM context

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import necessary project modules
from src import database
from src import scheduler
from src import ai_manager
from src import populate_db
from src.scraper.spiders import gutenberg_spider
from src.data_models import Work, Author, Topic, Jurisdiction # Import necessary models
from src.ai import answer_query_with_context # Import the AI function for querying
from .date_provider import get_current_date

# --- Setup ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gradio_ui")

# Ensure database is initialized when UI starts
try:
    database.init_db()
    database.initialize_default_jurisdictions()
    logger.info("Database initialized for UI.")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}", exc_info=True)
    # Optionally raise or handle this error to prevent UI launch if DB fails

# --- UI Helper Functions ---

def format_works_for_display(works: list[Work]) -> pd.DataFrame:
    """Formats a list of Work objects into a Pandas DataFrame for Gradio."""
    columns = ["ID", "Title", "Authors", "Topic", "Status", "Expiry Date", "Days Remaining"]
    if not works:
        return pd.DataFrame(columns=columns)

    data = []
    today = get_current_date() # Get current date for calculating days remaining
    for work in works:
        authors = ", ".join(a.name for a in work.authors) if work.authors else "Unknown"
        topic = work.topic.name if work.topic else "N/A"
        status = work.status if work.status else "Unknown"
        expiry = work.copyright_expiry_date.isoformat() if work.copyright_expiry_date else "N/A"
        
        # Calculate days remaining
        days_left = None
        if work.copyright_expiry_date and work.copyright_expiry_date >= today:
            days_left = (work.copyright_expiry_date - today).days
        days_remaining_str = str(days_left) if days_left is not None else "N/A"

        data.append([work.id, work.title, authors, topic, status, expiry, days_remaining_str])

    return pd.DataFrame(data, columns=columns)

def format_authors_for_display(authors: list[Author]) -> pd.DataFrame:
    """Formats a list of Author objects into a Pandas DataFrame."""
    if not authors:
        return pd.DataFrame(columns=["ID", "Name", "Birth Date", "Death Date", "Nationality"])

    data = []
    for author in authors:
        birth = author.birth_date.isoformat() if author.birth_date else "N/A"
        death = author.death_date.isoformat() if author.death_date else "N/A"
        nat = author.nationality if author.nationality else "N/A"
        data.append([author.id, author.name, birth, death, nat])

    return pd.DataFrame(data, columns=["ID", "Name", "Birth Date", "Death Date", "Nationality"])

def format_topics_for_display(topics: list[Topic]) -> pd.DataFrame:
    """Formats a list of Topic objects into a Pandas DataFrame."""
    if not topics:
        return pd.DataFrame(columns=["ID", "Name"])
    data = [[topic.id, topic.name] for topic in topics]
    return pd.DataFrame(data, columns=["ID", "Name"])

def search_works_ui(query: str):
    """UI wrapper for searching works."""
    logger.info(f"UI: Searching works for '{query}'")
    if not query:
        return pd.DataFrame(), "Please enter a search query."
    try:
        results = database.search_works(query)
        if not results:
             return pd.DataFrame(), f"No works found matching '{query}'. Database might be empty or lack relevant entries."
        logger.info(f"UI: Found {len(results)} works for query '{query}'")
        return format_works_for_display(results), f"Found {len(results)} works."
    except Exception as e:
        logger.error(f"UI Search Error: {e}", exc_info=True)
        return pd.DataFrame(), f"Error during search: {e}"

def search_authors_ui(query: str):
    """UI wrapper for searching authors.
       Returns: DataFrame for display, status message, DataFrame for state."""
    logger.info(f"UI: Searching authors for '{query}'")
    empty_df = pd.DataFrame(columns=["ID", "Name", "Birth Date", "Death Date", "Nationality"]) # Define empty structure
    try:
        results = database.search_authors(query) # This returns List[Author]
        if not results:
             # Return empty DF for display, message, and empty DF for state
             return empty_df, f"No authors found matching '{query}'.", empty_df
        # Pass List[Author] to formatter
        authors_df = format_authors_for_display(results)
        # Return DF for display, message, and DF for state
        return authors_df, f"Found {len(results)} authors for query '{query}'.", authors_df
    except Exception as e:
        logger.error(f"UI Author Search Error: {e}", exc_info=True)
        # Return empty DF for display, error message, and empty DF for state
        return empty_df, f"Error searching authors: {e}", empty_df

def get_all_topics_ui():
    """UI wrapper to get all topics."""
    logger.info("UI: Getting all topics")
    try:
        results = database.get_all_topics()
        if not results:
             # Return an empty DataFrame instead of None
             return pd.DataFrame(columns=["ID", "Name"]), "No topics found in the database."
        return format_topics_for_display(results), f"Found {len(results)} topics."
    except Exception as e:
        logger.error(f"UI Topics Error: {e}", exc_info=True)
        # Return an empty DataFrame on error
        return pd.DataFrame(columns=["ID", "Name"]), f"Error retrieving topics: {e}"

def get_work_details_ui(evt: gr.SelectData, works_df: pd.DataFrame): # Modified signature
    """UI wrapper to get detailed information about a specific work."""
    if not evt.selected: # Check if a row is actually selected
        return "Select a work to view details.", -1 # Return -1 for invalid ID

    selected_index = evt.index[0] # Get the row index
    try:
        # Assuming 'ID' is the first column (index 0)
        work_id = int(works_df.iloc[selected_index, 0])
    except (IndexError, KeyError, ValueError):
         return "Could not retrieve selected work ID.", -1 # Return -1 for invalid ID

    logger.info(f"UI: Getting details for work ID {work_id}")

    try:
        work = database.get_work_by_id(work_id)
        if not work:
            return "Work not found.", work_id # Return ID even if not found

        # Build detailed information
        details_md = f"# {work.title}\n\n"

        # Authors section
        details_md += "## Authors\n"
        if work.authors:
            for author in work.authors:
                birth = f" (Born: {author.birth_date})" if author.birth_date else ""
                death = f" (Died: {author.death_date})" if author.death_date else ""
                nationality = f", {author.nationality}" if author.nationality else ""
                details_md += f"- **{author.name}**{birth}{death}{nationality}\n"
        else:
            details_md += "- Unknown\n"

        # Basic info section
        details_md += "\n## Publication Details\n"
        details_md += f"- **Topic:** {work.topic.name if work.topic else 'Unknown'}\n"
        details_md += f"- **Creation Date:** {work.creation_date or 'Unknown'}\n"
        details_md += f"- **First Publication:** {work.first_publication_date or 'Unknown'}\n"
        details_md += f"- **Primary Status:** {work.status or 'Unknown'}\n"
        details_md += f"- **Copyright Expiry:** {work.copyright_expiry_date or 'Unknown'}\n"

        if work.description:
            details_md += f"\n## Description\n{work.description}\n"

        # Get jurisdiction-specific status
        details_md += "\n## Status by Jurisdiction\n"
        jurisdictions = database.get_all_jurisdictions()

        for jurisdiction in jurisdictions:
            if not jurisdiction.id or not jurisdiction.code:
                continue # Skip if jurisdiction info is incomplete

            status_info = database.get_work_copyright_status_by_jurisdiction(work.id, jurisdiction.id)
            status = status_info.get('status', 'Unknown') if status_info else 'Unknown'
            expiry = status_info.get('expiry_date', 'Unknown') if status_info else 'Unknown'

            term_desc = f"life + {jurisdiction.term_years_after_death} years"
            if jurisdiction.has_special_rules:
                term_desc += " (with special rules)" # Indicate special rules

            details_md += f"### {jurisdiction.name} ({term_desc})\n"
            details_md += f"- **Status:** {status}\n"
            details_md += f"- **Expiry Date:** {expiry}\n"

        # Return details and the valid work_id
        return details_md, work_id
    except Exception as e:
        logger.error(f"UI Work Details Error: {e}", exc_info=True)
        # Return error message and the potentially valid ID
        return f"Error retrieving work details: {e}", work_id

def get_works_by_topic_ui(evt, topics_df):
    """UI wrapper to get works for a specific topic ID."""
    try:
        # Check if topics_df is None or not a DataFrame or empty
        if topics_df is None or not isinstance(topics_df, pd.DataFrame) or topics_df.empty:
             logger.warning("UI: get_works_by_topic_ui called with invalid or empty topics_df.")
             return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), "Topic data is not available. Cannot load works."
        
        # Check if the event is valid (not None or empty)
        if evt is None or not hasattr(evt, 'index') or not evt.index:
             return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), "Select a topic to view works."
        
        # Get the selected row index
        selected_index = evt.index[0]
        
        # Get the topic ID from the first column of the selected row
        try:
            # Check index bounds
            if selected_index >= len(topics_df):
                 logger.warning(f"UI: Selected index {selected_index} out of bounds for topics_df with length {len(topics_df)}.")
                 return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), "Invalid selection index."
                 
            topic_id = int(topics_df.iloc[selected_index, 0])
        except (IndexError, ValueError, TypeError) as e:
             logger.error(f"UI: Error retrieving topic ID from selection. Index: {selected_index}, Df shape: {topics_df.shape}. Error: {e}", exc_info=True)
             return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), "Could not retrieve topic ID from selection."
        
        logger.info(f"UI: Getting works for topic ID {topic_id}")
        
        # Fetch topic name for context
        topic = database.get_topic_by_id(topic_id)
        if not topic:
             logger.warning(f"UI: Could not find topic with ID {topic_id}")
             return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), f"Topic with ID {topic_id} not found."
             
        topic_name = topic.name
        
        # Get works for the topic name - FIXED: using get_works_by_topic instead of get_works_by_topic_id
        results = database.get_works_by_topic(topic_name)
        
        # Check if results is None or empty list
        if results is None or len(results) == 0:
             return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), f"No works found for topic '{topic_name}'."
        
        # Format and return works
        return format_works_for_display(results), f"Found {len(results)} works for topic '{topic_name}'."
    except Exception as e:
        logger.error(f"UI Works by Topic Error: {e}", exc_info=True)
        return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), f"Error retrieving works for topic: {e}"
    
def get_works_by_author_ui(evt, authors_df):
    """UI wrapper to get works for a specific author ID."""
    try:
        # Check if the event is valid (not None or empty)
        if evt is None or not hasattr(evt, 'index'):
            return pd.DataFrame(), "Select an author to view their works."
            
        # Get the selected row index
        selected_index = evt.index[0]
        
        # Get the author ID from the first column of the selected row
        try:
            author_id = int(authors_df.iloc[selected_index, 0])
        except (IndexError, ValueError):
            return pd.DataFrame(), "Could not retrieve author ID from selection."
            
        logger.info(f"UI: Getting works for author ID {author_id}")
        
        # Fetch author name for context
        author = database.get_author_by_id(author_id)
        author_name = author.name if author else f"ID {author_id}"
        
        # Get works for the author ID
        results = database.get_works_by_author_id(author_id)
        
        # Check if results is None or empty list
        if results is None or len(results) == 0:
            return pd.DataFrame(), f"No works found for author '{author_name}'."
            
        # Format and return works
        return format_works_for_display(results), f"Found {len(results)} works for author '{author_name}'."
    except Exception as e:
        logger.error(f"UI Works by Author Error: {e}", exc_info=True)
        return pd.DataFrame(), f"Error retrieving works for author: {e}"

def get_ai_analysis_for_work(work_id): # Remove type hint for debugging
    """Generate AI analysis for a specific work ID."""
    # --- DEBUGGING ---
    logger.info(f"UI: Entering get_ai_analysis_for_work. Received argument type: {type(work_id)}")
    logger.info(f"UI: Received argument value: {repr(work_id)}") # Use repr for detailed value
    # --- END DEBUGGING ---

    # --- Robust ID Check ---
    actual_work_id = None
    if isinstance(work_id, int):
        actual_work_id = work_id
    elif isinstance(work_id, float): # Gradio might pass Number state as float
        actual_work_id = int(work_id)
    # Add checks for other potential types if necessary based on logs
    # elif hasattr(work_id, 'value'): # Check if the state object itself was passed
    #    if isinstance(work_id.value, (int, float)):
    #        actual_work_id = int(work_id.value)

    if actual_work_id is None:
        logger.error(f"UI: Could not determine a valid integer work ID from input. Type: {type(work_id)}, Value: {repr(work_id)}")
        return "Error: Could not identify the selected work ID. Please try selecting the work again."
    # --- End Robust ID Check ---

    logger.info(f"UI: Processing AI analysis for integer work ID {actual_work_id}") # Log the final ID used

    # Check if a valid work ID was passed (using the validated integer ID)
    if actual_work_id < 0: # Check for the -1 placeholder
        return "Please select a valid work from the table first."

    try:
        # Ensure API key is configured
        ai_manager.validate_gemini_api_key()

        # Get work details using the validated integer ID
        work = database.get_work_by_id(actual_work_id)
        if not work:
            # Use the validated integer ID in the error message
            return f"Work with ID {actual_work_id} not found."

        # Generate prompt about this specific work
        prompt = f"Analyze the copyright status of '{work.title}' in different jurisdictions. "

        if work.authors:
            authors_str = ", ".join(a.name for a in work.authors)
            prompt += f"Created by {authors_str}. "

            # --- Initialize death_dates list ---
            death_dates = []
            # --- END Initialize death_dates list ---
            for author in work.authors:
                 if author.death_date:
                    death_dates.append(f"{author.name} died on {author.death_date}")

            if death_dates:
                 prompt += f"{', '.join(death_dates)}. "

        if work.creation_date:
            prompt += f"Created on {work.creation_date}. "

        prompt += "Explain when this work will enter the public domain in different countries, and any special considerations."

        # Get the analysis using the general AI function
        # Pass the generated prompt string to ask_ai_about_data
        analysis = ask_ai_about_data(prompt)
        return analysis

    except Exception as e:
        logger.error(f"UI Work Analysis Error: {e}", exc_info=True)
        return f"Error generating analysis for work ID {actual_work_id}: {e}"

# --- Report Functions ---
def get_upcoming_expirations_ui():
    """UI wrapper for displaying the nearest upcoming expirations."""
    logger.info("UI: Getting nearest upcoming expirations")
    try:
        today = get_current_date()
        limit = 20  # Show the nearest 20 expirations

        # Get the nearest works expiring on or after today, without upper date limit
        expiring_works = database.get_next_expiring_works(current_date=today, limit=limit)

        if not expiring_works:
            return pd.DataFrame(), f"No upcoming copyright expirations found from {today.isoformat()} onwards."

        # Format for display
        df_display = format_works_for_display(expiring_works)
        
        return df_display, f"Showing the {len(expiring_works)} nearest upcoming copyright expirations from {today.isoformat()} onwards."
    except Exception as e:
        logger.error(f"UI Expiry Report Error: {e}", exc_info=True)
        return pd.DataFrame(), f"Error generating report: {e}"

def get_public_domain_ui():
    """UI wrapper for displaying public domain works."""
    logger.info("UI: Getting public domain works")
    try:
        pd_works = database.get_public_domain_works()
        if not pd_works:
             return pd.DataFrame(), "No works found marked as Public Domain (primary status). Database might be empty or works haven't been processed."
        return format_works_for_display(pd_works), f"Found {len(pd_works)} public domain works."
    except Exception as e:
        logger.error(f"UI PD Report Error: {e}", exc_info=True)
        return pd.DataFrame(), f"Error generating report: {e}"

def get_international_status_ui():
    """UI wrapper for displaying international status."""
    logger.info("UI: Getting international status")
    try:
        all_works = database.get_all_works()
        jurisdictions = database.get_all_jurisdictions()

        if not all_works:
            return "Database is empty. Please add works via the 'Data Management' tab first."
        if not jurisdictions:
             return "No jurisdictions found in the database."

        report_md = "## International Copyright Status\n\n"
        current_date = date.today()

        for jurisdiction in jurisdictions:
            if not jurisdiction.id or not jurisdiction.code: continue

            term_desc = f"life + {jurisdiction.term_years_after_death} years"
            if jurisdiction.has_special_rules:
                term_desc += " (with special rules)"

            report_md += f"### {jurisdiction.name} ({term_desc})\n"

            pd_in_jur = []
            for work in all_works:
                if not work.id: continue
                status_info = database.get_work_copyright_status_by_jurisdiction(work.id, jurisdiction.id)
                status = status_info.get('status', 'Unknown') if status_info else 'Unknown'
                if status == 'Public Domain':
                    authors = ", ".join(a.name for a in work.authors) if work.authors else "Unknown"
                    pd_in_jur.append(f"- {work.title} (by {authors})")

            if pd_in_jur:
                report_md += "**Public Domain Works:**\n" + "\n".join(sorted(pd_in_jur)) + "\n\n"
            else:
                report_md += "*No works found in Public Domain for this jurisdiction.*\n\n"

        return report_md
    except Exception as e:
        logger.error(f"UI International Report Error: {e}", exc_info=True)
        return f"Error generating international report: {e}"

# --- Dashboard Function ---
def get_dashboard_info():
    """Checks the database and returns status info and highlights."""
    try:
        all_works = database.get_all_works()
        count = len(all_works)
        status_md = f"## Copyright Database Overview\n\n"
        status_md += f"The database contains **{count}** creative works.\n\n"

        # Get statistics
        topics = database.get_all_topics()
        authors = database.get_all_authors()
        jurisdictions = database.get_all_jurisdictions()

        # Create statistics chart
        status_md += "### Statistics\n"
        status_md += f"- **Works:** {count}\n"
        status_md += f"- **Authors:** {len(authors)}\n"
        status_md += f"- **Topics:** {len(topics)}\n"
        status_md += f"- **Jurisdictions:** {len(jurisdictions)}\n\n"

        # Get work status distribution
        pd_works = [w for w in all_works if w.status == "Public Domain"]
        copyrighted_works = [w for w in all_works if w.status == "Copyrighted"]
        unknown_works = [w for w in all_works if w.status not in ["Public Domain", "Copyrighted"]]

        status_md += "### Copyright Status Distribution\n"
        status_md += f"- **Public Domain:** {len(pd_works)} works\n"
        status_md += f"- **Copyrighted:** {len(copyrighted_works)} works\n"
        status_md += f"- **Unknown Status:** {len(unknown_works)} works\n\n"

        # Create empty DataFrames for highlights
        expiring_soon_df = pd.DataFrame()
        pd_works_df = pd.DataFrame()

        if count == 0:
            status_md += "**Note:** Database is currently empty. Use the **Data Management** tab to add works."
        else:
            status_md += "### Explore the Database\n"
            status_md += "- Use the **Browse Works** tab to search across all works\n"
            status_md += "- Use the **Browse Authors** tab to find works by specific authors\n"
            status_md += "- Use the **Browse Topics** tab to explore works by category\n"
            status_md += "- Check the **Reports** tab for copyright summaries\n"
            status_md += "- Use the **Ask AI** tab for help interpreting copyright information\n\n"

            # Get expiring soon works
            today = date.today()
            one_year_later = date(today.year + 1, today.month, today.day)
            expiring_works = database.get_works_nearing_expiry(one_year_later)

            if expiring_works:
                expiring_works.sort(key=lambda w: w.copyright_expiry_date or date.max)
                expiring_soon_df = format_works_for_display(expiring_works[:5]) # Show top 5

                status_md += "### 🚨 Works Expiring Soon\n"
                status_md += f"There are **{len(expiring_works)}** works set to enter the public domain within the next year.\n"
                status_md += "*Check the table below for details.*\n\n"

            # Get some PD works
            if pd_works:
                pd_sample = random.sample(pd_works, min(len(pd_works), 5)) # Show 5 random
                pd_works_df = format_works_for_display(pd_sample)

                status_md += "### ✅ Public Domain Works\n"
                status_md += f"There are **{len(pd_works)}** works already in the public domain.\n"
                status_md += "*Check the table below for a sample of these works.*\n"

        return status_md, expiring_soon_df, pd_works_df

    except Exception as e:
        logger.error(f"Error getting dashboard info: {e}", exc_info=True)
        return f"Error checking database status: {e}", pd.DataFrame(), pd.DataFrame()

# --- AI Assistant Function ---
def ask_ai_about_data(question: str):
    """Handles user questions, gathers context, and queries the LLM using RAG."""
    logger.info(f"UI: AI Question Received: '{question}'")
    if not question:
        return "Please ask a question about copyright, author rights, or works in the database."

    try:
        # Ensure API key is configured
        ai_manager.validate_gemini_api_key()

        # Import db_rag module here to avoid circular imports
        from . import db_rag
        
        # Use the RAG query system to get an answer with database context
        answer = db_rag.rag_query(question)
        return answer

    except Exception as e:
        logger.error(f"UI Ask AI Error: {e}", exc_info=True)
        # Fallback to a basic answer if RAG fails
        try:
            # Create minimal context with just the date
            minimal_context = f"You are a copyright assistant. Current date: {get_current_date().isoformat()}"
            fallback_answer = ai_manager.answer_query_with_context(question, minimal_context)
            return f"(Error retrieving database context) {fallback_answer}"
        except Exception as ai_err:
            logger.error(f"UI Ask AI Fallback Error: {ai_err}", exc_info=True)
            return f"Sorry, I encountered an error trying to answer your question: {e}"

def get_ai_analysis_for_work(work_id: int):
    """Generate AI analysis for a specific work."""
    logger.info(f"UI: Generating AI analysis for work ID {work_id}")
    if not work_id:
        return "Please select a work to analyze."

    try:
        # Ensure API key is configured
        ai_manager.validate_gemini_api_key()

        # Get work details
        work = database.get_work_by_id(work_id)
        if not work:
            return "Work not found."

        # Generate prompt about this specific work
        prompt = f"Analyze the copyright status of '{work.title}' in different jurisdictions. "

        if work.authors:
            authors = ", ".join(a.name for a in work.authors)
            prompt += f"Created by {authors}. "

            # Add death dates if available
            death_dates = []
            for author in work.authors:
                if author.death_date:
                    death_dates.append(f"{author.name} died on {author.death_date}")

            if death_dates:
                prompt += f"{', '.join(death_dates)}. "

        if work.creation_date:
            prompt += f"Created on {work.creation_date}. "

        prompt += "Explain when this work will enter the public domain in different countries, and any special considerations."

        # Get the analysis
        analysis = ask_ai_about_data(prompt)
        return analysis

    except Exception as e:
        logger.error(f"UI Work Analysis Error: {e}", exc_info=True)
        return f"Error generating analysis: {e}"

def initialize_topics_ui():
    """Initialize the topics tab with data and UI elements."""
    logger.info("UI: Initializing topics tab")
    try:
        # First check if we have any topics in the database
        topics = database.get_all_topics()
        
        if not topics or len(topics) == 0:
            # No topics found, let's see if we have any works with topics that weren't properly registered
            logger.warning("No topics found in database. Checking for topics in works...")
            all_works = database.get_all_works()
            topic_names = set()
            for work in all_works:
                if work.topic and work.topic.name:
                    topic_names.add(work.topic.name)
            
            # Add any missing topics to the database
            for topic_name in topic_names:
                logger.info(f"Adding missing topic: {topic_name}")
                database.add_topic(topic_name)
            
            # Try getting topics again
            topics = database.get_all_topics()
        
        # Format topics for display and return
        topics_df = format_topics_for_display(topics)
        message = f"Found {len(topics)} topics."
        
        if len(topics) == 0:
            # If we still have no topics, we need sample data
            message = "No topics found. Use the 'Data Management' tab to add sample data."
        
        logger.info(f"UI: Topics tab initialized with {len(topics)} topics")
        return topics_df, message
        
    except Exception as e:
        logger.error(f"UI Topics Initialization Error: {e}", exc_info=True)
        empty_df = pd.DataFrame(columns=["ID", "Name"])
        return empty_df, f"Error initializing topics: {e}"

def setup_topics_tab():
    """Get the topic selection handler function."""
    # Topic selection handler
    def topic_selection_handler(evt: gr.SelectData):
        try:
            # Check if the event has valid index information
            if not hasattr(evt, 'index') or not evt.index:
                return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), "Please select a topic to view works."
            
            # Get the topic data directly from the database - don't rely on UI state
            topics = database.get_all_topics()
            if not topics or len(topics) <= evt.index[0]:
                return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), "Invalid topic selection."
            
            # Get the selected topic
            selected_topic = topics[evt.index[0]]
            topic_name = selected_topic.name
            
            logger.info(f"UI: Getting works for topic: {topic_name} (ID: {selected_topic.id})")
            
            # Get works by topic name directly
            works = database.get_works_by_topic(topic_name)
            
            if not works:
                return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), f"No works found for topic '{topic_name}'."
            
            return format_works_for_display(works), f"Found {len(works)} works for topic '{topic_name}'."
            
        except Exception as e:
            logger.error(f"UI Topic Selection Error: {e}", exc_info=True)
            return pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"]), f"Error loading works: {str(e)}"

    return topic_selection_handler

def setup_authors_tab():
    """Get the author selection handler function."""
    def author_selection_handler(evt: gr.SelectData, authors_df_from_state: pd.DataFrame):
        authors_df = authors_df_from_state
        empty_works_df = pd.DataFrame(columns=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"])
        try:
            if authors_df is None or not isinstance(authors_df, pd.DataFrame) or authors_df.empty:
                logger.warning("UI: author_selection_handler called with invalid or empty authors_df from state.")
                return empty_works_df, "Author data is not available. Cannot load works."
            if evt is None or not hasattr(evt, 'index') or not evt.index:
                logger.debug("UI: author_selection_handler called without a valid selection event.")
                return empty_works_df, "Please select an author to view their works."
            selected_index = evt.index[0]
            try:
                if selected_index >= len(authors_df):
                    logger.warning(f"UI: Selected index {selected_index} out of bounds for authors_df with length {len(authors_df)}.")
                    return empty_works_df, "Invalid selection index."
                author_id = int(authors_df.iloc[selected_index]['ID'])
            except (IndexError, ValueError, TypeError, KeyError) as e:
                logger.error(f"UI: Error retrieving author ID from DataFrame state. Index: {selected_index}, Df shape: {authors_df.shape}. Error: {e}", exc_info=True)
                if selected_index < len(authors_df):
                    logger.error(f"Problematic row data: {authors_df.iloc[selected_index]}")
                return empty_works_df, "Could not retrieve author ID from selection."
            logger.info(f"UI: Getting works for author ID {author_id}")
            author = database.get_author_by_id(author_id)
            if not author:
                return empty_works_df, f"Author with ID {author_id} not found in database."
            author_name = author.name
            logger.info(f"UI: Getting works for author: {author_name} (ID: {author_id})")
            works = database.get_works_by_author_id(author_id)
            if not works:
                return empty_works_df, f"No works found for author '{author_name}'."
            return format_works_for_display(works), f"Found {len(works)} works for author '{author_name}'."
        except Exception as e:
            logger.error(f"UI Author Selection Error: {e}", exc_info=True)
            return empty_works_df, f"Error loading works: {str(e)}"
    return author_selection_handler

# --- Data Management Functions ---
def enhance_works_ui(topic: str = None, limit: int = 10):
    """UI wrapper to trigger AI enhancement."""
    logger.info(f"UI: Triggering enhancement (Topic: {topic}, Limit: {limit})")
    try:
        ai_manager.validate_gemini_api_key()
        count = ai_manager.enhance_existing_works(topic, limit)
        return f"Enhancement process completed. Attempted to enhance {count} works."
    except Exception as e:
        logger.error(f"UI Enhance Error: {e}", exc_info=True)
        return f"Error during enhancement: {e}"

def populate_db_ui():
    """UI wrapper to trigger database population."""
    logger.info("UI: Triggering database population with famous works")
    try:
        # Ensure populate_db is imported correctly
        from src import populate_db
        result_code = populate_db.main()
        if result_code == 0:
            return "Database population script completed successfully. Refresh tabs to see changes."
        else:
            return "Database population script finished with errors (check logs)."
    except Exception as e:
        logger.error(f"UI Populate DB Error: {e}", exc_info=True)
        return f"Error running population script: {e}"

def scrape_gutenberg_ui(query: str = "", max_works: int = 5):
    """UI wrapper to trigger Gutenberg scraping."""
    logger.info(f"UI: Triggering Gutenberg scrape (Query: '{query}', Max: {max_works})")
    try:
        ai_manager.validate_gemini_api_key()
        # Ensure gutenberg_spider is imported correctly
        from src.scraper.spiders import gutenberg_spider
        works = gutenberg_spider.scrape_gutenberg_batch(query=query, max_works=max_works)
        saved_count = ai_manager.save_works_to_database(works)
        return f"Gutenberg scraping completed. Scraped {len(works)} works, saved {saved_count} to database. Refresh tabs to see changes."
    except Exception as e:
        logger.error(f"UI Gutenberg Scrape Error: {e}", exc_info=True)
        return f"Error during Gutenberg scraping: {e}"

# --- Gradio Interface Definition ---
with gr.Blocks(title="Author Rights Explorer", theme=gr.themes.Base()) as iface:
    gr.Markdown("# Copyright and Author Rights Explorer")
    gr.Markdown("*Explore copyright information for creative works across international jurisdictions*")

    # --- State Components ---
    selected_work_id_state = gr.Number(value=-1, visible=False)
    authors_data_state = gr.State()  # State for authors data
    topics_data_state = gr.State()   # State for topics data

    with gr.Tabs():
        # --- Dashboard Tab ---
        with gr.TabItem("Dashboard", id=0):
            gr.Markdown("## Copyright Database Overview")
            db_status_output = gr.Markdown(label="Database Status")

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Works Expiring Soon")
                    # Removed max_rows
                    expiring_output = gr.DataFrame(label="Expiring Works", headers=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"], wrap=True)
                with gr.Column():
                    gr.Markdown("### Public Domain Examples")
                    # Removed max_rows
                    pd_output = gr.DataFrame(label="Public Domain Works", headers=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"], wrap=True)

            # Add a refresh button
            refresh_button = gr.Button("Refresh Dashboard")
            refresh_button.click(get_dashboard_info, inputs=None, outputs=[db_status_output, expiring_output, pd_output])

            # Load dashboard info when UI starts
            iface.load(get_dashboard_info, inputs=None, outputs=[db_status_output, expiring_output, pd_output])

        # --- Browse Works Tab ---
        with gr.TabItem("Browse Works", id=1):
            gr.Markdown("## Find & View Works")
            with gr.Row():
                search_input = gr.Textbox(label="Search Works", placeholder="Enter title, author, or topic")
                search_button = gr.Button("Search")

            search_status = gr.Textbox(label="Status", interactive=False)
            works_output = gr.DataFrame(label="Works Found", headers=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"], wrap=True, interactive=True)

            # Bind the search function
            search_button.click(search_works_ui, inputs=search_input, outputs=[works_output, search_status])

            # Work details section
            gr.Markdown("## Work Details")
            gr.Markdown("*Select a work from the table above to view details*")

            work_details_output = gr.Markdown(label="Work Details")

            # Add AI analysis section for the selected work
            gr.Markdown("## AI Analysis")
            work_analysis_button = gr.Button("Generate Copyright Analysis")
            work_analysis_output = gr.Markdown(label="Copyright Analysis")

            # Hidden element to store the current work query for AI
            current_work_query = gr.Textbox(visible=False)

            # Bind the work selection event
            works_output.select(
                fn=get_work_details_ui,
                inputs=[works_output],
                outputs=[work_details_output, selected_work_id_state]
            )

            # Bind the analysis button
            work_analysis_button.click(
                fn=get_ai_analysis_for_work,
                inputs=[selected_work_id_state],
                outputs=work_analysis_output
            )

        # --- Browse Authors Tab ---
        with gr.TabItem("Browse Authors", id=2):
            gr.Markdown("## Find & View Authors")
            with gr.Row():
                 author_search_input = gr.Textbox(label="Search Authors", placeholder="e.g., Jane Austen")
                 author_search_button = gr.Button("Search")

            author_search_status = gr.Textbox(label="Status", interactive=False)
            authors_output = gr.DataFrame(label="Authors Found", headers=["ID", "Name", "Birth Date", "Death Date", "Nationality"], wrap=True, interactive=True)

            # Bind the author search function - NOW OUTPUTS TO STATE
            author_search_button.click(
                search_authors_ui,
                inputs=author_search_input,
                outputs=[authors_output, author_search_status, authors_data_state]
            )

            gr.Markdown("## Works by Selected Author")
            gr.Markdown("*Select an author from the table above to view their works*")
            author_works_status = gr.Textbox(label="Status", interactive=False)
            author_works_output = gr.DataFrame(label="Author's Works", headers=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"], wrap=True, interactive=True)

            # Get the author selection handler function
            author_selection_handler = setup_authors_tab()

            # Bind author selection - NOW INPUTS FROM STATE
            authors_output.select(
                fn=author_selection_handler,
                inputs=[authors_data_state],
                outputs=[author_works_output, author_works_status]
            )

            # Add work details when selecting a work by an author
            author_work_details_output = gr.Markdown(label="Selected Work Details")

            author_works_output.select(
                fn=get_work_details_ui,
                inputs=[author_works_output],
                outputs=[author_work_details_output, selected_work_id_state] # Update state here too
            )

        # --- Browse Topics Tab ---
        with gr.TabItem("Browse Topics", id=3):
            gr.Markdown("## Explore by Topic")
            topic_status = gr.Textbox(label="Status", interactive=False)
            topics_output = gr.DataFrame(label="Available Topics", headers=["ID", "Name"], wrap=True, interactive=True)

            # Load topics when tab opens or refresh button clicked
            topics_refresh_button = gr.Button("Refresh Topics")
            topics_refresh_button.click(initialize_topics_ui, inputs=None, outputs=[topics_output, topic_status])

            # Also load on UI start with the initialization function
            iface.load(initialize_topics_ui, inputs=None, outputs=[topics_output, topic_status])

            gr.Markdown("## Works in Selected Topic")
            gr.Markdown("*Select a topic from the table above to view works*")

            topic_works_status = gr.Textbox(label="Status", interactive=False)
            topic_works_output = gr.DataFrame(label="Topic Works", headers=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"], wrap=True, interactive=True)

            # Get the topic selection handler function
            topic_selection_handler = setup_topics_tab()
            
            # Bind topic selection with the handler
            topics_output.select(
                fn=topic_selection_handler,
                outputs=[topic_works_output, topic_works_status]
            )
            
            # Work details when selecting a work within a topic
            topic_work_details_output = gr.Markdown(label="Selected Work Details")
            
            # Bind work selection
            topic_works_output.select(
                fn=get_work_details_ui,
                inputs=[topic_works_output],
                outputs=[topic_work_details_output, selected_work_id_state]
            )

        # --- Reports Tab ---
        with gr.TabItem("Reports", id=4):
            gr.Markdown("## Copyright Reports")

            with gr.Tab("Upcoming Expirations"):
                gr.Markdown("### Works Expiring Soon")
                gr.Markdown("*Shows works that will enter the public domain within the next year*")

                expiry_button = gr.Button("Generate Expiration Report")
                expiry_status = gr.Textbox(label="Status", interactive=False)
                expiry_report_output = gr.DataFrame(label="Works Expiring Soon", headers=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"], wrap=True)

                expiry_button.click(get_upcoming_expirations_ui, inputs=None, outputs=[expiry_report_output, expiry_status])

            with gr.Tab("Public Domain Works"):
                gr.Markdown("### Works in Public Domain")
                gr.Markdown("*Shows works that are already in the public domain*")

                pd_button = gr.Button("Generate Public Domain Report")
                pd_status = gr.Textbox(label="Status", interactive=False)
                pd_report_output = gr.DataFrame(label="Public Domain Works", headers=["ID", "Title", "Authors", "Topic", "Status", "Expiry Date"], wrap=True)

                pd_button.click(get_public_domain_ui, inputs=None, outputs=[pd_report_output, pd_status])

            with gr.Tab("International Status"):
                gr.Markdown("### International Copyright Status")
                gr.Markdown("*Shows copyright status across all jurisdictions*")

                international_button = gr.Button("Generate International Report")
                international_output = gr.Markdown(label="International Status")

                international_button.click(get_international_status_ui, inputs=None, outputs=international_output)

        # --- Ask AI Tab ---
        with gr.TabItem("Ask AI", id=5):
            gr.Markdown("## Ask the AI Assistant About Copyright")
            gr.Markdown("*Ask questions about copyright law, specific works in the database, or author rights*")

            ai_examples = [
                "When does The Great Gatsby enter the public domain?",
                "Explain the difference between US and EU copyright terms",
                "What works by Jane Austen are in the public domain?",
                "How do I determine if a work is in the public domain?",
                "What special rules apply to corporate works in the US?"
            ]

            ai_question = gr.Textbox(
                label="Your Question",
                placeholder="e.g., When will this work enter public domain in the US?",
                lines=2
            )

            # Add example questions
            gr.Examples(
                examples=ai_examples,
                inputs=ai_question
            )
            
            # First the button, then the answer output (proper ordering)
            ai_button = gr.Button("Ask AI", variant="primary", size="lg")
            
            # Improved answer display with more space and better formatting
            ai_answer = gr.Markdown(
                label="AI Answer",
                value="Ask a question to get started...",
                elem_id="ai_answer_box", # Keep the ID for styling
                elem_classes=["ai-answer-output"] # Keep the class for styling
            )

            # Add custom CSS to improve the AI answer display
            gr.HTML("""
            <style>
                #ai_answer_box {
                    /* Adaptable height with scrolling */
                    max-height: 400px; /* Set a maximum height */
                    min-height: 100px; /* Set a minimum height */
                    overflow-y: auto; /* Add scrollbar if content exceeds max-height */

                    /* Styling for better visibility */
                    margin-top: 15px;
                    padding: 15px;
                    border: 1px solid #ccc; /* Slightly darker border */
                    border-radius: 8px;
                    background-color: #ffffff; /* Use white background for contrast with dark text */
                    color: #333333; /* Ensure text color is dark */
                }
                /* Ensure nested elements inherit text color */
                .ai-answer-output p,
                .ai-answer-output li,
                .ai-answer-output h1,
                .ai-answer-output h2,
                .ai-answer-output h3,
                .ai-answer-output strong {
                    color: #333333 !important; /* Force dark text color */
                }
                .ai-answer-output p {
                    margin-bottom: 10px;
                }
                .ai-answer-output ul, .ai-answer-output ol {
                    margin-left: 20px;
                    margin-bottom: 10px;
                }
                .ai-answer-output h1, .ai-answer-output h2, .ai-answer-output h3 {
                    margin-top: 15px;
                    margin-bottom: 10px;
                }
            </style>
            """)
            
            # Define function to update the button text
            def set_thinking_button():
                return gr.Button.update(value="⌛ Thinking...", interactive=False)
            
            def reset_button():
                return gr.Button.update(value="Ask AI ⏎", interactive=True)
            
            # Chain the button actions in sequence
            ai_button.click(
                fn=set_thinking_button,
                inputs=None,
                outputs=ai_button
            ).then(
                fn=ask_ai_about_data,
                inputs=ai_question,
                outputs=ai_answer
            ).then(
                fn=reset_button,
                inputs=None,
                outputs=ai_button
            )

        # --- Data Management Tab (Less Prominent) ---
        with gr.TabItem("Data Management", id=6):
            gr.Markdown("## Database Management")
            gr.Markdown("*This section contains tools to populate and enhance the database*")

            with gr.Tab("Initialize Database"):
                gr.Markdown("### Add Sample Data")
                gr.Markdown("*Populate the database with common famous works*")

                populate_button = gr.Button("Populate with Famous Works")
                populate_status = gr.Textbox(label="Status", interactive=False)

                populate_button.click(populate_db_ui, inputs=None, outputs=populate_status)

            with gr.Tab("Scrape New Data"):
                gr.Markdown("### Import from Gutenberg")
                gr.Markdown("*Scrape and import works from Project Gutenberg (requires Gemini API key)*")

                with gr.Row():
                    scrape_query = gr.Textbox(label="Search Query", placeholder="e.g., science fiction")
                    scrape_limit = gr.Number(label="Maximum Works", value=5, minimum=1, maximum=20)

                scrape_button = gr.Button("Scrape Gutenberg")
                scrape_status = gr.Textbox(label="Status", interactive=False)

                scrape_button.click(scrape_gutenberg_ui, inputs=[scrape_query, scrape_limit], outputs=scrape_status)

            with gr.Tab("Enhance Existing Data"):
                gr.Markdown("### AI Enhancement")
                gr.Markdown("*Use AI to enhance existing works with missing information (requires Gemini API key)*")

                with gr.Row():
                    enhance_topic = gr.Textbox(label="Filter by Topic (Optional)", placeholder="e.g., Books")
                    enhance_limit = gr.Number(label="Maximum Works", value=5, minimum=1, maximum=20)

                enhance_button = gr.Button("Enhance Works")
                enhance_status = gr.Textbox(label="Status", interactive=False)

                enhance_button.click(enhance_works_ui, inputs=[enhance_topic, enhance_limit], outputs=enhance_status)

# --- Launch UI ---
if __name__ == "__main__":
    logger.info("Launching Author Rights Explorer UI...")
    iface.launch(share=False, debug=True)
