"""Evaluation harnesses (not part of the request path).

The embeddings recall@k bake-off (research R2) measures how well predicate resolution grounds a
user phrase to the correct EOL ontology URI — the deciding evidence for keeping the local Ollama
embeddings default vs upgrading to a hosted model, and for tuning the resolution confidence gates.
"""
