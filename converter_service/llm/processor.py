import json
import re
from .llama_local import LocalLlamaInference
from .prompt_manager import PromptManager
from .redactor import Redactor
from ..models import NerEntity, NerExtractionResult

_TRANSCRIPT_PLACEHOLDER = "{transcript_text}"
_MAX_RETRIES = 2

_SYSTEM_MSG_NER = (
    "You are a precise Named Entity Recognition (NER) engine for medical document anonymization. "
    "You extract PII/PHI entities and return them as a structured JSON list. "
    "You NEVER rewrite or modify the input text. Return JSON only."
)


class MedicalProcessor:
    def __init__(self):
        self.llama = LocalLlamaInference()
        self.prompt_manager = PromptManager()

    async def process_chunk(self, chunk_text: str, is_advanced: bool) -> dict:
        """
        Process a single text chunk through the NER-only pipeline.

        1. Send chunk to LLM → get structured entity list
        2. Apply deterministic redaction on the original text
        3. Return redacted text + entity list
        """
 
        ner_result = await self._extract_entities(chunk_text, is_advanced)

        redacted_text, applied, phantom = Redactor.redact(
            chunk_text, ner_result.entities
        )

        if phantom:
            print(
                f"[MedicalProcessor] {len(phantom)} phantom entities skipped "
                f"(LLM reported but not found in text)"
            )

        content_key = "cleaned_markdown" if is_advanced else "cleaned_text"
        return {
            content_key: redacted_text,
            "entities_removed": [ent.model_dump() for ent in applied],
            "document_language": ner_result.document_language,
        }

    async def _extract_entities(
        self, chunk_text: str, is_advanced: bool
    ) -> NerExtractionResult:
        """Send text to LLM and parse the NER-only JSON response."""
        template_name = "advanced_anonymizer" if is_advanced else "simple_anonymizer"
        prompt_template = self.prompt_manager.get_prompt(template_name)
        full_user_prompt = prompt_template.replace(_TRANSCRIPT_PLACEHOLDER, chunk_text)

        system_msg = _SYSTEM_MSG_NER

        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                raw_output = self.llama.generate_json(system_msg, full_user_prompt)
                raw_json = self._extract_json(raw_output)
                return self._parse_ner_result(raw_json)
            except ValueError as e:
                last_error = e
                print(
                    f"[MedicalProcessor] NER parse failed (attempt {attempt + 1}/{_MAX_RETRIES}): {e}"
                )
                
                system_msg = (
                    "You are a precise NER engine for medical anonymization. "
                    "Return ONLY a single, valid, compact JSON object with "
                    '"entities" (array of {text, tag}) and "document_language" (string). '
                    "Do NOT use line breaks inside string values — use \\\\n instead."
                )

        raise ValueError(
            f"Failed to get valid NER JSON after {_MAX_RETRIES} attempts. "
            f"Last error: {last_error}"
        )

    @staticmethod
    def _parse_ner_result(raw_json: dict) -> NerExtractionResult:
        """
        Validate and parse raw LLM JSON into a NerExtractionResult.
        Filters out invalid / abstract entities.
        """
        raw_entities = raw_json.get("entities", [])
        doc_lang = raw_json.get("document_language", "unknown")

        valid_entities: list[NerEntity] = []
        for item in raw_entities:
            if not isinstance(item, dict):
                continue

            text = item.get("text", "").strip()
            tag = item.get("tag", "").strip().upper()

            if not text or not tag:
                continue

            # Filter out abstract labels that the LLM sometimes returns
            _ABSTRACT_BLOCKLIST = {
                "patientenname", "patient name", "nazwa pacjenta",
                "adresse", "address", "adres",
                "pesel", "svn", "ssn",
                "[name]", "[pesel]", "[address]", "[adresse]",
                "[surname]", "[id_number]",
            }
            if text.lower() in _ABSTRACT_BLOCKLIST:
                print(f"[NER Filter] Rejected abstract entity: '{text}'")
                continue

            # Filter out entities that look like tag placeholders [TAG]
            if re.match(r"^\[.+\]$", text):
                print(f"[NER Filter] Rejected tag-like entity: '{text}'")
                continue

            # Filter out very short entities that are likely noise
            # (single characters, unless they look like IDs)
            if len(text) <= 1 and tag not in ("COUNTRY_CODE",):
                print(f"[NER Filter] Rejected too-short entity: '{text}'")
                continue

            valid_entities.append(NerEntity(text=text, tag=tag))

        return NerExtractionResult(
            entities=valid_entities,
            document_language=doc_lang,
        )

    def _extract_json(self, text: str) -> dict:
        text = text.strip()

        # First try: direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find the JSON object boundaries
        start = text.find("{")
        if start == -1:
            raise ValueError(f"No JSON object found in LLM response: {text[:200]}...")

        json_text = text[start:]

        # Try raw_decode first (handles trailing text after valid JSON)
        try:
            obj, _ = json.JSONDecoder().raw_decode(json_text)
            return obj
        except json.JSONDecodeError:
            pass

        # Attempt repairs on the broken JSON
        json_text = self._repair_json(json_text)

        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass

        # Last resort: try raw_decode on repaired text
        try:
            obj, _ = json.JSONDecoder().raw_decode(json_text)
            return obj
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Cannot parse JSON even after repair. Error: {e}. "
                f"Raw output (first 500 chars): {text[:500]}"
            ) from e

    @staticmethod
    def _repair_json(text: str) -> str:
        """Attempt to fix common LLM JSON issues."""
        # 1. Fix unescaped newlines/tabs inside string values
        #    Walk through the text and escape newlines that appear inside strings
        result = []
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == '\\' and in_string:
                result.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == '\n':
                    result.append('\\n')
                    continue
                if ch == '\r':
                    result.append('\\r')
                    continue
                if ch == '\t':
                    result.append('\\t')
                    continue
            result.append(ch)
        text = ''.join(result)

        # 2. Remove trailing commas before } or ]
        text = re.sub(r',\s*([}\]])', r'\1', text)

        # 3. Try to close truncated JSON (missing closing braces/brackets)
        open_braces = text.count('{') - text.count('}')
        open_brackets = text.count('[') - text.count(']')

        if open_braces > 0 or open_brackets > 0:
            # If we're inside a string (odd number of unescaped quotes), close it
            unescaped_quotes = len(re.findall(r'(?<!\\)"', text))
            if unescaped_quotes % 2 != 0:
                text += '"'

            text += ']' * max(0, open_brackets)
            text += '}' * max(0, open_braces)

        return text
