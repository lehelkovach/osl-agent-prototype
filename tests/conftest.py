"""
Pytest configuration that ensures the project root is importable so tests can
`import src.personal_assistant.*` regardless of how pytest is invoked.
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
