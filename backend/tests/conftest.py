import os

# Imported modules require a key at import time. Tests never call Mistral.
os.environ.setdefault("MISTRAL_API_KEY", "test-key-not-used")
