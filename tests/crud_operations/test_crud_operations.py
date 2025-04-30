import unittest
import sys
import os
import sqlite3
from datetime import date
import logging

# Add parent directory to path to ensure imports work correctly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.data_models import Work, Author, Topic, Jurisdiction
from src import database

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestCRUDOperations(unittest.TestCase):
    """Test cases for the database CRUD (Create, Read, Update, Delete) operations."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Clear any existing data FIRST to ensure isolation
        database.clear_database()
        # Initialize DB schema
        database.init_db()
        # Add default jurisdictions needed for tests
        database.initialize_default_jurisdictions()
        # Get US jurisdiction for the tests
        self.us_jurisdiction = database.get_jurisdiction_by_name("United States")
        # Create a test topic needed for many tests
        self.test_topic = database.add_topic("Test Topic")
    
    def tearDown(self):
        """Clean up after each test."""
        # Clear all data from the database
        database.clear_database()
    
    def test_create_operations(self):
        """Test creating new records in the database."""
        print("\nTesting CREATE operations...")
        
        # 1. Create a new author
        author = Author(
            name="Test Author",
            birth_date=date(1900, 1, 1),
            death_date=date(1980, 12, 31),
            nationality="US"
        )
        saved_author = database.get_or_save_author(author)
        self.assertIsNotNone(saved_author)
        self.assertIsNotNone(saved_author.id)
        self.assertEqual(saved_author.name, "Test Author")
        print(f"Created author: {saved_author.name}, ID: {saved_author.id}")
        
        # 2. Create a new work
        work = Work(
            title="Test Work",
            authors=[saved_author],
            topic=self.test_topic,
            creation_date=date(1950, 5, 15),
            status="Copyrighted",
            primary_jurisdiction=self.us_jurisdiction
        )
        saved_work = database.save_work(work)
        self.assertIsNotNone(saved_work)
        self.assertIsNotNone(saved_work.id)
        self.assertEqual(saved_work.title, "Test Work")
        self.assertEqual(len(saved_work.authors), 1)
        self.assertEqual(saved_work.authors[0].name, "Test Author")
        print(f"Created work: {saved_work.title}, ID: {saved_work.id}")
        
        # 3. Create a new topic
        topic = database.add_topic("Another Test Topic")
        self.assertIsNotNone(topic)
        self.assertIsNotNone(topic.id)
        self.assertEqual(topic.name, "Another Test Topic")
        print(f"Created topic: {topic.name}, ID: {topic.id}")
        
        # Verify total count
        all_works = database.get_all_works()
        self.assertEqual(len(all_works), 1)
        print(f"Total works in database after creation: {len(all_works)}")
    
    def test_read_operations(self):
        """Test reading records from the database."""
        print("\nTesting READ operations...")
        
        # Create some test data first
        author1 = database.get_or_save_author(Author(name="Author One", nationality="US"))
        author2 = database.get_or_save_author(Author(name="Author Two", nationality="GB"))
        
        work1 = database.save_work(Work(
            title="Work One",
            authors=[author1],
            topic=self.test_topic,
            status="Public Domain"
        ))
        work2 = database.save_work(Work(
            title="Work Two",
            authors=[author2],
            topic=self.test_topic,
            status="Copyrighted"
        ))
        work3 = database.save_work(Work(
            title="Collaborative Work",
            authors=[author1, author2],
            topic=self.test_topic,
            status="Copyrighted"
        ))
        
        # 1. Test get_work_by_id
        retrieved_work = database.get_work_by_id(work1.id)
        self.assertIsNotNone(retrieved_work)
        self.assertEqual(retrieved_work.title, "Work One")
        print(f"Retrieved work by ID: {retrieved_work.title}")
        
        # 2. Test get_all_works
        all_works = database.get_all_works()
        self.assertEqual(len(all_works), 3)
        print(f"Retrieved all works: {len(all_works)} works found")
        
        # 3. Test get_works_by_topic
        topic_works = database.get_works_by_topic("Test Topic")
        self.assertEqual(len(topic_works), 3)
        print(f"Retrieved works by topic: {len(topic_works)} works found")
        
        # 4. Test get_public_domain_works
        public_domain_works = database.get_public_domain_works()
        self.assertEqual(len(public_domain_works), 1)
        self.assertEqual(public_domain_works[0].title, "Work One")
        print(f"Retrieved public domain works: {len(public_domain_works)} works found")
        
        # 5. Test search_works
        search_results = database.search_works("Collaborative")
        self.assertEqual(len(search_results), 1)
        self.assertEqual(search_results[0].title, "Collaborative Work")
        print(f"Search results for 'Collaborative': {len(search_results)} works found")
        
        # 6. Test searching by author
        author_search = database.search_works("Author One")
        self.assertEqual(len(author_search), 2)  # Should find Work One and Collaborative Work
        print(f"Search results for 'Author One': {len(author_search)} works found")
    
    def test_update_operations(self):
        """Test updating records in the database."""
        print("\nTesting UPDATE operations...")
        
        # Create initial data
        author = database.get_or_save_author(Author(
            name="Original Author",
            birth_date=date(1900, 1, 1),
            nationality="US"
        ))
        
        work = database.save_work(Work(
            title="Original Title",
            authors=[author],
            topic=self.test_topic,
            creation_date=date(1950, 1, 1),
            status="Copyrighted"
        ))
        
        # 1. Update work title and status
        work.title = "Updated Title"
        work.status = "Public Domain"
        updated_work = database.save_work(work)
        
        self.assertEqual(updated_work.title, "Updated Title")
        self.assertEqual(updated_work.status, "Public Domain")
        print(f"Updated work title to: {updated_work.title}, status to: {updated_work.status}")
        
        # 2. Update author information
        author.death_date = date(1980, 12, 31)
        updated_author = database.get_or_save_author(author)
        
        self.assertEqual(updated_author.death_date, date(1980, 12, 31))
        print(f"Updated author death date to: {updated_author.death_date}")
        
        # 3. Add additional author to work
        new_author = database.get_or_save_author(Author(
            name="Additional Author",
            birth_date=date(1910, 5, 15),
            death_date=date(1990, 8, 20),
            nationality="GB"
        ))
        
        work.authors.append(new_author)
        updated_work = database.save_work(work)
        
        self.assertEqual(len(updated_work.authors), 2)
        author_names = [a.name for a in updated_work.authors]
        self.assertIn("Original Author", author_names)
        self.assertIn("Additional Author", author_names)
        print(f"Added additional author. Work now has {len(updated_work.authors)} authors.")
        
        # 4. Change work's topic
        new_topic = database.add_topic("New Topic")
        work.topic = new_topic
        updated_work = database.save_work(work)
        
        self.assertEqual(updated_work.topic.name, "New Topic")
        print(f"Updated work topic to: {updated_work.topic.name}")
        
        # Verify updates persisted
        retrieved_work = database.get_work_by_id(work.id)
        self.assertEqual(retrieved_work.title, "Updated Title")
        self.assertEqual(retrieved_work.status, "Public Domain")
        self.assertEqual(retrieved_work.topic.name, "New Topic")
        self.assertEqual(len(retrieved_work.authors), 2)
        print("All updates successfully persisted in the database")
    
    def test_delete_operations(self):
        """Test deleting records from the database."""
        print("\nTesting DELETE operations...")
        
        # Create test data
        author1 = database.get_or_save_author(Author(name="Delete Test Author 1"))
        author2 = database.get_or_save_author(Author(name="Delete Test Author 2"))
        
        work1 = database.save_work(Work(
            title="Delete Test Work 1",
            authors=[author1],
            topic=self.test_topic
        ))
        
        work2 = database.save_work(Work(
            title="Delete Test Work 2",
            authors=[author2],
            topic=self.test_topic
        ))
        
        # Verify works were created
        all_works_before = database.get_all_works()
        self.assertEqual(len(all_works_before), 2)
        print(f"Initial works count: {len(all_works_before)}")
        
        # Delete works and verify - use proper delete_work function
        success = database.delete_work(work1.id)
        self.assertTrue(success)
        all_works_after_first_delete = database.get_all_works()
        self.assertEqual(len(all_works_after_first_delete), 1)
        print(f"Work count after first delete: {len(all_works_after_first_delete)}")
        
        success = database.delete_work(work2.id)
        self.assertTrue(success)
        all_works_after_second_delete = database.get_all_works()
        self.assertEqual(len(all_works_after_second_delete), 0)
        print(f"Work count after second delete: {len(all_works_after_second_delete)}")
        
        # Clear entire database
        database.clear_database()
        all_works_after_clear = database.get_all_works()
        self.assertEqual(len(all_works_after_clear), 0)
        print("Database cleared successfully")
    
    def _delete_work(self, work_id):
        """
        Legacy helper method kept for reference.
        The proper database.delete_work() function should be used instead.
        """
        return database.delete_work(work_id)
    
    def test_bulk_operations(self):
        """Test bulk operations for creating and retrieving multiple works."""
        print("\nTesting bulk operations...")
        
        # Create test data for bulk insert
        bulk_data = [
            {
                "title": "Bulk Work 1",
                "authors": [{"name": "Bulk Author 1", "birth_date": "1800-01-01", "death_date": "1880-12-31"}],
                "creation_date": "1870-05-10",
                "status": "Public Domain",
                "primary_jurisdiction": self.us_jurisdiction
            },
            {
                "title": "Bulk Work 2",
                "authors": [{"name": "Bulk Author 2", "birth_date": "1900-03-15", "death_date": "1980-07-22"}],
                "creation_date": "1950-11-30",
                "status": "Copyrighted",
                "primary_jurisdiction": self.us_jurisdiction
            },
            {
                "title": "Bulk Work 3",
                "authors": [
                    {"name": "Bulk Author 3", "birth_date": "1910-06-20", "death_date": "1990-02-14"},
                    {"name": "Bulk Author 4", "birth_date": "1912-08-05", "death_date": "1995-04-30"}
                ],
                "creation_date": "1960-09-25",
                "status": "Copyrighted",
                "primary_jurisdiction": self.us_jurisdiction
            }
        ]
        
        # Add bulk works using the add_famous_works method
        topic_name = "Bulk Test Topic"
        database.add_topic(topic_name)
        count = database.add_famous_works(topic_name, bulk_data)
        
        self.assertEqual(count, 3)
        print(f"Bulk inserted {count} works")
        
        # Verify all works were added
        all_works = database.get_all_works()
        self.assertEqual(len(all_works), 3)
        
        # Verify works by topic
        topic_works = database.get_works_by_topic(topic_name)
        self.assertEqual(len(topic_works), 3)
        print(f"Retrieved {len(topic_works)} works from topic '{topic_name}'")
        
        # Verify a collaborative work was correctly added with multiple authors
        collaborative_works = [w for w in all_works if len(w.authors) > 1]
        self.assertEqual(len(collaborative_works), 1)
        self.assertEqual(len(collaborative_works[0].authors), 2)
        print(f"Verified collaborative work with {len(collaborative_works[0].authors)} authors")

if __name__ == "__main__":
    print(f"Running CRUD operation tests at {date.today().isoformat()}")
    unittest.main()