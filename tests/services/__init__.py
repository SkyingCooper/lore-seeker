"""Service tests.

When unittest discovery starts from tests/, this package is imported as the
top-level services package. Extend the path so backend.services remains
importable during discovery.
"""

from pathlib import Path


BACKEND_SERVICES = Path(__file__).resolve().parents[2] / "backend" / "services"
__path__.append(str(BACKEND_SERVICES))
