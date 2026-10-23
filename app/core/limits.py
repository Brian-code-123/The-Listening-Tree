"""Shared bounds for request parameters."""
from typing import Annotated

from fastapi import Path

# The database ids are BIGINT; anything outside this range cannot name a row, and
# a value past 2**63-1 makes the driver raise instead of simply matching nothing.
MAX_DB_ID = 2**63 - 1

DbId = Annotated[int, Path(ge=1, le=MAX_DB_ID)]
