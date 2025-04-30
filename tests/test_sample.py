import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from datetime import date
import io
import time

# Fix imports by adding the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now imports should work properly
from src.data_models import Work, Author, Jurisdiction, CopyrightRule, Topic
from src import scheduler
from src import database

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
        execution_time = time.time() - self.execution_time[test]
        self.test_results.append({
            'test': test,
            'result': 'PASS',
            'execution_time': execution_time
        })
    
    def addFailure(self, test, err):
        super(DetailedTestResult, self).addFailure(test, err)
        self.failure_count += 1
        execution_time = time.time() - self.execution_time[test]
        self.test_results.append({
            'test': test,
            'result': 'FAIL',
            'error': err,
            'execution_time': execution_time
        })
    
    def addError(self, test, err):
        super(DetailedTestResult, self).addError(test, err)
        self.error_count += 1
        execution_time = time.time() - self.execution_time[test]
        self.test_results.append({
            'test': test,
            'result': 'ERROR',
            'error': err,
            'execution_time': execution_time
        })
    
    def addSkip(self, test, reason):
        super(DetailedTestResult, self).addSkip(test, reason)
        self.skipped_count += 1
        execution_time = time.time() - self.execution_time[test]
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
            test_name = test.id().split('.')[-1]
            test_class = test.id().split('.')[-2]
            execution_time = result['execution_time']
            
            # Get the test docstring (description)
            test_doc = test._testMethodDoc if test._testMethodDoc else "No description provided"
            
            self.stream.writeln(f"\n{test_class}.{test_name} ({execution_time:.3f}s): {result['result']}")
            self.stream.writeln(f"Description: {test_doc}")
            
            if result['result'] == 'FAIL' or result['result'] == 'ERROR':
                self.stream.writeln("Error:")
                err_type, err_value, _ = result['error']
                self.stream.writeln(f"{err_type.__name__}: {err_value}")
            
            if result['result'] == 'SKIP':
                self.stream.writeln(f"Reason: {result['reason']}")

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

# --- Basic tests that use the real database ---
class TestSchedulerBasic(unittest.TestCase):
    """Test basic scheduler module functionality with real database."""
    
    def setUp(self):
        """Set up test data."""
        # Get some jurisdictions to test with
        self.jurisdictions = database.get_all_jurisdictions()
        self.works = database.get_all_works()
        
    def test_calculate_standard_expiry(self):
        """Test standard copyright expiry calculation."""
        # Ensure we have works to test with
        if not self.works:
            self.skipTest("No works found in database.")
            
        # Test with each work
        for work in self.works[:3]:  # Use at most 3 works to keep it manageable
            if work.authors and any(a.death_date for a in work.authors):
                # Standard calculation should work
                # Get all jurisdictions to test with
                for jurisdiction in self.jurisdictions[:2]:  # Use at most 2 jurisdictions
                    result = scheduler.calculate_standard_expiry(work, jurisdiction)
                    self.assertTrue(result is None or isinstance(result, date), 
                                   f"calculate_standard_expiry returned an unexpected value: {result}")
    
    def test_apply_special_rules(self):
        """Test the application of special copyright rules."""
        # Ensure we have works to test with
        if not self.works:
            self.skipTest("No works found in database.")
            
        # Find a jurisdiction with special rules
        jurisdictions_with_rules = [j for j in self.jurisdictions if j.has_special_rules]
        if not jurisdictions_with_rules:
            self.skipTest("No jurisdictions with special rules found.")
            
        # Test with each work and jurisdiction with special rules
        for work in self.works[:3]:  # Use at most 3 works to keep it manageable
            for jurisdiction in jurisdictions_with_rules[:2]:  # Use at most 2 jurisdictions
                result = scheduler.apply_special_rules(work, jurisdiction)
                self.assertTrue(result is None or isinstance(result, date), 
                               f"apply_special_rules returned an unexpected value: {result}")
    
    def test_calculate_expiry(self):
        """Test the main expiry calculation function."""
        # Ensure we have works to test with
        if not self.works:
            self.skipTest("No works found in database.")
            
        # Test with each work
        for work in self.works[:3]:  # Use at most 3 works to keep it manageable
            # Test with each jurisdiction
            for jurisdiction in self.jurisdictions[:2]:  # Use at most 2 jurisdictions
                result = scheduler.calculate_expiry(work, jurisdiction)
                self.assertTrue(result is None or isinstance(result, date), 
                               f"calculate_expiry returned an unexpected value: {result}")
    
    def test_determine_status(self):
        """Test determining copyright status."""
        # Ensure we have works to test with
        if not self.works:
            self.skipTest("No works found in database.")
            
        # Test with each work
        for work in self.works[:3]:  # Use at most 3 works to keep it manageable
            # Test global status
            status = scheduler.determine_status(work)
            self.assertIn(status, ['Public Domain', 'Copyrighted', 'Unknown'], 
                         f"determine_status returned an unexpected value: {status}")
            
            # Test with each jurisdiction
            for jurisdiction in self.jurisdictions[:2]:  # Use at most 2 jurisdictions
                status = scheduler.determine_status(work, jurisdiction)
                self.assertIn(status, ['Public Domain', 'Copyrighted', 'Unknown'], 
                             f"determine_status returned an unexpected value: {status}")
    
    def test_update_work_status(self):
        """Test updating a work's copyright status."""
        # Ensure we have works to test with
        if not self.works:
            self.skipTest("No works found in database.")
            
        # Test with one work
        if self.works:
            work = self.works[0]
            updated_work = scheduler.update_work_status(work)
            self.assertIsInstance(updated_work, Work, f"update_work_status didn't return a Work object")
            self.assertIn(updated_work.status, ['Public Domain', 'Copyrighted', 'Unknown'], 
                         f"update_work_status set an unexpected status: {updated_work.status}")

if __name__ == '__main__':
    # Use our custom test runner instead of the default
    runner = DetailedTestRunner(verbosity=2)
    unittest.main(testRunner=runner)