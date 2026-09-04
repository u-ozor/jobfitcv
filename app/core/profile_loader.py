import json


PROFILE_PATH = "data/user_profile.json"


def load_profile():
    with open(PROFILE_PATH, "r") as f:
        return json.load(f)