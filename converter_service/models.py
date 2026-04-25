from pydantic import BaseModel
#Pydantic
class MedicalDocument(BaseModel):
    session_id: str
    filename: str
    chunks: list[str]
    content: str
    language: str
    processing_type: str # simple or advanced
    status: str = "processed"