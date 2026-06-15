from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptManager:
    @staticmethod
    def get_prompt(template_name: str) -> str:
        file_path = _PROMPTS_DIR / f"{template_name}.md"

        if not file_path.exists():
            raise FileNotFoundError(f"Not found template: {file_path}")

        return file_path.read_text(encoding="utf-8")
