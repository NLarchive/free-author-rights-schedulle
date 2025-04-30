# tests/test_scheduler.py
import unittest
import sys
import os
import logging
import time
from datetime import date, timedelta
from typing import List, Dict

# Fix imports by adding the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now imports should work properly
from src.data_models import Work, Author, Jurisdiction, CopyrightRule, Topic
from src import scheduler
from src import database

# --- Disable Logging During Tests ---
logging.disable(logging.CRITICAL)

# --- Custom Test Result Class ---
class DetailedTestResult(unittest.TextTestResult):
    """Custom TestResult class that provides more detailed output for each test."""
    
    def __init__(self, stream, descriptions, verbosity):
        super(DetailedTestResult, self).__init__(stream, descriptions, verbosity)
        self.stream = stream
        self.verbosity = verbosity
        self.success_count = 0
        self.failure_count = 0
        self.error_count = 0
        self.skipped_count = 0
        self.test_results = []
        self.execution_time = {}
    
    def startTest(self, test):
        super(DetailedTestResult, self).startTest(test)
        self.execution_time[test] = time.time()
    
    def addSuccess(self, test):
        super(DetailedTestResult, self).addSuccess(test)
        self.success_count += 1
        start_time = self.execution_time.get(test) # Use .get()
        execution_time = time.time() - start_time if start_time else 0.0 # Handle None
        self.test_results.append({
            'test': test,
            'result': 'PASS',
            'execution_time': execution_time
        })

    def addFailure(self, test, err):
        super(DetailedTestResult, self).addFailure(test, err)
        self.failure_count += 1
        start_time = self.execution_time.get(test) # Use .get()
        execution_time = time.time() - start_time if start_time else 0.0 # Handle None
        self.test_results.append({
            'test': test,
            'result': 'FAIL',
            'error': err,
            'execution_time': execution_time
        })

    def addError(self, test, err):
        super(DetailedTestResult, self).addError(test, err)
        self.error_count += 1
        start_time = self.execution_time.get(test) # Use .get()
        execution_time = time.time() - start_time if start_time else 0.0 # Handle None
        self.test_results.append({
            'test': test,
            'result': 'ERROR',
            'error': err,
            'execution_time': execution_time
        })

    def addSkip(self, test, reason):
        super(DetailedTestResult, self).addSkip(test, reason)
        self.skipped_count += 1
        start_time = self.execution_time.get(test) # Use .get()
        execution_time = time.time() - start_time if start_time else 0.0 # Handle None
        self.test_results.append({
            'test': test,
            'result': 'SKIP',
            'reason': reason,
            'execution_time': execution_time
        })
    
    def printDetailedReport(self):
        self.stream.writeln("\n=== DETAILED TEST REPORT ===")
        
        # Print summary
        self.stream.writeln(f"Total Tests: {self.testsRun}")
        self.stream.writeln(f"Passed: {self.success_count}")
        self.stream.writeln(f"Failed: {self.failure_count}")
        self.stream.writeln(f"Errors: {self.error_count}")
        self.stream.writeln(f"Skipped: {self.skipped_count}")
        
        # Print individual test results
        self.stream.writeln("\n--- Individual Test Results ---")
        
        for result in self.test_results:
            test = result['test']
            execution_time = result['execution_time']

            # Safely get test name and class
            test_id = getattr(test, 'id', lambda: 'Unknown Test')() # Use getattr for safety
            test_name = test_id.split('.')[-1]
            test_class = test_id.split('.')[-2] if '.' in test_id else 'UnknownClass'

            # Get the test docstring (description)
            test_doc = getattr(test, '_testMethodDoc', "No description provided or Class Setup/TearDown")
            if not test_doc: # Handle empty string docstrings
                test_doc = "No description provided or Class Setup/TearDown"
                
            self.stream.writeln(f"\n{test_class}.{test_name} ({execution_time:.3f}s): {result['result']}")
            self.stream.writeln(f"Description: {test_doc}")

            if result['result'] == 'FAIL' or result['result'] == 'ERROR':
                self.stream.writeln("Error:")
                # Check if error info is a tuple (expected format)
                if isinstance(result.get('error'), tuple) and len(result['error']) >= 2:
                    err_type, err_value = result['error'][:2]
                    err_name = getattr(err_type, '__name__', 'UnknownErrorType')
                    self.stream.writeln(f"{err_name}: {err_value}")
                else:
                    self.stream.writeln(f"Unexpected error format: {result.get('error')}")


            if result['result'] == 'SKIP':
                self.stream.writeln(f"Reason: {result.get('reason', 'No reason provided')}") # Use .get()

class DetailedTestRunner(unittest.TextTestRunner):
    """Custom TestRunner that uses DetailedTestResult to generate detailed reports."""
    
    def __init__(self, stream=None, descriptions=True, verbosity=1,
                 failfast=False, buffer=False, resultclass=None, warnings=None,
                 tb_locals=False):
        if resultclass is None:
            resultclass = DetailedTestResult
        super(DetailedTestRunner, self).__init__(
            stream=stream, descriptions=descriptions, verbosity=verbosity,
            failfast=failfast, buffer=buffer, resultclass=resultclass,
            warnings=warnings, tb_locals=tb_locals)
    
    def run(self, test):
        result = super(DetailedTestRunner, self).run(test)
        result.printDetailedReport()
        return result

# Current date for consistent testing
TODAY = date(2025, 4, 29)

class TestSchedulerMethods(unittest.TestCase):
    """Test all methods in the scheduler module using actual database content."""

    @classmethod
    def setUpClass(cls):
        """Initialize database connection and ensure data exists for all tests."""
        # Initialize DB schema and default jurisdictions first
        database.init_db()
        database.initialize_default_jurisdictions()

        cls.works = database.get_all_works()

        # If database is empty, add minimal sample data needed for scheduler tests
        if not cls.works:
            print("\nINFO: Database empty, adding sample data for scheduler tests...")

            try:
                # Add a topic
                book_topic = database.add_topic("Test Book")
                movie_topic = database.add_topic("Test Movie")

                # Create authors (don't add them directly to DB here)
                author1 = Author(name="Author A", birth_date=date(1900, 1, 1), death_date=date(1970, 12, 31))
                author2 = Author(name="Author B (Living)", birth_date=date(1950, 1, 1), death_date=None)
                author_unknown = Author(name="Author C (Unknown Dates)")

                # Create works with authors
                work1 = Work(title="PD Book", authors=[author1], topic=book_topic, creation_date=date(1920, 1, 1)) # Pre-1923 US
                work2 = Work(title="Copyrighted Book", authors=[author2], topic=book_topic, creation_date=date(1980, 1, 1)) # Post-1978 US
                work3 = Work(title="Rule of Shorter Term", authors=[author1], topic=book_topic, creation_date=date(1950, 1, 1), first_publication_date=date(1950,1,1)) # US 1923-1977
                work4 = Work(title="Unknown Date Work", authors=[author_unknown], topic=movie_topic) # Unknown status

                # Add works to DB using save_work
                database.save_work(work1) # Changed from add_work
                database.save_work(work2) # Changed from add_work
                database.save_work(work3) # Changed from add_work
                database.save_work(work4) # Changed from add_work

                # Re-fetch works after adding sample data
                cls.works = database.get_all_works()
                print(f"INFO: Added {len(cls.works)} sample works.")

            except Exception as e:
                raise RuntimeError(f"Failed to populate database for scheduler tests: {e}")


        # Ensure we have at least some works now
        if not cls.works:
            # If still no works after trying to add, something is fundamentally wrong
            raise RuntimeError("Database is still empty after attempting to add sample data.")

        cls.jurisdictions = database.get_all_jurisdictions()

        
        # Ensure we have at least some works in the database
        if not cls.works:
            raise unittest.SkipTest("No works found in database. Tests need actual works to run.")
        
        # Save references to different work types for easier testing
        cls.works_by_status = {}
        cls.works_by_jurisdiction = {}
        cls.works_by_type = {}
        
        # Categorize works for testing
        for work in cls.works:
            # By status
            status = work.status
            if status not in cls.works_by_status:
                cls.works_by_status[status] = []
            cls.works_by_status[status].append(work)
            
            # By primary jurisdiction
            if work.primary_jurisdiction:
                jur_code = work.primary_jurisdiction.code
                if jur_code not in cls.works_by_jurisdiction:
                    cls.works_by_jurisdiction[jur_code] = []
                cls.works_by_jurisdiction[jur_code].append(work)
            
            # By type (topic)
            if work.topic:
                topic_name = work.topic.name
                if topic_name not in cls.works_by_type:
                    cls.works_by_type[topic_name] = []
                cls.works_by_type[topic_name].append(work)
        
        print(f"Found {len(cls.works)} works, {len(cls.jurisdictions)} jurisdictions in database")
        print(f"Works by status: {', '.join(f'{k}: {len(v)}' for k, v in cls.works_by_status.items())}")
        print(f"Works by jurisdiction: {', '.join(f'{k}: {len(v)}' for k, v in cls.works_by_jurisdiction.items())}")
        print(f"Works by type: {', '.join(f'{k}: {len(v)}' for k, v in cls.works_by_type.items())}")
    
    def setUp(self):
        """Set up for each test."""
        # This runs before each test method
        # Nothing needed for now as we're just reading the database
        pass
    
    def tearDown(self):
        """Clean up after each test."""
        # This runs after each test method
        # Nothing needed for now as we're just reading the database
        pass
    
    # --- Test calculate_standard_expiry ---
    def test_calculate_standard_expiry_with_author_death(self):
        """Test standard expiry calculation based on author death date."""
        # Find a work with an author with death date
        works_with_deceased_authors = []
        for work in self.works:
            if work.authors and any(a.death_date for a in work.authors):
                works_with_deceased_authors.append(work)
        
        if not works_with_deceased_authors:
            self.skipTest("No works with deceased authors found in database.")
        
        work = works_with_deceased_authors[0]  # Take the first one
        last_author_death = max(a.death_date for a in work.authors if a.death_date)
        
        # Get a jurisdiction with a known term_years_after_death
        jurisdiction = next((j for j in self.jurisdictions if j.term_years_after_death), None)
        if not jurisdiction:
            self.skipTest("No jurisdiction with term_years_after_death found.")
        
        # Calculate expected expiry (last death + term years, end of year)
        expected_expiry = date(last_author_death.year + jurisdiction.term_years_after_death, 12, 31)
        
        # Run the calculation
        expiry = scheduler.calculate_standard_expiry(work, jurisdiction)
        
        self.assertEqual(expiry, expected_expiry)
        
    def test_calculate_standard_expiry_with_creation_date(self):
        """Test standard expiry calculation based on creation date."""
        # Find a work with creation date but no author death dates
        works_with_creation = []
        for work in self.works:
            if work.creation_date and not any(a.death_date for a in work.authors):
                works_with_creation.append(work)
        
        if not works_with_creation:
            self.skipTest("No works with creation date but no author death dates found.")
        
        work = works_with_creation[0]  # Take the first one
        
        # Get a jurisdiction with a known term_years_after_death
        jurisdiction = next((j for j in self.jurisdictions if j.term_years_after_death), None)
        if not jurisdiction:
            self.skipTest("No jurisdiction with term_years_after_death found.")
        
        # Calculate expected expiry (creation + term years, end of year)
        expected_expiry = date(work.creation_date.year + jurisdiction.term_years_after_death, 12, 31)
        
        # Run the calculation
        expiry = scheduler.calculate_standard_expiry(work, jurisdiction)
        
        self.assertEqual(expiry, expected_expiry)
    
    def test_calculate_standard_expiry_with_no_dates(self):
        """Test standard expiry calculation with insufficient information."""
        # Create a work with no dates
        work = Work(title="Test Work with No Dates", authors=[])
        
        # Run the calculation
        expiry = scheduler.calculate_standard_expiry(work)
        
        # Should return None if insufficient information
        self.assertIsNone(expiry)
    
    # --- Test apply_special_rules ---
    def test_apply_special_rules(self):
        """Test applying special copyright rules for a jurisdiction."""
        # Find a jurisdiction with special rules
        jurisdiction = next((j for j in self.jurisdictions if j.has_special_rules), None)
        if not jurisdiction:
            self.skipTest("No jurisdiction with special rules found.")
        
        # Get the special rules for this jurisdiction
        rules = database.get_copyright_rules_for_jurisdiction(jurisdiction.id)
        if not rules:
            self.skipTest(f"No special rules found for jurisdiction {jurisdiction.name}.")
        
        # Test each rule with an appropriate work
        for rule in rules:
            # Find or create a work that matches this rule
            # This part is tricky because we need to find works that match specific rules
            # For now, we'll just test that the function doesn't crash
            work = self.works[0]  # Just use the first work
            
            # Run the calculation
            expiry = scheduler.apply_special_rules(work, jurisdiction)
            
            # Just check that it returns something (either a date or None)
            self.assertTrue(expiry is None or isinstance(expiry, date))
    
    # --- Test calculate_expiry ---
    def test_calculate_expiry(self):
        """Test the main expiry calculation function."""
        # Test with each work
        for work in self.works:
            # Test with each jurisdiction
            for jurisdiction in self.jurisdictions:
                # Run the calculation
                expiry = scheduler.calculate_expiry(work, jurisdiction)
                
                # Check that it returns a date or None
                self.assertTrue(expiry is None or isinstance(expiry, date))
    
    # --- Test determine_status ---
    def test_determine_status(self):
        """Test determining copyright status (Public Domain, Copyrighted, Unknown)."""
        # Test with each work
        for work in self.works:
            # Run the status determination
            status = scheduler.determine_status(work, current_date=TODAY)
            
            # Check that it returns a valid status
            self.assertIn(status, ['Public Domain', 'Copyrighted', 'Unknown'])
    
    def test_determine_status_with_jurisdiction(self):
        """Test determining copyright status for a specific jurisdiction."""
        # Test with each work
        for work in self.works:
            # Test with each jurisdiction
            for jurisdiction in self.jurisdictions:
                # Run the status determination
                status = scheduler.determine_status(work, jurisdiction, current_date=TODAY)
                
                # Check that it returns a valid status
                self.assertIn(status, ['Public Domain', 'Copyrighted', 'Unknown'])
    
    # --- Test calculate_multi_jurisdiction_status ---
    def test_calculate_multi_jurisdiction_status(self):
        """Test calculating status across multiple jurisdictions."""
        # Test with each work
        for work in self.works:
            # Run the multi-jurisdiction status calculation
            status_map = scheduler.calculate_multi_jurisdiction_status(work, self.jurisdictions)
            
            # Check that it returns a dictionary with correct keys and values
            self.assertIsInstance(status_map, dict)
            for jur_code, status in status_map.items():
                self.assertIn(status, ['Public Domain', 'Copyrighted', 'Unknown'])
                self.assertTrue(any(j.code == jur_code for j in self.jurisdictions))
    
    # --- Test update_work_status ---
    def test_update_work_status(self):
        """Test updating a work's copyright status."""
        # Test with each work
        for work in self.works:
            # Make a copy of the work to not modify the original
            work_copy = Work(
                id=work.id,
                title=work.title,
                authors=work.authors.copy() if work.authors else [],
                topic=work.topic,
                creation_date=work.creation_date,
                first_publication_date=work.first_publication_date,
                source_url=work.source_url,
                copyright_expiry_date=None,  # Clear these for testing
                status="Unknown",  # Clear these for testing
                primary_jurisdiction=work.primary_jurisdiction,
                status_by_jurisdiction={}  # Clear these for testing
            )
            
            # Run the update
            updated_work = scheduler.update_work_status(work_copy)
            
            # Check that status fields are updated
            self.assertIsInstance(updated_work, Work)
            self.assertIn(updated_work.status, ['Public Domain', 'Copyrighted', 'Unknown'])
            self.assertTrue(updated_work.copyright_expiry_date is None or 
                          isinstance(updated_work.copyright_expiry_date, date))
            self.assertIsInstance(updated_work.status_by_jurisdiction, dict)
    
    # --- Test get_days_until_expiry ---
    def test_get_days_until_expiry(self):
        """Test calculating days until copyright expiry."""
        # Test with each work
        for work in self.works:
            # Run the calculation
            days = scheduler.get_days_until_expiry(work, current_date=TODAY)
            
            # Check result
            if days is not None:
                self.assertIsInstance(days, int)
            
            # Validate the result matches the status
            status = scheduler.determine_status(work, current_date=TODAY)
            if status == 'Public Domain':
                self.assertIsNone(days, "Public Domain work should return None for days until expiry")
    
    # --- Test get_works_by_status_in_jurisdiction ---
    def test_get_works_by_status_in_jurisdiction(self):
        """Test filtering works by status in a jurisdiction."""
        # Test with each jurisdiction
        for jurisdiction in self.jurisdictions:
            if not jurisdiction.code:
                continue
                
            # Test with each status
            for status in ['Public Domain', 'Copyrighted', 'Unknown']:
                # Run the filter
                filtered_works = scheduler.get_works_by_status_in_jurisdiction(jurisdiction.code, status)
                
                # Check that it returns a list
                self.assertIsInstance(filtered_works, list)
                
                # Check that all returned works have the requested status in this jurisdiction
                for work in filtered_works:
                    work_status = scheduler.determine_status(work, jurisdiction, current_date=TODAY)
                    self.assertEqual(work_status, status)

if __name__ == '__main__':
    # Use our custom test runner
    runner = DetailedTestRunner(verbosity=2)
    unittest.main(testRunner=runner)