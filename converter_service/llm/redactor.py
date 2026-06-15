"""
Deterministic redaction engine.

Takes the original text and a list of NER entities, then performs
exact string replacement to produce anonymized output.
"""

import re
from ..models import NerEntity


class Redactor:
    @staticmethod
    def redact(
        text: str,
        entities: list[NerEntity],
    ) -> tuple[str, list[NerEntity], list[NerEntity]]:
        """
        Replace every detected entity in *text* with its ``[TAG]`` placeholder.

        Parameters:

        text : str
            The original, unmodified text extracted from the document.
        entities : list[NerEntity]
            Entities detected by the LLM.

        Returns:
        
        tuple[str, list[NerEntity], list[NerEntity]]
            - redacted text
            - list of entities that were successfully applied
            - list of entities that were NOT found in the text (phantom)
        """
        if not entities:
            return text, [], []

        # De-duplicate entities
        seen: set[tuple[str, str]] = set()
        unique_entities: list[NerEntity] = []
        for ent in entities:
            key = (ent.text, ent.tag)
            if key not in seen:
                seen.add(key)
                unique_entities.append(ent)

        unique_entities.sort(key=lambda e: len(e.text), reverse=True)

        applied: list[NerEntity] = []
        phantom: list[NerEntity] = []

        for entity in unique_entities:
            tag_placeholder = f"[{entity.tag}]"

            pattern = re.escape(entity.text)

            new_text, count = re.subn(pattern, tag_placeholder, text)

            if count > 0:
                text = new_text
                applied.append(entity)
            else:
                # Try a more lenient match: collapse whitespace differences
                # (PDF extraction often introduces extra spaces / line breaks)
                flexible_pattern = r"\s+".join(
                    re.escape(word) for word in entity.text.split()
                )
                new_text, count = re.subn(flexible_pattern, tag_placeholder, text)
                if count > 0:
                    text = new_text
                    applied.append(entity)
                else:
                    phantom.append(entity)

        if phantom:
            print(
                f"[Redactor] WARNING: {len(phantom)} entity(ies) not found in text: "
                f"{[e.text for e in phantom]}"
            )

        return text, applied, phantom
