import os
import fitz

class DocumentClassifier:
    MAX_PAGES_FOR_SIMPLE = 15
    MIN_CHAR_COUNT_FOR_NON_SCAN = 100
    MIN_SIZE_MB_FOR_SCAN_DETECTION = 0.5
    TABLE_INDICATOR_SPACES = 50
    TABLE_INDICATOR_SPECIAL_CHARS = 5

    @classmethod
    def is_complex(cls, file_path: str) -> bool:
        extension = os.path.splitext(file_path)[1].lower()
        if extension == '.docx':
            return False
        if extension == '.pdf':
            return cls._analyze_pdf(file_path)
        return True
    
    @classmethod
    def _analyze_pdf(cls, file_path: str) -> bool:
        try:
            with fitz.open(file_path) as doc:
                total_pages = len(doc)
                if total_pages > cls.MAX_PAGES_FOR_SIMPLE: return True
                
                text_samples = sorted(list({0, total_pages//2, total_pages-1}))
                full_text_sample = ""
                for idx in text_samples:
                    if idx < total_pages:
                        full_text_sample += doc[idx].get_text()
                
                # check if it is scan (small amount of text + huge size of file)
                file_size_mb = os.path.getsize(file_path)/(1024*1024)
                is_likely_scan = ( len(full_text_sample.strip()) < cls.MIN_CHAR_COUNT_FOR_NON_SCAN and file_size_mb > cls.MIN_SIZE_MB_FOR_SCAN_DETECTION)
                
                if is_likely_scan: return True

                # advanced conditions for tables and layout
                special_chars_count = (
                    full_text_sample.count('|') + 
                    full_text_sample.count('\t') + 
                    full_text_sample.count(';')
                )

                has_complex_layout = (
                    full_text_sample.count('  ') > cls.TABLE_INDICATOR_SPACES or 
                    special_chars_count > cls.TABLE_INDICATOR_SPECIAL_CHARS
                )
                
                return has_complex_layout
        except Exception:
            return True # better to use docling