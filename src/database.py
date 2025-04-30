import sqlite3
import logging
import os
import threading
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from contextlib import contextmanager

from .config import DATABASE_PATH, DATA_DIR
from .data_models import Work, Author, Topic, Jurisdiction, CopyrightRule

logger = logging.getLogger(__name__)

# Thread-local storage for database connections
_local = threading.local()

@contextmanager
def get_connection():
    """
    Context manager for database connections.
    Creates or reuses connections per thread and handles commit/rollback automatically.
    """
    # Initialize connection for this thread if it doesn't exist
    if not hasattr(_local, 'connection'):
        _local.connection = None
    
    # Create a new connection if we don't have one
    new_connection = False
    if _local.connection is None:
        _local.connection = sqlite3.connect(DATABASE_PATH, timeout=20.0)  # Increased timeout
        _local.connection.row_factory = sqlite3.Row  # Return rows as dictionaries
        new_connection = True
    
    try:
        # Yield the connection to the caller
        yield _local.connection
        # If we got here without an exception, commit any changes
        _local.connection.commit()
    except Exception as e:
        # On exception, roll back any changes
        if _local.connection:
            _local.connection.rollback()
            logger.error(f"Database error, rolling back: {e}")
        raise
    finally:
        # Close the connection if we created a new one
        if new_connection and _local.connection:
            _local.connection.close()
            _local.connection = None

def dict_factory(cursor, row):
    """Convert SQLite rows to dictionaries for easier handling."""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    
    logger.info(f"Initializing database at {DATABASE_PATH}")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            ## Drop existing tables to ensure a clean start
            # cursor.execute("DROP TABLE IF EXISTS work_jurisdiction_status")
            # cursor.execute("DROP TABLE IF EXISTS copyright_rules")
            # cursor.execute("DROP TABLE IF EXISTS work_authors")
            # cursor.execute("DROP TABLE IF EXISTS works")
            # cursor.execute("DROP TABLE IF EXISTS authors")
            # cursor.execute("DROP TABLE IF EXISTS topics")
            # cursor.execute("DROP TABLE IF EXISTS jurisdictions")
            
            # Create jurisdictions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jurisdictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    code TEXT,
                    term_years_after_death INTEGER DEFAULT 70,
                    has_special_rules BOOLEAN DEFAULT 0
                )
            ''')
            
            # Create copyright_rules table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS copyright_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    jurisdiction_id INTEGER NOT NULL,
                    rule_type TEXT NOT NULL,
                    term_years INTEGER NOT NULL,
                    base_date_type TEXT NOT NULL,
                    description TEXT,
                    FOREIGN KEY (jurisdiction_id) REFERENCES jurisdictions (id),
                    UNIQUE (jurisdiction_id, rule_type)
                )
            ''')
            
            # Create topics table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE
                )
            ''')
            
            # Create authors table with nationality field
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS authors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    birth_date TEXT,
                    death_date TEXT,
                    nationality TEXT
                )
            ''')
            
            # Create works table with enhanced fields
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS works (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    topic_id INTEGER,
                    creation_date TEXT,
                    first_publication_date TEXT,
                    source_url TEXT UNIQUE,
                    scraped_timestamp TEXT,
                    copyright_expiry_date TEXT,
                    primary_jurisdiction_id INTEGER,
                    status TEXT DEFAULT 'Unknown',
                    is_collaborative BOOLEAN DEFAULT 0,      -- Added
                    original_language TEXT,                 -- Added
                    original_publisher TEXT,                -- Added
                    description TEXT,                       -- Added
                    FOREIGN KEY (topic_id) REFERENCES topics (id),
                    FOREIGN KEY (primary_jurisdiction_id) REFERENCES jurisdictions (id)
                )
            ''')
            
            # Create work_authors junction table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS work_authors (
                    work_id INTEGER,
                    author_id INTEGER,
                    FOREIGN KEY (work_id) REFERENCES works (id),
                    FOREIGN KEY (author_id) REFERENCES authors (id),
                    PRIMARY KEY (work_id, author_id)
                )
            ''')
            
            # Create work_jurisdiction_status table for per-jurisdiction status
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS work_jurisdiction_status (
                    work_id INTEGER,
                    jurisdiction_id INTEGER,
                    status TEXT DEFAULT 'Unknown',
                    expiry_date TEXT,
                    FOREIGN KEY (work_id) REFERENCES works (id),
                    FOREIGN KEY (jurisdiction_id) REFERENCES jurisdictions (id),
                    PRIMARY KEY (work_id, jurisdiction_id)
                )
            ''')
            
            # Add indexes for frequent queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_works_expiry ON works (copyright_expiry_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_works_status ON works (status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_works_topic ON works (topic_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_works_jurisdiction ON works (primary_jurisdiction_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_work_jurisdiction_status ON work_jurisdiction_status (jurisdiction_id, status)')
            
        logger.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logger.error(f"Database error during initialization: {e}")
        raise

def add_topic(name: str) -> Optional[Topic]:
    """Adds a topic to the database if it doesn't exist, or retrieves it if it does."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert or ignore the topic
            cursor.execute('INSERT OR IGNORE INTO topics (name) VALUES (?)', (name,))
            
            # Get the topic ID (whether newly inserted or existing)
            cursor.execute('SELECT id FROM topics WHERE name = ?', (name,))
            result = cursor.fetchone()
            
            if result:
                return Topic(id=result[0], name=name)
            return None
    except sqlite3.Error as e:
        logger.error(f"Database error adding topic '{name}': {e}")
        return None

def get_topic_by_name(name: str) -> Optional[Topic]:
    """Retrieves a topic by name."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT id, name FROM topics WHERE name = ?', (name,))
            result = cursor.fetchone()
            
            if result:
                return Topic(id=result[0], name=result[1])
            return None
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving topic '{name}': {e}")
        return None
    
def get_all_topics() -> List[Topic]:
    """Retrieves all topics from the database."""
    topics = []
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            # Use dict_factory for easier access
            conn.row_factory = dict_factory
            cursor.execute('SELECT id, name FROM topics ORDER BY name')
            results = cursor.fetchall()
            for row in results:
                topics.append(Topic(id=row['id'], name=row['name']))
        logger.info(f"Retrieved {len(topics)} topics from database")
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving all topics: {e}")
    finally:
        # Reset row_factory if it was changed within the connection context
        if 'conn' in locals() and conn:
             conn.row_factory = sqlite3.Row # Or whatever the default was
    return topics

def get_topic_by_id(topic_id: int) -> Optional[Topic]:
    """Retrieves a topic by its ID."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            conn.row_factory = dict_factory
            cursor.execute('SELECT id, name FROM topics WHERE id = ?', (topic_id,))
            result = cursor.fetchone()
            if result:
                return Topic(id=result['id'], name=result['name'])
            return None
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving topic ID {topic_id}: {e}")
        return None
    finally:
        if 'conn' in locals() and conn:
            conn.row_factory = sqlite3.Row

def get_all_authors() -> List[Author]:
    """Retrieves all authors from the database."""
    authors = []
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            conn.row_factory = dict_factory # Use dict_factory
            cursor.execute('SELECT id, name, birth_date, death_date, nationality FROM authors ORDER BY name')
            results = cursor.fetchall()
            for row in results:
                authors.append(Author(
                    id=row['id'],
                    name=row['name'],
                    birth_date=_parse_db_date(row['birth_date']),
                    death_date=_parse_db_date(row['death_date']),
                    nationality=row['nationality']
                    # bio=row.get('bio') # Uncomment if bio column exists
                ))
        logger.info(f"Retrieved {len(authors)} authors from database")
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving all authors: {e}")
    finally:
        if 'conn' in locals() and conn:
             conn.row_factory = sqlite3.Row
    return authors

def get_author_by_id(author_id: int) -> Optional[Author]:
    """Retrieves an author by their ID."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            conn.row_factory = dict_factory
            cursor.execute('SELECT * FROM authors WHERE id = ?', (author_id,))
            result = cursor.fetchone()
            if result:
                return Author(
                    id=result['id'],
                    name=result['name'],
                    birth_date=_parse_db_date(result['birth_date']),
                    death_date=_parse_db_date(result['death_date']),
                    nationality=result['nationality']
                    # bio=result.get('bio') # Uncomment if bio column exists
                )
            return None
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving author ID {author_id}: {e}")
        return None
    finally:
        if 'conn' in locals() and conn:
             conn.row_factory = sqlite3.Row
             
def get_or_save_author(author: Author) -> Optional[Author]:
    """Saves an author to the database if they don't exist, or retrieves them if they do."""
    if not author.name:
        logger.warning("Cannot save author with empty name")
        return None
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Convert dates to string format for SQLite if they exist
            birth_date_str = author.birth_date.isoformat() if author.birth_date else None
            death_date_str = author.death_date.isoformat() if author.death_date else None
            
            # Check if author already exists
            cursor.execute('SELECT id, birth_date, death_date, nationality FROM authors WHERE name = ?', (author.name,))
            result = cursor.fetchone()
            
            if result:
                # Author exists, update if we have more info
                db_id = result[0]
                db_birth = result[1]
                db_death = result[2]
                db_nationality = result[3]
                
                # Update if we have data that was previously NULL
                if (birth_date_str and not db_birth) or (death_date_str and not db_death) or (author.nationality and not db_nationality):
                    cursor.execute(
                        'UPDATE authors SET birth_date = COALESCE(?, birth_date), death_date = COALESCE(?, death_date), nationality = COALESCE(?, nationality) WHERE id = ?',
                        (birth_date_str, death_date_str, author.nationality, db_id)
                    )
                
                # Return the author with ID
                saved_author = Author(id=db_id, name=author.name)
                
                # Convert database string dates back to date objects if they exist
                if db_birth:
                    saved_author.birth_date = date.fromisoformat(db_birth)
                elif birth_date_str:
                    saved_author.birth_date = author.birth_date
                    
                if db_death:
                    saved_author.death_date = date.fromisoformat(db_death)
                elif death_date_str:
                    saved_author.death_date = author.death_date
                
                # Set nationality
                saved_author.nationality = db_nationality or author.nationality
                    
                return saved_author
            else:
                # Insert new author
                cursor.execute(
                    'INSERT INTO authors (name, birth_date, death_date, nationality) VALUES (?, ?, ?, ?)',
                    (author.name, birth_date_str, death_date_str, author.nationality)
                )
                
                # Get the new ID
                author_id = cursor.lastrowid
                
                # Return author with ID
                saved_author = Author(
                    id=author_id,
                    name=author.name,
                    birth_date=author.birth_date,
                    death_date=author.death_date,
                    nationality=author.nationality
                )
                return saved_author
                
    except sqlite3.Error as e:
        logger.error(f"Database error saving author '{author.name}': {e}")
        return None

def save_work(work: Work) -> Optional[Work]:
    """Saves a Work object to the database with all related data."""
    if not work.title:
        logger.warning("Cannot save work with empty title")
        return None
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # First, ensure we have a topic_id if a topic is provided
            topic_id = None
            if work.topic:
                if work.topic.id:
                    # Verify the topic ID exists
                    cursor.execute('SELECT id FROM topics WHERE id = ?', (work.topic.id,))
                    if not cursor.fetchone():
                        # Topic ID doesn't exist, try to get by name
                        topic = get_topic_by_name(work.topic.name)
                        topic_id = topic.id if topic else None
                    else:
                        topic_id = work.topic.id
                elif work.topic.name:
                    # Try to get topic by name
                    topic = get_topic_by_name(work.topic.name)
                    if not topic:
                        # Create new topic
                        topic = add_topic(work.topic.name)
                    topic_id = topic.id if topic else None
            
            # Handle primary jurisdiction if provided
            primary_jurisdiction_id = None
            if work.primary_jurisdiction:
                if work.primary_jurisdiction.id:
                    # Verify the jurisdiction ID exists
                    cursor.execute('SELECT id FROM jurisdictions WHERE id = ?', (work.primary_jurisdiction.id,))
                    if not cursor.fetchone():
                        # Jurisdiction ID doesn't exist, try to get by name
                        jurisdiction = get_jurisdiction_by_name(work.primary_jurisdiction.name)
                        primary_jurisdiction_id = jurisdiction.id if jurisdiction else None
                    else:
                        primary_jurisdiction_id = work.primary_jurisdiction.id
                elif work.primary_jurisdiction.name:
                    # Try to get jurisdiction by name
                    jurisdiction = get_jurisdiction_by_name(work.primary_jurisdiction.name)
                    primary_jurisdiction_id = jurisdiction.id if jurisdiction else None
            
            # Convert dates to string format for SQLite if they exist
            creation_date_str = work.creation_date.isoformat() if work.creation_date else None
            first_publication_date_str = work.first_publication_date.isoformat() if work.first_publication_date else None
            expiry_date_str = work.copyright_expiry_date.isoformat() if work.copyright_expiry_date else None
            scraped_timestamp_str = work.scraped_timestamp.isoformat() if work.scraped_timestamp else datetime.utcnow().isoformat()
            is_collaborative_int = 1 if work.is_collaborative else 0 # Define this before use
            
            # Check if work exists based on source_url (if provided) or title
            existing_id = None
            if work.source_url:
                cursor.execute('SELECT id FROM works WHERE source_url = ?', (work.source_url,))
                result = cursor.fetchone()
                if result:
                    existing_id = result[0]
            
            if not existing_id and work.id:
                # Check if the provided ID exists
                cursor.execute('SELECT id FROM works WHERE id = ?', (work.id,))
                result = cursor.fetchone()
                if result:
                    existing_id = result[0]
            
            # Save or update the work
            if existing_id:
                # Update existing work
                cursor.execute('''
                    UPDATE works
                    SET title = ?,
                        topic_id = COALESCE(?, topic_id),
                        creation_date = COALESCE(?, creation_date),
                        first_publication_date = COALESCE(?, first_publication_date),
                        source_url = COALESCE(?, source_url),
                        scraped_timestamp = ?,
                        copyright_expiry_date = ?, -- Allow overwriting expiry date
                        primary_jurisdiction_id = COALESCE(?, primary_jurisdiction_id),
                        status = ?, -- Allow overwriting status
                        is_collaborative = ?, -- Allow overwriting flag
                        original_language = COALESCE(?, original_language),
                        original_publisher = COALESCE(?, original_publisher),
                        description = COALESCE(?, description)
                    WHERE id = ?
                ''', (
                    work.title,
                    topic_id,
                    creation_date_str,
                    first_publication_date_str,
                    work.source_url,
                    scraped_timestamp_str,
                    expiry_date_str, # Update expiry date
                    primary_jurisdiction_id,
                    work.status, # Update status
                    is_collaborative_int, # Update flag
                    work.original_language,
                    work.original_publisher,
                    work.description,
                    existing_id
                ))
                work_id = existing_id
                logger.debug(f"Updated work ID: {work_id}")
            else:
                # Insert new work
                cursor.execute('''
                    INSERT INTO works (
                        title, topic_id, creation_date, first_publication_date,
                        source_url, scraped_timestamp, copyright_expiry_date,
                        primary_jurisdiction_id, status, is_collaborative,
                        original_language, original_publisher, description
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    work.title, topic_id, creation_date_str, first_publication_date_str,
                    work.source_url, scraped_timestamp_str, expiry_date_str,
                    primary_jurisdiction_id, work.status, is_collaborative_int,
                    work.original_language,
                    work.original_publisher,
                    work.description
                ))
                work_id = cursor.lastrowid
                logger.debug(f"Inserted new work ID: {work_id}")
            
            # Handle authors
            if work.authors:
                # First, save all authors to get their IDs
                saved_authors = []
                for author in work.authors:
                    saved_author = get_or_save_author(author)
                    if saved_author:
                        saved_authors.append(saved_author)
                
                # If updating an existing work, clear existing author links
                if existing_id:
                    cursor.execute('DELETE FROM work_authors WHERE work_id = ?', (existing_id,))
                
                # Create links between work and authors
                for author in saved_authors:
                    if author.id:
                        cursor.execute(
                            'INSERT OR IGNORE INTO work_authors (work_id, author_id) VALUES (?, ?)',
                            (work_id, author.id)
                        )
            
            # Handle jurisdiction-specific statuses
            if work.status_by_jurisdiction and work_id:
                for jur_code, status in work.status_by_jurisdiction.items():
                    # Find the jurisdiction ID by code
                    cursor.execute('SELECT id FROM jurisdictions WHERE code = ?', (jur_code,))
                    jur_result = cursor.fetchone()
                    if jur_result:
                        jur_id = jur_result[0]
                        # Set the status for this jurisdiction
                        # We don't have expiry dates by jurisdiction in the Work model yet, 
                        # so we'll set it to the main expiry date
                        set_work_copyright_status_by_jurisdiction(work_id, jur_id, status, 
                                                                  work.copyright_expiry_date)
            
            # Now fetch the complete saved work with its ID and relationships
            saved_work = get_work_by_id(work_id, conn)
            
            return saved_work
            
    except sqlite3.Error as e:
        logger.error(f"Database error saving work '{work.title}': {e}")
        return None

def get_work_by_title(title: str, existing_conn=None) -> Optional[Work]:
    """Retrieves a single work by its exact title."""
    logger.debug(f"Attempting to retrieve work by title: '{title}'")

    # Define a function to perform the database operations
    def _db_ops(conn):
        conn.row_factory = dict_factory # Use dict_factory for easier processing
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM works WHERE title = ?", (title,))
        row = cursor.fetchone()
        if row:
            logger.debug(f"Found work with title '{title}', ID: {row['id']}")
            # Use get_work_by_id to retrieve the full object, passing the connection
            return get_work_by_id(row['id'], existing_conn=conn)
        else:
            logger.debug(f"No work found with title: '{title}'")
            return None

    try:
        if existing_conn:
            # Use the provided connection directly
            return _db_ops(existing_conn)
        else:
            # Use the context manager to get a new connection
            with get_connection() as conn:
                return _db_ops(conn)
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving work by title '{title}': {e}", exc_info=True)
        return None
    # No finally block needed here to close connection, context manager handles it

def get_work_by_id(work_id: int, existing_conn=None) -> Optional[Work]:
    """Retrieves a single work by its ID, including authors and topic."""
    logger.debug(f"Retrieving work by ID: {work_id}")

    # Define a function to perform the database operations
    def _db_ops(conn):
        conn.row_factory = dict_factory
        cursor = conn.cursor()

        # Fetch work details
        cursor.execute("SELECT * FROM works WHERE id = ?", (work_id,))
        work_row = cursor.fetchone()

        if not work_row:
            logger.warning(f"No work found with ID: {work_id}")
            return None

        # Fetch authors for the work
        cursor.execute("""
            SELECT a.* FROM authors a
            JOIN work_authors wa ON a.id = wa.author_id
            WHERE wa.work_id = ?
        """, (work_id,))
        author_rows = cursor.fetchall()
        # Convert author rows to Author objects, handling potential missing fields
        authors = []
        for row in author_rows:
             authors.append(Author(
                 id=row.get('id'),
                 name=row.get('name'),
                 birth_date=_parse_db_date(row.get('birth_date')),
                 death_date=_parse_db_date(row.get('death_date')),
                 nationality=row.get('nationality'),
                 bio=row.get('bio') # Assuming bio is now in authors table
             ))


        # Fetch topic for the work
        topic = None
        if work_row.get('topic_id'):
            cursor.execute("SELECT * FROM topics WHERE id = ?", (work_row['topic_id'],))
            topic_row = cursor.fetchone()
            if topic_row:
                topic = Topic(**topic_row)

        # Construct the Work object
        work = Work(
            id=work_row['id'],
            title=work_row['title'],
            authors=authors,
            topic=topic,
            creation_date=_parse_db_date(work_row.get('creation_date')),
            publication_date=_parse_db_date(work_row.get('first_publication_date')),
            # first_publication_date=_parse_db_date(work_row.get('first_publication_date')), # Redundant, use  publication_date
            source_url=work_row.get('source_url'),
            scraped_timestamp=_parse_db_datetime(work_row.get('scraped_timestamp')),
            copyright_expiry_date=_parse_db_date(work_row.get('copyright_expiry_date')),
            status=work_row.get('status', 'Unknown'),
            is_collaborative=bool(work_row.get('is_collaborative', 0)), # Need to add this column to DB schema
            original_language=work_row.get('original_language'), # Need to add this column to DB schema
            original_publisher=work_row.get('original_publisher'), # Need to add this column to DB schema
            description=work_row.get('description') # Need to add this column to DB schema
        )
        # primary_jurisdiction and status_by_jurisdiction need separate loading

        logger.debug(f"Successfully retrieved work: {work.title}")
        return work

    try:
        if existing_conn:
            # Use the provided connection directly
            return _db_ops(existing_conn)
        else:
            # Use the context manager to get a new connection
            with get_connection() as conn:
                return _db_ops(conn)
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving work ID {work_id}: {e}", exc_info=True)
        return None

# Helper function to parse dates from DB (if not already present)
def _parse_db_date(date_str: Optional[str]) -> Optional[date]:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        logger.warning(f"Could not parse date '{date_str}' from database.")
        return None

# Helper function to parse datetimes from DB (if not already present)
def _parse_db_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
     if not datetime_str:
         return None
     try:
         # Adjust format if needed based on how it's stored (e.g., with/without microseconds)
         return datetime.fromisoformat(datetime_str)
     except (ValueError, TypeError):
         logger.warning(f"Could not parse datetime '{datetime_str}' from database.")
         return None

def get_all_works() -> List[Work]:
    """Retrieves all works from the database."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all work IDs
            cursor.execute('SELECT id FROM works ORDER BY title')
            work_ids = [row[0] for row in cursor.fetchall()]
            
            # Fetch complete works
            works = []
            for work_id in work_ids:
                work = get_work_by_id(work_id, conn)
                if work:
                    works.append(work)
            
            logger.info(f"Retrieved {len(works)} works from database")
            return works
            
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving all works: {e}")
        return []

def get_works_by_topic(topic_name: str) -> List[Work]:
    """Retrieves works belonging to a specific topic."""
    logger.info(f"Attempting to retrieve works for topic: '{topic_name}'")
    works = []
    
    try:
        with get_connection() as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            
            # First get the topic ID
            cursor.execute("SELECT id FROM topics WHERE name = ?", (topic_name,))
            topic_row = cursor.fetchone()
            
            if not topic_row:
                logger.warning(f"Topic not found: {topic_name}")
                return []
                
            topic_id = topic_row['id']
            
            # Get all works with this topic ID
            cursor.execute("""
                SELECT w.* FROM works w
                WHERE w.topic_id = ?
            """, (topic_id,))
            
            work_rows = cursor.fetchall()
            
            for row in work_rows:
                # Convert row to Work object
                work = Work(
                    id=row['id'],
                    title=row['title'],
                    creation_date=_parse_db_date(row['creation_date']),
                    first_publication_date=_parse_db_date(row['first_publication_date']),
                    source_url=row.get('source_url'),
                    scraped_timestamp=_parse_db_datetime(row.get('scraped_timestamp')),
                    copyright_expiry_date=_parse_db_date(row.get('copyright_expiry_date')),
                    status=row.get('status', 'Unknown'),
                    is_collaborative=bool(row.get('is_collaborative', False)),
                    original_language=row.get('original_language'),
                    original_publisher=row.get('original_publisher'),
                    description=row.get('description')
                )
                
                # Get topic
                cursor.execute("SELECT id, name FROM topics WHERE id = ?", (row['topic_id'],))
                topic_row = cursor.fetchone()
                if topic_row:
                    work.topic = Topic(id=topic_row['id'], name=topic_row['name'])
                
                # Get authors for this work
                cursor.execute("""
                    SELECT a.* FROM authors a
                    JOIN work_authors wa ON a.id = wa.author_id
                    WHERE wa.work_id = ?
                """, (row['id'],))
                
                author_rows = cursor.fetchall()
                for author_row in author_rows:
                    author = Author(
                        id=author_row['id'],
                        name=author_row['name'],
                        birth_date=_parse_db_date(author_row.get('birth_date')),
                        death_date=_parse_db_date(author_row.get('death_date')),
                        nationality=author_row.get('nationality'),
                        bio=author_row.get('bio')
                    )
                    work.authors.append(author)
                
                works.append(work)
            
            logger.info(f"Found {len(works)} works for topic '{topic_name}'")
    
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving works by topic: {e}", exc_info=True)
    
    return works

def get_works_nearing_expiry(threshold_date: date) -> List[Work]:
    """Retrieves works with expiry date before or on the threshold."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            threshold_str = threshold_date.isoformat()
            
            # Get all work IDs with expiry dates before or on the threshold
            cursor.execute('''
                SELECT id FROM works 
                WHERE copyright_expiry_date IS NOT NULL 
                  AND copyright_expiry_date <= ? 
                  AND status = 'Copyrighted'
                ORDER BY copyright_expiry_date
            ''', (threshold_str,))
            
            work_ids = [row[0] for row in cursor.fetchall()]
            
            # Fetch complete works
            works = []
            for work_id in work_ids:
                work = get_work_by_id(work_id, conn)
                if work:
                    works.append(work)
            
            logger.info(f"Retrieved {len(works)} works expiring on or before {threshold_date}")
            return works
            
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving works nearing expiry: {e}")
        return []

def get_public_domain_works() -> List[Work]:
    """Retrieves works already in the public domain."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all work IDs with 'Public Domain' status
            cursor.execute('''
                SELECT id FROM works 
                WHERE status = 'Public Domain'
                ORDER BY title
            ''')
            
            work_ids = [row[0] for row in cursor.fetchall()]
            
            # Fetch complete works
            works = []
            for work_id in work_ids:
                work = get_work_by_id(work_id, conn)
                if work:
                    works.append(work)
            
            logger.info(f"Retrieved {len(works)} public domain works")
            return works
            
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving public domain works: {e}")
        return []

def add_famous_works(topic: str, works_data: List[dict]) -> int:
    """
    Adds a batch of famous works to the database for a specific topic.
    Returns the number of successfully added works.
    
    Each work_data dict should have:
    - 'title': Work title
    - 'authors': List of author dictionaries with 'name', optional 'birth_date', optional 'death_date', optional 'nationality'
    - Optional 'creation_date': When the work was created/published
    - Optional 'first_publication_date': When the work was first published (important for some jurisdictions)
    - Optional 'status': Default 'Unknown'
    - Optional 'primary_jurisdiction': The primary jurisdiction for copyright
    - Optional 'copyright_expiry_date': When copyright expires if known
    """
    # Import here to avoid circular imports
    from . import scheduler
    
    success_count = 0
    
    # Get or create topic
    topic_obj = get_topic_by_name(topic)
    if not topic_obj:
        topic_obj = add_topic(topic)
        if not topic_obj:
            logger.error(f"Failed to create topic: {topic}")
            return 0
    
    for work_data in works_data:
        try:
            # Create author objects
            authors = []
            for author_data in work_data.get('authors', []):
                birth_date = None
                if 'birth_date' in author_data and author_data['birth_date']:
                    if isinstance(author_data['birth_date'], str):
                        birth_date = date.fromisoformat(author_data['birth_date'])
                    else:
                        birth_date = author_data['birth_date']
                
                death_date = None
                if 'death_date' in author_data and author_data['death_date']:
                    if isinstance(author_data['death_date'], str):
                        death_date = date.fromisoformat(author_data['death_date'])
                    else:
                        death_date = author_data['death_date']
                
                nationality = author_data.get('nationality')
                
                author = Author(
                    name=author_data['name'],
                    birth_date=birth_date,
                    death_date=death_date,
                    nationality=nationality
                )
                authors.append(author)
            
            # Create work object
            creation_date = None
            if 'creation_date' in work_data and work_data['creation_date']:
                if isinstance(work_data['creation_date'], str):
                    creation_date = date.fromisoformat(work_data['creation_date'])
                else:
                    creation_date = work_data['creation_date']
            
            first_publication_date = None
            if 'first_publication_date' in work_data and work_data['first_publication_date']:
                if isinstance(work_data['first_publication_date'], str):
                    first_publication_date = date.fromisoformat(work_data['first_publication_date'])
                else:
                    first_publication_date = work_data['first_publication_date']
            
            expiry_date = None
            if 'copyright_expiry_date' in work_data and work_data['copyright_expiry_date']:
                if isinstance(work_data['copyright_expiry_date'], str):
                    expiry_date = date.fromisoformat(work_data['copyright_expiry_date'])
                else:
                    expiry_date = work_data['copyright_expiry_date']
            
            # Handle primary jurisdiction
            primary_jurisdiction = work_data.get('primary_jurisdiction')
            
            work = Work(
                title=work_data['title'],
                authors=authors,
                topic=topic_obj,
                creation_date=creation_date,
                first_publication_date=first_publication_date,
                copyright_expiry_date=expiry_date,
                status=work_data.get('status', 'Unknown'),
                source_url=work_data.get('source_url'),
                primary_jurisdiction=primary_jurisdiction
            )
            
            # Update copyright status across all jurisdictions
            work = scheduler.update_work_status(work)
            
            # Save to database
            saved_work = save_work(work)
            if saved_work:
                success_count += 1
                logger.info(f"Added famous work: {saved_work.title}")
            else:
                logger.warning(f"Failed to add famous work: {work.title}")
                
        except Exception as e:
            logger.error(f"Error adding famous work {work_data.get('title', 'Unknown')}: {e}")
    
    return success_count

def search_works(query: str) -> List[Work]:
    """Searches for works by title, author name, or topic."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Get work IDs matching the search query
            search_term = f"%{query}%"
            cursor.execute('''
                SELECT DISTINCT w.id
                FROM works w
                LEFT JOIN topics t ON w.topic_id = t.id
                LEFT JOIN work_authors wa ON w.id = wa.work_id
                LEFT JOIN authors a ON wa.author_id = a.id
                WHERE w.title LIKE ? 
                   OR a.name LIKE ?
                   OR t.name LIKE ?
                ORDER BY w.title
            ''', (search_term, search_term, search_term))
            
            work_ids = [row[0] for row in cursor.fetchall()]
            
            # Fetch complete works
            works = []
            for work_id in work_ids:
                work = get_work_by_id(work_id, conn)
                if work:
                    works.append(work)
            
            logger.info(f"Search for '{query}' returned {len(works)} works")
            return works
            
    except sqlite3.Error as e:
        logger.error(f"Database error during search for '{query}': {e}")
        return []

def search_authors(query: str) -> List[Author]:
    """Searches for authors by name (case-insensitive)."""
    logger.info(f"Searching for authors matching: '{query}'")
    authors = []
    try:
        with get_connection() as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            # Use LIKE for partial matching, case-insensitive
            search_term = f"%{query}%"
            cursor.execute("""
                SELECT * FROM authors
                WHERE name LIKE ? COLLATE NOCASE
                ORDER BY name
            """, (search_term,))
            rows = cursor.fetchall()
            for row in rows:
                author = Author(
                    id=row['id'],
                    name=row['name'],
                    birth_date=_parse_db_date(row.get('birth_date')),
                    death_date=_parse_db_date(row.get('death_date')),
                    nationality=row.get('nationality'),
                    bio=row.get('bio')
                )
                authors.append(author)
            logger.info(f"Found {len(authors)} authors matching '{query}'")
    except sqlite3.Error as e:
        logger.error(f"Database error searching authors: {e}", exc_info=True)
    return authors

def clear_database():
    """Clears all data from the database but keeps the structure.
    Useful for testing or resetting the database."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Disable foreign key constraints temporarily
            cursor.execute('PRAGMA foreign_keys = OFF;')
            
            # Delete data from all tables
            cursor.execute('DELETE FROM work_authors;')
            cursor.execute('DELETE FROM works;')
            cursor.execute('DELETE FROM authors;')
            cursor.execute('DELETE FROM topics;')
            
            # Reset auto-increment counters
            cursor.execute('DELETE FROM sqlite_sequence;')
            
            # Re-enable foreign key constraints
            cursor.execute('PRAGMA foreign_keys = ON;')
            
            logger.info("Database cleared successfully.")
            return True
    except sqlite3.Error as e:
        logger.error(f"Error clearing database: {e}")
        return False

def add_jurisdiction(jurisdiction: Jurisdiction) -> Optional[Jurisdiction]:
    """Adds a jurisdiction to the database or updates it if it exists."""
    if not jurisdiction.name:
        logger.warning("Cannot save jurisdiction with empty name")
        return None
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if jurisdiction already exists
            cursor.execute('SELECT id FROM jurisdictions WHERE name = ?', (jurisdiction.name,))
            result = cursor.fetchone()
            
            if result:
                # Update existing jurisdiction
                cursor.execute('''
                    UPDATE jurisdictions 
                    SET code = ?, 
                        term_years_after_death = ?, 
                        has_special_rules = ?
                    WHERE id = ?
                ''', (
                    jurisdiction.code,
                    jurisdiction.term_years_after_death,
                    1 if jurisdiction.has_special_rules else 0,
                    result[0]
                ))
                jurisdiction.id = result[0]
            else:
                # Insert new jurisdiction
                cursor.execute('''
                    INSERT INTO jurisdictions (name, code, term_years_after_death, has_special_rules)
                    VALUES (?, ?, ?, ?)
                ''', (
                    jurisdiction.name,
                    jurisdiction.code,
                    jurisdiction.term_years_after_death,
                    1 if jurisdiction.has_special_rules else 0
                ))
                jurisdiction.id = cursor.lastrowid
            
            return jurisdiction
    except sqlite3.Error as e:
        logger.error(f"Database error saving jurisdiction '{jurisdiction.name}': {e}")
        return None

def get_jurisdiction_by_name(name: str) -> Optional[Jurisdiction]:
    """Retrieves a jurisdiction by name."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, code, term_years_after_death, has_special_rules
                FROM jurisdictions
                WHERE name = ?
            ''', (name,))
            
            result = cursor.fetchone()
            if not result:
                return None
            
            return Jurisdiction(
                id=result[0],
                name=result[1],
                code=result[2],
                term_years_after_death=result[3],
                has_special_rules=bool(result[4])
            )
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving jurisdiction '{name}': {e}")
        return None

def get_all_jurisdictions() -> List[Jurisdiction]:
    """Retrieves all jurisdictions from the database."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, name, code, term_years_after_death, has_special_rules
                FROM jurisdictions
                ORDER BY name
            ''')
            
            jurisdictions = []
            for row in cursor.fetchall():
                jurisdiction = Jurisdiction(
                    id=row[0],
                    name=row[1],
                    code=row[2],
                    term_years_after_death=row[3],
                    has_special_rules=bool(row[4])
                )
                jurisdictions.append(jurisdiction)
            
            return jurisdictions
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving all jurisdictions: {e}")
        return []

def add_copyright_rule(rule: CopyrightRule) -> Optional[CopyrightRule]:
    """Adds a copyright rule to the database or updates it if it exists."""
    if not rule.jurisdiction or not rule.jurisdiction.id:
        logger.warning("Cannot save copyright rule without a valid jurisdiction ID")
        return None
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if rule already exists
            cursor.execute('''
                SELECT id FROM copyright_rules 
                WHERE jurisdiction_id = ? AND rule_type = ?
            ''', (rule.jurisdiction.id, rule.rule_type))
            
            result = cursor.fetchone()
            
            if result:
                # Update existing rule
                cursor.execute('''
                    UPDATE copyright_rules
                    SET term_years = ?,
                        base_date_type = ?,
                        description = ?
                    WHERE id = ?
                ''', (
                    rule.term_years,
                    rule.base_date_type,
                    rule.description,
                    result[0]
                ))
                rule_id = result[0]
            else:
                # Insert new rule
                cursor.execute('''
                    INSERT INTO copyright_rules (jurisdiction_id, rule_type, term_years, base_date_type, description)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    rule.jurisdiction.id,
                    rule.rule_type,
                    rule.term_years,
                    rule.base_date_type,
                    rule.description
                ))
                rule_id = cursor.lastrowid
            
            # Return a complete rule with ID
            complete_rule = CopyrightRule(
                jurisdiction=rule.jurisdiction,
                rule_type=rule.rule_type,
                term_years=rule.term_years,
                base_date_type=rule.base_date_type,
                description=rule.description
            )
            
            return complete_rule
    except sqlite3.Error as e:
        logger.error(f"Database error saving copyright rule: {e}")
        return None

def get_copyright_rules_for_jurisdiction(jurisdiction_id: int) -> List[CopyrightRule]:
    """Retrieves all copyright rules for a specific jurisdiction."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Get the jurisdiction first
            cursor.execute('''
                SELECT id, name, code, term_years_after_death, has_special_rules
                FROM jurisdictions
                WHERE id = ?
            ''', (jurisdiction_id,))
            
            jurisdiction_data = cursor.fetchone()
            if not jurisdiction_data:
                logger.warning(f"No jurisdiction found with ID: {jurisdiction_id}")
                return []
            
            jurisdiction = Jurisdiction(
                id=jurisdiction_data[0],
                name=jurisdiction_data[1],
                code=jurisdiction_data[2],
                term_years_after_death=jurisdiction_data[3],
                has_special_rules=bool(jurisdiction_data[4])
            )
            
            # Get all rules for this jurisdiction
            cursor.execute('''
                SELECT id, rule_type, term_years, base_date_type, description
                FROM copyright_rules
                WHERE jurisdiction_id = ?
            ''', (jurisdiction_id,))
            
            rules = []
            for row in cursor.fetchall():
                rule = CopyrightRule(
                    jurisdiction=jurisdiction,
                    rule_type=row[1],
                    term_years=row[2],
                    base_date_type=row[3],
                    description=row[4]
                )
                rules.append(rule)
            
            return rules
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving copyright rules for jurisdiction {jurisdiction_id}: {e}")
        return []

def initialize_default_jurisdictions():
    """Initializes default jurisdictions and their copyright rules."""
    # Major jurisdictions with their default rules
    jurisdictions = [
        {
            "name": "United States",
            "code": "US",
            "term_years_after_death": 70,
            "has_special_rules": True,
            "rules": [
                {
                    "rule_type": "published_before_1923",
                    "term_years": 0,
                    "base_date_type": "fixed_year",
                    "description": "Works published before 1923 are in the public domain"
                },
                {
                    "rule_type": "corporate_works",
                    "term_years": 95,
                    "base_date_type": "publication",
                    "description": "Works made for hire, published after 1978: 95 years from publication or 120 years from creation, whichever is shorter"
                },
                {
                    "rule_type": "published_1923_to_1977",
                    "term_years": 95,
                    "base_date_type": "publication",
                    "description": "Works published 1923-1977 with copyright notice: 95 years from publication date"
                }
            ]
        },
        {
            "name": "European Union",
            "code": "EU",
            "term_years_after_death": 70,
            "has_special_rules": True,
            "rules": [
                {
                    "rule_type": "anonymous_works",
                    "term_years": 70,
                    "base_date_type": "publication",
                    "description": "Anonymous or pseudonymous works: 70 years after publication"
                },
                {
                    "rule_type": "collaborative_works",
                    "term_years": 70,
                    "base_date_type": "author_death",
                    "description": "For jointly authored works: 70 years after death of last surviving author"
                }
            ]
        },
        {
            "name": "Canada",
            "code": "CA",
            "term_years_after_death": 50,  # Changed to 70 in 2022 for future implementation
            "has_special_rules": False
        },
        {
            "name": "United Kingdom",
            "code": "GB",
            "term_years_after_death": 70,
            "has_special_rules": True,
            "rules": [
                {
                    "rule_type": "crown_copyright",
                    "term_years": 50,
                    "base_date_type": "publication",
                    "description": "Crown copyright: 50 years from publication"
                }
            ]
        },
        {
            "name": "Japan",
            "code": "JP",
            "term_years_after_death": 70,
            "has_special_rules": False
        },
        {
            "name": "Mexico",
            "code": "MX",
            "term_years_after_death": 100,
            "has_special_rules": False
        }
    ]
    
    for jur_data in jurisdictions:
        # Add the jurisdiction
        jurisdiction = Jurisdiction(
            name=jur_data["name"],
            code=jur_data["code"],
            term_years_after_death=jur_data["term_years_after_death"],
            has_special_rules=jur_data["has_special_rules"]
        )
        
        saved_jurisdiction = add_jurisdiction(jurisdiction)
        if not saved_jurisdiction:
            logger.error(f"Failed to add jurisdiction: {jur_data['name']}")
            continue
        
        # Add rules if any
        if "rules" in jur_data and jur_data["has_special_rules"]:
            for rule_data in jur_data["rules"]:
                rule = CopyrightRule(
                    jurisdiction=saved_jurisdiction,
                    rule_type=rule_data["rule_type"],
                    term_years=rule_data["term_years"],
                    base_date_type=rule_data["base_date_type"],
                    description=rule_data["description"]
                )
                
                saved_rule = add_copyright_rule(rule)
                if not saved_rule:
                    logger.error(f"Failed to add copyright rule: {rule_data['rule_type']} for {jur_data['name']}")
    
    logger.info("Default jurisdictions and copyright rules initialized")

def get_work_copyright_status_by_jurisdiction(work_id: int, jurisdiction_id: int) -> Optional[dict]:
    """Gets the copyright status of a work in a specific jurisdiction."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT status, expiry_date
                FROM work_jurisdiction_status
                WHERE work_id = ? AND jurisdiction_id = ?
            ''', (work_id, jurisdiction_id))
            
            result = cursor.fetchone()
            if result:
                return {
                    "status": result[0],
                    "expiry_date": date.fromisoformat(result[1]) if result[1] else None
                }
            return None
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving jurisdiction status for work {work_id}, jurisdiction {jurisdiction_id}: {e}")
        return None

def set_work_copyright_status_by_jurisdiction(work_id: int, jurisdiction_id: int, status: str, expiry_date: Optional[date] = None):
    """Sets the copyright status of a work in a specific jurisdiction."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            expiry_date_str = expiry_date.isoformat() if expiry_date else None
            
            # Check if record exists
            cursor.execute('''
                SELECT 1 FROM work_jurisdiction_status
                WHERE work_id = ? AND jurisdiction_id = ?
            ''', (work_id, jurisdiction_id))
            
            if cursor.fetchone():
                # Update existing record
                cursor.execute('''
                    UPDATE work_jurisdiction_status
                    SET status = ?, expiry_date = ?
                    WHERE work_id = ? AND jurisdiction_id = ?
                ''', (status, expiry_date_str, work_id, jurisdiction_id))
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO work_jurisdiction_status (work_id, jurisdiction_id, status, expiry_date)
                    VALUES (?, ?, ?, ?)
                ''', (work_id, jurisdiction_id, status, expiry_date_str))
            
            return True
    except sqlite3.Error as e:
        logger.error(f"Database error setting jurisdiction status for work {work_id}, jurisdiction {jurisdiction_id}: {e}")
        return False

def delete_work(work_id: int) -> bool:
    """Deletes a work from the database by ID, including all related records."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # First delete from junction tables to maintain referential integrity
            cursor.execute('DELETE FROM work_authors WHERE work_id = ?', (work_id,))
            cursor.execute('DELETE FROM work_jurisdiction_status WHERE work_id = ?', (work_id,))
            
            # Then delete the main work record
            cursor.execute('DELETE FROM works WHERE id = ?', (work_id,))
            
            # Check if any rows were affected
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        logger.error(f"Database error deleting work {work_id}: {e}")
        return False

def get_works_by_author_id(author_id: int) -> List[Work]:
    """Retrieves works by a specific author ID."""
    logger.info(f"Retrieving works by author ID: {author_id}")
    works = []
    
    try:
        with get_connection() as conn:
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            
            # Get all works with this author ID
            cursor.execute("""
                SELECT w.* FROM works w
                JOIN work_authors wa ON w.id = wa.work_id
                WHERE wa.author_id = ?
                ORDER BY w.title
            """, (author_id,))
            
            work_rows = cursor.fetchall()
            
            # Process each work
            for row in work_rows:
                # Convert row to Work object
                work = Work(
                    id=row['id'],
                    title=row['title'],
                    creation_date=_parse_db_date(row.get('creation_date')),
                    first_publication_date=_parse_db_date(row.get('first_publication_date')),
                    source_url=row.get('source_url'),
                    scraped_timestamp=_parse_db_datetime(row.get('scraped_timestamp')),
                    copyright_expiry_date=_parse_db_date(row.get('copyright_expiry_date')),
                    status=row.get('status', 'Unknown'),
                    is_collaborative=bool(row.get('is_collaborative', False)),
                    original_language=row.get('original_language'),
                    original_publisher=row.get('original_publisher'),
                    description=row.get('description')
                )
                
                # Get topic for this work
                if row.get('topic_id'):
                    cursor.execute("SELECT id, name FROM topics WHERE id = ?", (row['topic_id'],))
                    topic_row = cursor.fetchone()
                    if topic_row:
                        work.topic = Topic(id=topic_row['id'], name=topic_row['name'])
                
                # Get all authors for this work (not just the requested one)
                cursor.execute("""
                    SELECT a.* FROM authors a
                    JOIN work_authors wa ON a.id = wa.author_id
                    WHERE wa.work_id = ?
                """, (row['id'],))
                
                author_rows = cursor.fetchall()
                for author_row in author_rows:
                    author = Author(
                        id=author_row['id'],
                        name=author_row['name'],
                        birth_date=_parse_db_date(author_row.get('birth_date')),
                        death_date=_parse_db_date(author_row.get('death_date')),
                        nationality=author_row.get('nationality'),
                        bio=author_row.get('bio')
                    )
                    work.authors.append(author)
                
                works.append(work)
            
            logger.info(f"Found {len(works)} works for author ID {author_id}")
    
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving works by author ID {author_id}: {e}", exc_info=True)
    
    return works

def get_next_expiring_works(current_date: date, limit: int = 20) -> List[Work]:
    """
    Retrieves works with copyright expiry dates on or after the current date,
    ordered by the nearest expiry date first.

    Args:
        current_date: Only works expiring on or after this date are included
        limit: Maximum number of results to return (default: 20)
        
    Returns:
        List of upcoming expiring works, sorted by expiry date (soonest first)
    """
    logger.info(f"Fetching works expiring on or after {current_date.isoformat()}, limit {limit}")
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all work IDs with expiry dates on or after the current date
            # Sort by expiry date (ascending) to get the nearest expirations first
            cursor.execute('''
                SELECT id FROM works 
                WHERE copyright_expiry_date IS NOT NULL 
                  AND copyright_expiry_date >= ? 
                  AND status = 'Copyrighted'
                ORDER BY copyright_expiry_date ASC
                LIMIT ?
            ''', (current_date.isoformat(), limit))
            
            work_ids = [row[0] for row in cursor.fetchall()]
            
            # Fetch complete works
            works = []
            for work_id in work_ids:
                work = get_work_by_id(work_id, conn)
                if work:
                    works.append(work)
            
            logger.info(f"Retrieved {len(works)} works expiring on or after {current_date.isoformat()}")
            return works
            
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving next expiring works: {e}")
        return []
