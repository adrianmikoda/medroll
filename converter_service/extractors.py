import fitz
from docx import Document
from abc import ABC, abstractmethod

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: str) -> str:
        pass

class PDFExtractor(BaseExtractor):
    def extract(self, file_path: str) -> str:
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text.strip()

class DocxExtractor(BaseExtractor):
    def extract(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs]).strip()
    
class DoclingExtractor(BaseExtractor):
    def __init__(self):
        self.converter = None

    def extract(self, file_path: str) -> str:
        if self.converter is None:
            try:
                from docling.document_converter import DocumentConverter
            except ImportError:
                raise ImportError(
                    "docling is not installed. To use advanced extraction, please install docling."
                )
            self.converter = DocumentConverter()
        result = self.converter.convert(file_path)
        return result.document.export_to_markdown()