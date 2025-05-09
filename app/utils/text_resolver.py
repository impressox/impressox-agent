import re

try:
    from rapidfuzz import process, fuzz
    USE_RAPIDFUZZ = True
except ImportError:
    import difflib
    USE_RAPIDFUZZ = False

try:
    import unidecode
except ImportError:
    raise ImportError("Bạn cần cài đặt thư viện 'unidecode' (pip install unidecode)")

class TextResolver:
    def __init__(self, candidates: list[str], threshold: int = 70, alias_dict: dict[str, str] = None):
        self.candidates = candidates
        self.threshold = threshold
        self.alias_dict = alias_dict or {}
        self.normalized_candidates = [self._normalize(c) for c in candidates]

    def _normalize(self, text: str) -> str:
        text = unidecode.unidecode(text.lower())
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def match(self, input_text: str) -> str:
        norm_input = self._normalize(input_text)
        # Step 1: Check alias dictionary first
        if norm_input in self.alias_dict:
            return self.alias_dict[norm_input]

        # Step 2: Fallback to fuzzy
        if USE_RAPIDFUZZ:
            result = process.extractOne(norm_input, self.normalized_candidates, scorer=fuzz.token_sort_ratio)
            if result and result[1] >= self.threshold:
                index = self.normalized_candidates.index(result[0])
                return self.candidates[index]
        else:
            matches = difflib.get_close_matches(norm_input, self.normalized_candidates, n=1, cutoff=self.threshold / 100)
            if matches:
                index = self.normalized_candidates.index(matches[0])
                return self.candidates[index]

        return input_text

