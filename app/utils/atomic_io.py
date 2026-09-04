# app/utils/atomic_io.py
#
# write-then-rename gives atomicity: os.replace() is a single filesystem
# operation, so a concurrent read never sees a partial file, and a killed
# process (e.g. uvicorn --reload restarting mid-write) leaves the temp file
# orphaned instead of corrupting the real one.

import json
import os


def atomic_write_json(path, data):
    tmp_path = f"{path}.tmp-{os.getpid()}"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)
