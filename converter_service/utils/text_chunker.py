import re


class TextProcessor:
    @staticmethod
    def split_into_chunks(text: str, max_chars: int = 4000) -> list[str]:
        if len(text) <= max_chars:
            return [text]

        sections = re.split(r"(?=\n#+)", text)
        chunks: list[str] = []
        current_chunk = ""

        for section in sections:
            if len(current_chunk) + len(section) <= max_chars:
                current_chunk += section
                continue

            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            if len(section) > max_chars:
                parts = [
                    section[i : i + max_chars]
                    for i in range(0, len(section), max_chars)
                ]
                chunks.extend(parts[:-1])
                current_chunk = parts[-1]
            else:
                current_chunk = section

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
