import re
from typing import Optional, List
from ..domain.schemas import QuoteVerificationResult, DocumentSection

class QuoteVerifier:
    """
    Deterministic quote verifier ensuring zero hallucination.
    Verifies that any candidate claim citing a quote can be located verbatim
    in the raw candidate source text, calculating exact character offsets and section provenance.
    """

    @classmethod
    def verify_quote(
        cls,
        raw_source_text: str,
        quote: Optional[str],
        sections: Optional[List[DocumentSection]] = None
    ) -> QuoteVerificationResult:
        """
        Verify that the given quote exists in raw_source_text.
        Returns QuoteVerificationResult with exact offsets or hallucination warning.
        """
        if not quote or not quote.strip():
            return QuoteVerificationResult(
                valid=False,
                warning="EMPTY_QUOTE_PROVIDED"
            )

        clean_quote = quote.strip()

        # 1. Exact Substring Search
        exact_index = raw_source_text.find(clean_quote)
        if exact_index != -1:
            start_offset = exact_index
            end_offset = start_offset + len(clean_quote)
            matched_text = raw_source_text[start_offset:end_offset]
            page_num, sec_name = cls._locate_section(start_offset, sections)

            return QuoteVerificationResult(
                valid=True,
                start_offset=start_offset,
                end_offset=end_offset,
                page_number=page_num,
                section_name=sec_name,
                matched_text=matched_text,
                warning=None
            )

        # 2. Normalized Whitespace Substring Search
        # Build regex that allows any sequence of whitespace in source text where quote has whitespace
        quote_words = [re.escape(word) for word in clean_quote.split()]
        if len(quote_words) > 0:
            flexible_pattern = r"\s+".join(quote_words)
            match = re.search(flexible_pattern, raw_source_text, flags=re.IGNORECASE)
            if match:
                start_offset = match.start()
                end_offset = match.end()
                matched_text = raw_source_text[start_offset:end_offset]
                page_num, sec_name = cls._locate_section(start_offset, sections)

                return QuoteVerificationResult(
                    valid=True,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    page_number=page_num,
                    section_name=sec_name,
                    matched_text=matched_text,
                    warning="MATCHED_WITH_WHITESPACE_NORMALIZATION"
                )

        # 3. Punctuation-Normalized Flexible Search (curly quotes, typographic dashes)
        def _norm_punct(s: str) -> str:
            return (s.replace('“', '"').replace('”', '"')
                     .replace('‘', "'").replace('’', "'")
                     .replace('—', '-').replace('–', '-'))

        norm_quote = _norm_punct(clean_quote)
        norm_source = _norm_punct(raw_source_text)
        quote_words_norm = [re.escape(word) for word in norm_quote.split()]
        if len(quote_words_norm) > 0:
            pattern_norm = r"\s+".join(quote_words_norm)
            match_norm = re.search(pattern_norm, norm_source, flags=re.IGNORECASE)
            if match_norm:
                start_offset = match_norm.start()
                end_offset = match_norm.end()
                matched_text = raw_source_text[start_offset:end_offset]
                page_num, sec_name = cls._locate_section(start_offset, sections)

                return QuoteVerificationResult(
                    valid=True,
                    start_offset=start_offset,
                    end_offset=end_offset,
                    page_number=page_num,
                    section_name=sec_name,
                    matched_text=matched_text,
                    warning="MATCHED_WITH_PUNCTUATION_NORMALIZATION"
                )

        # 4. Not Found -> Hallucination Prevented
        return QuoteVerificationResult(
            valid=False,
            warning="UNVERIFIED_HALLUCINATION_PREVENTED"
        )

    @staticmethod
    def _locate_section(offset: int, sections: Optional[List[DocumentSection]]) -> tuple[Optional[int], Optional[str]]:
        """Map character offset to section and page number if sections provided."""
        if not sections:
            return 1, "Full Document"

        for sec in sections:
            if sec.start_offset <= offset <= sec.end_offset:
                return sec.page_number, sec.section_name

        # Fallback to closest preceding section
        for sec in reversed(sections):
            if offset >= sec.start_offset:
                return sec.page_number, sec.section_name

        return 1, sections[0].section_name if sections else "Document"
