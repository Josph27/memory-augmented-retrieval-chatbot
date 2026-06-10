from __future__ import annotations

from evals.document_qa.diagnose_dataset import diagnose_rows


def test_diagnose_rows_reports_duplicates_and_anchor_position() -> None:
    rows = [
        {
            "document_text": "Ada created the Meridian protocol.",
            "question": "Who created Meridian?",
            "answer_anchor": "Ada",
        },
        {
            "document_text": "Ada created the Meridian protocol.",
            "question": "Who created Meridian?",
            "answer_anchor": "Ada",
        },
        {
            "document_text": ("prefix " * 100) + "Luminara",
            "question": "What is the protocol?",
            "answer_anchor": "Luminara",
        },
    ]

    diagnostics = diagnose_rows(rows, chunk_size=40, chunk_overlap=0)

    assert diagnostics.cases == 3
    assert diagnostics.unique_documents == 2
    assert diagnostics.duplicate_document_texts == 2
    assert diagnostics.duplicate_questions == 2
    assert diagnostics.estimated_chunks >= 2
    assert diagnostics.answer_anchor_length_distribution["1_word"] == 3
    assert round(diagnostics.answer_in_first_500_pct, 1) == 66.7
