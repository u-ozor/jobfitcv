# app/similarity.py

import numpy as np


def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)

    return np.dot(a, b) / (
        np.linalg.norm(a) * np.linalg.norm(b)
    )
    
    
def jaccard_similarity(set_a, set_b):
    if not set_a and not set_b:
        return 0.0

    inter = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))

    return inter / union if union else 0.0