from langdetect import detect_langs

class LanguageService:
    @staticmethod
    def detect(text: str) -> tuple[bool, str]:
        try:
            predictions = detect_langs(text[:2000]) # [lang:confidence score]
            top_lang = predictions[0]

            if top_lang.lang not in ['pl', 'de', 'en']:
                return False, f"Unsupported: {top_lang.lang}"
            return True, top_lang.lang
        except:
            return False, "Unknown"