# Ensures the BEACON root package is on sys.path when tests in this directory
# are collected individually or together. Without this, importing
# app.crawlers.site_aggregator causes a circular import error when pytest
# collects multiple crawler test files in the same run.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
