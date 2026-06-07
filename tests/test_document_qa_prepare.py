from __future__ import annotations

import pytest

from evals.document_qa.prepare_squad_subset import squad_example_to_row


def test_squad_example_to_row_maps_required_fields() -> None:
    example = {
        "id": "5733be284776f41900661182",
        "title": "University_of_Notre_Dame",
        "context": "Architecturally, the school has a Catholic character.",
        "question": "What kind of character does the school have?",
        "answers": {
            "text": ["Catholic"],
            "answer_start": [38],
        },
    }

    row = squad_example_to_row(example, index=3)

    assert row == {
        "case_id": "squad_validation_0003",
        "source": "squad",
        "document_id": "5733be284776f41900661182",
        "document_text": "Architecturally, the school has a Catholic character.",
        "question": "What kind of character does the school have?",
        "expected_answer": "Catholic",
        "supporting_evidence": "Architecturally, the school has a Catholic character.",
        "answer_anchor": "Catholic",
        "category": "standard_document_qa",
    }


def test_squad_example_to_row_rejects_missing_answers() -> None:
    example = {
        "id": "missing",
        "context": "A context exists.",
        "question": "What exists?",
        "answers": {"text": [], "answer_start": []},
    }

    with pytest.raises(ValueError, match="missing context, question, or answers"):
        squad_example_to_row(example, index=0)
