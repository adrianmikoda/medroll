import os
import json
from .extractors import PDFExtractor, DocxExtractor, DoclingExtractor
from .utils.text_chunker import TextProcessor
from .classifier import DocumentClassifier
from .models import MedicalDocument, NerEntity


class FileConverter:
    SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

    def __init__(self, file_path: str, session_id: str, processor):
        self.file_path = file_path
        self.session_id = session_id
        self.processor = processor
        self.extension = os.path.splitext(file_path)[1].lower()
        self.simple_extractors = {
            ".pdf": PDFExtractor(),
            ".docx": DocxExtractor(),
        }
        self.advanced_extractor = DoclingExtractor()

    async def convert(self) -> str:
        if self.extension not in self.SUPPORTED_EXTENSIONS:
            return json.dumps(
                {
                    "status": "error",
                    "message": (
                        f"Unsupported file type: {self.extension}. "
                        "Supported: .pdf, .docx"
                    ),
                }
            )

        is_adv = DocumentClassifier.is_complex(self.file_path)
        p_type = "advanced" if is_adv else "simple"

        try:
            extractor = (
                self.advanced_extractor
                if is_adv
                else self.simple_extractors.get(self.extension)
            )
            if extractor is None:
                return json.dumps(
                    {
                        "status": "error",
                        "message": (
                            f"Unsupported file type: {self.extension}. "
                            "Supported: .pdf, .docx"
                        ),
                    }
                )

            raw_text = extractor.extract(self.file_path)
            if not raw_text.strip():
                return json.dumps(
                    {
                        "status": "error",
                        "message": "No text extracted from document",
                    }
                )

            chunks = TextProcessor.split_into_chunks(raw_text)
            if not chunks:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "Failed to split document into chunks",
                    }
                )

            processed_chunks = []
            for chunk in chunks:
                llm_result = await self.processor.process_chunk(
                    chunk, is_advanced=is_adv
                )
                processed_chunks.append(llm_result)
            return self._build_response(processed_chunks, p_type)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def _build_response(self, llm_result: list, p_type: str) -> str:
        content_key = "cleaned_markdown" if p_type == "advanced" else "cleaned_text"

        # Language detected by LLM during NER extraction
        detected_lang = "unknown"
        for res in llm_result:
            lang = res.get("document_language", "unknown")
            if lang != "unknown":
                detected_lang = lang
                break

        final_content = "\n\n".join(
            [res.get(content_key, "") for res in llm_result]
        )

        # Collect all applied entities from all chunks
        all_entities: list[NerEntity] = []
        for res in llm_result:
            for ent_dict in res.get("entities_removed", []):
                if isinstance(ent_dict, dict):
                    all_entities.append(NerEntity(**ent_dict))
                elif isinstance(ent_dict, NerEntity):
                    all_entities.append(ent_dict)

        # De-duplicate entities across chunks (same text+tag)
        seen: set[tuple[str, str]] = set()
        unique_entities: list[NerEntity] = []
        for ent in all_entities:
            key = (ent.text, ent.tag)
            if key not in seen:
                seen.add(key)
                unique_entities.append(ent)

        doc_obj = MedicalDocument(
            session_id=self.session_id,
            filename=os.path.basename(self.file_path),
            chunks=[res.get(content_key, "") for res in llm_result],
            content=final_content,
            language=detected_lang,
            processing_type=p_type,
            entities_removed=unique_entities,
        )
        return doc_obj.model_dump_json(indent=4)
