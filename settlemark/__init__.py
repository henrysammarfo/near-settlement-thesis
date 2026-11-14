"""Settlemark: reproducible onchain settlement research.

The pipeline is fetch -> validate -> analyse -> chart -> render. Every number that reaches
THESIS.md or the live page is computed from the CSV files in data/, and every CSV row
carries the URL it came from and the UTC time it was fetched.
"""

__version__ = "2.0.0"
