# scripts/preprocess_resume_data.py

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # allow direct invocation

from app.pipelines.preprocessing_pipeline import (
    preprocess_resume_chunks
)


if __name__ == "__main__":
    preprocess_resume_chunks()