import json
import os

EXPERIENCE_PATH = "data/experience.json"


def load_experience():
    if not os.path.exists(EXPERIENCE_PATH):
        return {"experience": [], "education": [], "certifications": []}
    with open(EXPERIENCE_PATH) as f:
        return json.load(f)
