"""Single source of truth for the project name (rename gate §1.4).

A rename must be a single commit: this constant + pyproject.toml.
Do not hardcode the name anywhere else.
"""

__version__ = "0.3.1"
NAME = "snapdec"  # final — rename gate cleared 2026-10-03, see docs/adr/0007
