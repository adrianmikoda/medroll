from pydantic import BaseModel


class NerEntity(BaseModel):
    """A single entity extracted by the LLM"""
    text: str       # the original phrase from input document
    tag: str        # anonymization tag, e.g. SURNAME, CITY, PHONE_NUMBER


class NerExtractionResult(BaseModel):
    """Structured output expected from the LLM"""
    entities: list[NerEntity] = []
    document_language: str = "unknown"


class MedicalDocument(BaseModel):
    session_id: str
    filename: str
    chunks: list[str]
    content: str
    language: str
    processing_type: str  # simple or advanced
    entities_removed: list[NerEntity] = []
    status: str = "processed"
