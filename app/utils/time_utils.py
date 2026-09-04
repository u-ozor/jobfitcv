#app/utils/time_utils.py

from datetime import datetime
from zoneinfo import ZoneInfo


from app.core.config import TIMEZONE

# =========================================================
# Resume-local timestamp
# =========================================================

def local_timestamp():
   return (
        datetime.now(
            ZoneInfo(TIMEZONE)
        ).isoformat()
    )

def file_stamp():
    timestamp = datetime.now(
        ZoneInfo(TIMEZONE)
    ).strftime("%Y%m%d_%H%M%S")

    return timestamp