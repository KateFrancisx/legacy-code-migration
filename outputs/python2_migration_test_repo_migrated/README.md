# Legacy Billing Demo

Small Python 2 repository designed to test a repository-level Python 2 -> Python 3 migration pipeline.

Dependency chain:
main.py -> billing.py -> utils.py
                 |
                 -> config.py

The repository intentionally contains common Python 2 constructs:
- print statements
- xrange
- raw_input is avoided so automated execution is easier
- old-style string formatting
- Python 2 exception syntax
- dict.iteritems()
- unicode/str compatibility helper
- integer-division-sensitive calculation

It also contains a JavaScript file, configuration, requirements, and legacy tests.
