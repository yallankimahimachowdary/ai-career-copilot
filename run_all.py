#!/usr/bin/env python3
"""
run_all.py
----------
Root entrypoint delegating directly to scripts/run_all.py.
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scripts.run_all import main

if __name__ == "__main__":
    main()
