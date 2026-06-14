from __future__ import annotations

from typing import Any, Iterable, Literal, Mapping

from .models import Candidate, PatientRequest


RawValueStrategy = Literal["inverse", "negative", "cosine_distance"]


def raw_value_to_score(
    raw_value: float,
    strategy: RawValueStrategy = "inverse",
) -> float:

    if strategy == "inverse":
        return 1.0 / (1.0 + max(raw_value, 0.0))

    if strategy == "negative":
        return -raw_value

    if strategy == "cosine_distance":
        # LanceDB zwraca cosine distance, więc naturalny score to 1 - distance.
        return 1.0 - raw_value

    raise ValueError(f"Unsupported raw value strategy: {strategy}")


def patient_from_lancedb_rows(
    patient_id: str,
    rows: Iterable[Mapping[str, Any]],
    doctor_id_key: str = "doctor_id",
    raw_value_key: str = "_distance",
    score_key: str | None = None,
    raw_value_strategy: RawValueStrategy = "inverse",
    raw_value_type: str = "distance",
) -> PatientRequest:
    candidates: list[Candidate] = []

    for row in rows:
        if doctor_id_key not in row:
            raise KeyError(f"Missing key '{doctor_id_key}' in search result row")

        doctor_id = str(row[doctor_id_key])

        raw_value = None
        if raw_value_key in row and row[raw_value_key] is not None:
            raw_value = float(row[raw_value_key])

        if score_key is not None and score_key in row and row[score_key] is not None:
            score = float(row[score_key])
        elif raw_value is not None:
            score = raw_value_to_score(raw_value, strategy=raw_value_strategy)
        else:
            raise ValueError(
                f"Row for doctor_id='{doctor_id}' has neither '{score_key}' nor '{raw_value_key}'"
            )

        metadata = {
            key: value
            for key, value in row.items()
            if key not in {doctor_id_key, raw_value_key, score_key}
        }

        candidates.append(
            Candidate(
                doctor_id=doctor_id,
                score=score,
                raw_value=raw_value,
                raw_value_type=raw_value_type,
                metadata=metadata,
            )
        )

    return PatientRequest(patient_id=patient_id, candidates=candidates)