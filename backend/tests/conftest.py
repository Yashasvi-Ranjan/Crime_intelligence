"""Hermetic test environment.

A developer's .env (live Zetaris, Nightshift token, SAMPLE_MODE) must never change test outcomes, and a
fresh clone with a judge's .env must pass too. Real environment variables take precedence over dotenv
files, so pin the integration switches here before ``app.config`` is imported.
"""

import os

os.environ["ZETARIS_ENABLED"] = "false"
os.environ["SAMPLE_MODE"] = "false"
os.environ["NIGHTSHIFT_API_KEY"] = ""
os.environ["NIGHTSHIFT_API_KEY_FILE"] = ""
