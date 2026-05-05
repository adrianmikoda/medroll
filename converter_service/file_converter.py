import os
import json
from .extractors import PDFExtractor, DocxExtractor, DoclingExtractor 
from .utils.language_detector import LanguageService
from .utils.text_chunker import TextProcessor
from .classifier import DocumentClassifier
from .models import MedicalDocument

class FileConverter:
    def __init__(self, file_path: str, session_id: str):
        self.file_path = file_path
        self.session_id = session_id
        self.extension = os.path.splitext(file_path)[1].lower()
        self.simple_extractors = {
            '.pdf': PDFExtractor(),
            '.docx': DocxExtractor(),
        }
        self.advanced_extractor = DoclingExtractor()
    
    def convert(self)->str:
        is_adv = DocumentClassifier.is_complex(self.file_path)
        p_type = "advanced" if is_adv else "simple"

        try:
            extractor = self.advanced_extractor if is_adv else self.simple_extractors.get(self.extension)
            raw_text = extractor.extract(self.file_path)
            return self._build_response(raw_text, p_type)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
    
    def _build_response(self, text:str, p_type:str)->str:
        is_valid, lang = LanguageService.detect(text)
        chunks = TextProcessor.split_into_chunks(text)
        doc_obj = MedicalDocument(
            session_id=self.session_id,
            filename=os.path.basename(self.file_path),
            chunks = chunks,
            content=text,
            language=lang if is_valid else "unknown",
            processing_type=p_type
        )
        return doc_obj.model_dump_json(indent=4)