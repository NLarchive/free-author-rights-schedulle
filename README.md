# Free Author Rights Schedule & Explorer

This project aims to identify, track, and analyze the copyright status of creative works (books, movies, music) across different jurisdictions. It uses web scraping, AI enhancement, and a local database to manage information about works, authors, and their potential entry into the public domain. A web-based UI built with Gradio provides an interface for exploring the data and interacting with the AI.

**Disclaimer:** Copyright law is complex and varies significantly by jurisdiction, work type, publication date, and other factors. The calculations and AI analyses in this project are based on available data and simplified rules (primarily author's life + term years, with some specific rules). **This tool should not be considered definitive legal advice.** Always consult reliable sources and legal experts for accurate copyright status determination.

## Features

*   **Database:** Uses SQLite ([`data/copyright_data.db`](d:\CODE\PROJECTS\free-author-rights-schedulle\data\copyright_data.db)) to store information about Works, Authors, Topics, and Jurisdictions. Schema defined in [`src/data_models.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\data_models.py).
*   **Data Management:** CRUD operations for the database handled by [`src/database.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\database.py). Includes functions for searching, retrieving works by status/topic/author, and managing relationships.
*   **Web Scraping:** Includes a spider for Project Gutenberg ([`src/scraper/spiders/gutenberg_spider.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\scraper\spiders\gutenberg_spider.py)) to fetch work details. Framework allows for adding more spiders.
*   **AI Enhancement:** Leverages Google Gemini (via [`src/ai/__init__.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\ai\__init__.py)) to:
    *   Enhance incomplete work and author data.
    *   Verify and determine copyright status across multiple jurisdictions (US, EU, UK, CA, JP, MX).
    *   Generate structured knowledge about works and authors ([`src/knowledge_generator.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\knowledge_generator.py)).
    *   Answer user questions about the data using RAG ([`src/db_rag.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\db_rag.py)).
*   **Copyright Calculation:** [`src/scheduler.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\scheduler.py) calculates estimated copyright expiry dates based on author death dates, publication dates, and jurisdiction-specific rules (defined in [`src/database.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\database.py)).
*   **Web UI:** A Gradio interface ([`src/ui_gradio.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\ui_gradio.py)) provides:
    *   Dashboard overview of the database.
    *   Browsing and searching works, authors, and topics.
    *   Detailed view of works and authors.
    *   On-demand AI copyright analysis for specific works.
    *   AI assistant (RAG) to answer questions about the data.
    *   Data management tools (populate, scrape, enhance).
*   **Command-Line Interface:** [`src/ai_manager.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\ai_manager.py) allows running initialization, scraping, AI enhancement, and knowledge generation/import from the terminal.
*   **Configuration:** Settings managed via `.env` file and [`src/config.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\config.py).

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd free-author-rights-schedulle
    ```
2.  **Create and activate a Python virtual environment:**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure API Key:**
    *   Create a `.env` file in the project root.
    *   Add your Google Gemini API key:
        ```env
        # .env
        GEMINI_API_KEY="YOUR_API_KEY"
        # Optional: Specify a different Gemini model (defaults to gemini-1.5-flash)
        # GEMINI_MODEL="gemini-pro"
        # Optional: Override the current date for simulation (YYYY-MM-DD)
        # CURRENT_DATE="2026-01-01"
        ```
    *   *Note:* The AI features (enhancement, analysis, RAG, generation) require a valid `GEMINI_API_KEY`.

## Usage

### Web Interface (Recommended)

Launch the Gradio UI:

```bash
python src/ui_gradio.py
```

This will start a local web server. Open the provided URL (usually `http://127.0.0.1:7860`) in your browser.

The UI allows you to:
*   View the dashboard with database statistics and highlights.
*   Browse, search, and view details for works, authors, and topics.
*   Trigger AI copyright analysis for selected works.
*   Ask the AI assistant questions about copyright and the data.
*   Manage the database (populate with sample data, scrape from Gutenberg, enhance existing data).

### Command-Line Interface

Use [`src/ai_manager.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\ai_manager.py) for specific tasks:

```bash
# Initialize the database (creates tables, adds default jurisdictions)
python src/ai_manager.py init

# Scrape works from Project Gutenberg and save to DB
python src/ai_manager.py scrape --source gutenberg --query "science fiction" --max 20

# Enhance existing works in the DB using AI (e.g., fill missing info)
python src/ai_manager.py enhance --limit 50
python src/ai_manager.py enhance --topic "Books" --limit 20

# Generate structured knowledge using AI (saves to data/knowledge/)
python src/ai_manager.py generate --topics "Science Fiction" "Fantasy" --count 10

# Import previously generated knowledge into the database
python src/ai_manager.py import --limit 50
python src/ai_manager.py import --topic "Science Fiction" --limit 20

# See all commands
python src/ai_manager.py --help
```

### Configuration

*   **`.env`:** Stores the `GEMINI_API_KEY` and optionally `GEMINI_MODEL` and `CURRENT_DATE`.
*   **[`src/config.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\config.py):**
    *   `DATABASE_PATH`: Location of the SQLite database file.
    *   `TARGET_URLS`: List of URLs for potential future scrapers (currently unused by default).
    *   `USER_AGENT`, `REQUEST_DELAY_SECONDS`: Settings for web scraping politeness.
    *   `DEFAULT_TERM_YEARS`: Default copyright term used if no specific rule applies.
    *   `LOG_FILE`, `LOG_LEVEL`: Logging configuration.
    *   `PREDEFINED_TOPICS`: Topics automatically added during initialization.
    *   `BATCH_SIZE`, `API_RATE_LIMIT`: AI processing configuration.

## System Flow

1.  **Initialization (`init` command or UI start):**
    *   [`src/database.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\database.py) creates the SQLite database and tables if they don't exist.
    *   Default jurisdictions and basic copyright rules are added.
    *   Predefined topics (from [`src/config.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\config.py)) are added.
2.  **Scraping (`scrape` command or UI):**
    *   The appropriate spider (e.g., [`gutenberg_spider.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\scraper\spiders\gutenberg_spider.py)) is selected.
    *   The spider fetches data from the target website.
    *   It parses HTML to extract basic work and author information, creating [`Work`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\data_models.py) and [`Author`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\data_models.py) objects.
    *   AI Enhancement ([`src/ai/__init__.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\ai\__init__.py)) is called to fill missing details (dates, nationality, topic) and verify copyright status across jurisdictions using LLM prompts.
    *   [`src/scheduler.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\scheduler.py) calculates the primary expiry date and status.
    *   [`src/database.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\database.py) saves the enhanced `Work`, `Author`, `Topic`, and relationships to the database.
3.  **UI Interaction ([`src/ui_gradio.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\ui_gradio.py)):**
    *   Fetches data from [`src/database.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\database.py) to display tables and details.
    *   Calls functions in [`src/ai_manager.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\ai_manager.py) or directly interacts with AI/scraping modules for actions like analysis, scraping, and enhancement.
    *   Uses [`src/db_rag.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\db_rag.py) to generate context from the database for the AI assistant.
4.  **AI Enhancement (`enhance` command or UI):**
    *   Retrieves existing works from the database.
    *   Sends batches of works to the AI ([`src/ai.process_batch`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\ai\__init__.py)) for enrichment.
    *   Saves the updated works back to the database.

```mermaid
sequenceDiagram
    participant User
    participant UI (Gradio) / CLI (ai_manager.py)
    participant Database (database.py)
    participant Scraper (e.g., gutenberg_spider.py)
    participant AI (ai/__init__.py)
    participant Scheduler (scheduler.py)
    participant Config (config.py)
    participant DataModels (data_models.py)

    User->>UI (Gradio) / CLI (ai_manager.py): Initiate Action (e.g., Scrape, Browse, Analyze)

    alt Scrape Action
        UI (Gradio) / CLI (ai_manager.py)->>Config: Read Target URL/Source Info
        UI (Gradio) / CLI (ai_manager.py)->>Scraper: scrape_gutenberg_batch(query, max)
        Scraper->>Scraper: Send HTTP Request(url)
        Scraper->>Scraper: Parse HTML Response
        Scraper->>DataModels: Create basic Work/Author objects
        Scraper->>AI: enhance_work_with_llm(work)
        AI->>AI: Call Gemini API (Work Prompt)
        AI-->>Scraper: Enhanced Work object (details, topic)
        Scraper->>AI: verify_copyright_status(work)
        AI->>AI: Call Gemini API (Copyright Prompt)
        AI-->>Scraper: Work with status_by_jurisdiction
        Scraper-->>UI (Gradio) / CLI (ai_manager.py): List[Enhanced Work]

        loop Enhanced Works
            UI (Gradio) / CLI (ai_manager.py)->>Scheduler: update_work_status(work)
            Scheduler->>Database: Get Jurisdiction Rules
            Scheduler->>Scheduler: Calculate Expiry & Status
            Scheduler-->>UI (Gradio) / CLI (ai_manager.py): Updated Work object
            UI (Gradio) / CLI (ai_manager.py)->>Database: save_work(work)
            Database->>Database: Manage Topic, Authors, Work, Links
            Database-->>UI (Gradio) / CLI (ai_manager.py): Saved Work ID
        end
    end

    alt Browse/View Action (UI)
        UI (Gradio) / CLI (ai_manager.py)->>Database: get_all_works() / search_works() / etc.
        Database-->>UI (Gradio) / CLI (ai_manager.py): List[Work] / List[Author] / etc.
        UI (Gradio) / CLI (ai_manager.py)->>User: Display Data
    end

    alt AI Analysis Action (UI)
        User->>UI (Gradio) / CLI (ai_manager.py): Select Work, Click Analyze
        UI (Gradio) / CLI (ai_manager.py)->>Database: get_work_by_id(work_id)
        Database-->>UI (Gradio) / CLI (ai_manager.py): Work object
        UI (Gradio) / CLI (ai_manager.py)->>AI: verify_copyright_status(work)
        AI->>AI: Call Gemini API (Copyright Prompt)
        AI-->>UI (Gradio) / CLI (ai_manager.py): Copyright Status Dict + Reasoning
        UI (Gradio) / CLI (ai_manager.py)->>User: Display Analysis
    end

    alt Ask AI Action (UI)
        User->>UI (Gradio) / CLI (ai_manager.py): Enter Question
        UI (Gradio) / CLI (ai_manager.py)->>Database (via db_rag.py): Find related Works/Authors/Stats
        Database (via db_rag.py)-->>UI (Gradio) / CLI (ai_manager.py): Context String
        UI (Gradio) / CLI (ai_manager.py)->>AI: answer_query_with_context(question, context)
        AI->>AI: Call Gemini API (RAG Prompt)
        AI-->>UI (Gradio) / CLI (ai_manager.py): Answer String
        UI (Gradio) / CLI (ai_manager.py)->>User: Display Answer
    end

```

## Limitations & Future Development

*   **Copyright Complexity:** The current copyright logic in [`src/scheduler.py`](d:\CODE\PROJECTS\free-author-rights-schedulle\src\scheduler.py) is simplified. Real-world copyright is far more nuanced (first publication date, renewals, work type, treaties, etc.).
*   **Scraper Coverage:** Only Project Gutenberg is implemented. More scrapers are needed for broader coverage (e.g., IMDb, MusicBrainz, national libraries).
*   **Scraping Robustness:** Error handling, `robots.txt` compliance, and handling dynamic websites could be improved. Consider using a framework like Scrapy.
*   **UI Refinements:** The Gradio UI is functional but could be enhanced with more advanced filtering, sorting, visualizations, and user feedback mechanisms.
*   **Testing:** More comprehensive unit and integration tests are needed, especially for `scheduler.py`, `database.py`, and AI interactions. Mocking external services (API calls, web requests) is crucial.
*   **Data Validation:** Stricter validation of data coming from scrapers and AI is needed.

*(Further instructions to be added)*