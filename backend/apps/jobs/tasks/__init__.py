"""Demo Hatchet tasks (platform smoke tests). Importing requires HATCHET_CLIENT_TOKEN.

Domain tasks live in their own app's tasks.py; see apps/jobs/registry.py.
"""

from .agent import demo_agent
from .housekeeping import nightly_housekeeping
from .indexing import demo_index

TASKS = [demo_index, demo_agent, nightly_housekeeping]
