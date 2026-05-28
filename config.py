import os

MODEL_CHOICES = {
    "all-MiniLM-L6-v2": "all-MiniLM-L6-v2",
    "sentence-transformers/embeddinggemma-300m-medical": "sentence-transformers/embeddinggemma-300m-medical",
    "nvidia/llama-embed-nemotron-8b": "nvidia/llama-embed-nemotron-8b",

}

MODEL_DIMS = {
    "all-MiniLM-L6-v2": 384,
    "sentence-transformers/embeddinggemma-300m-medical": 768,
    "nvidia/llama-embed-nemotron-8b": 4096,
}

MODE_CHOICES = ["overwrite", "open"]

SELECTED_MODEL_KEY = "sentence-transformers/embeddinggemma-300m-medical"
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
