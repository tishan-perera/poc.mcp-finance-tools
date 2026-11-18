"""The committed CSV is exactly what the generator produces."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_committed_books_match_the_generator():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "generate_synthetic_books.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
