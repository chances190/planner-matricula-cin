#!/usr/bin/env python3
"""Standalone entrypoint for the planner package.

All logic has been moved into ``planner/`` modules.  This script exists so that
users can continue to call ``./planner.py`` and our tests remain simple.
"""

from __future__ import annotations

from planner.cli import main


if __name__ == "__main__":
    main()
