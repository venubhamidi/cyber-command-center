"""Test setup for the whole repository. Runs before anything is imported: tests use the test
database (they empty tables) and never the development one."""
import os

from harness.testing import test_database_url

os.environ["APP_DATABASE_URL"] = test_database_url()
os.environ["APP_ENVIRONMENT"] = "test"
os.environ["APP_RATE_LIMIT_PER_MINUTE"] = "0"
os.environ["APP_LLM_PROVIDER"] = "mock"
