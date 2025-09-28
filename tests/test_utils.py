import pytest
from story_builder.utils import sanitize_project_name

def test_sanitize_project_name():
    assert sanitize_project_name("My Project!") == "My_Project_"
    assert sanitize_project_name("safe-name_123") == "safe-name_123"
    assert sanitize_project_name("a/b\\c") == "a_b_c"
