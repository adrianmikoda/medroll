import os

MODEL_CHOICES = {
    "nvidia/llama-embed-nemotron-8b": "nvidia/llama-embed-nemotron-8b",
    "all-MiniLM-L6-v2": "all-MiniLM-L6-v2",
}

MODEL_DIMS = {
    "nvidia/llama-embed-nemotron-8b": 4096,
    "all-MiniLM-L6-v2": 384,
}

MODE_CHOICES = ["overwrite", "open"]

SELECTED_MODEL_KEY = "all-MiniLM-L6-v2"
SELECTED_MODE = "open"

def get_selected_model() -> str:
    return MODEL_CHOICES[SELECTED_MODEL_KEY]

def get_selected_vector_dim() -> int:
    return MODEL_DIMS[SELECTED_MODEL_KEY]

def set_model(key: str) -> None:
    if key not in MODEL_CHOICES:
        raise ValueError(f"Unsupported model key: {key}")
    global SELECTED_MODEL_KEY
    SELECTED_MODEL_KEY = key

def get_selected_mode() -> str:
    return SELECTED_MODE

def set_selected_mode(mode: str) -> None:
    if mode not in MODE_CHOICES:
        raise ValueError(f"Unsupported mode: {mode}")
    global SELECTED_MODE
    SELECTED_MODE = mode
