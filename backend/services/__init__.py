"""Backend services package.

During ``unittest discover tests`` with ``PYTHONPATH=backend``, Python imports
this package as top-level ``services`` before it sees ``tests/services``. Adding
the optional tests path keeps discovery working without affecting production.
"""

from pathlib import Path


_tests_services = Path(__file__).resolve().parents[2] / "tests" / "services"
if _tests_services.exists():
    __path__.append(str(_tests_services))
