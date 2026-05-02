from __future__ import annotations

from typing import Any, Iterable, Literal, Mapping

from .models import Candidate, PatientRequest


ScoreTransform = Literal[
    "inverse_distance",
    "negative_distance",
    "cosine_similarity",
    "identity_score",
]


def raw_value_to_score(value: float, transform: ScoreTransform = "inverse_distance") -> float:
    """
    Zamieniam surowy wynik z retrievalu na score, gdzie większy = lepszy.
    """

    if transform == "inverse_distance":
        # Dla klasycznych dystansów >= 0: mniejszy dystans -> większy score
        return 1.0 / (1.0 + max(value, 0.0))

    if transform == "negative_distance":
        # Zachowuję porządek: mniejszy dystans -> większy score
        return -value

    if transform == "cosine_similarity":
        # Zakładam, że baza już zwraca similarity, więc większy = lepszy
        return value

    if transform == "identity_score":
        # Zakładam, że wejście to już gotowy score
        return value

    raise ValueError(f"Unsupported score transform: {transform}")


def patient_from_lancedb_rows(
    patient_id: str,
    rows: Iterable[Mapping[str, Any]],
    doctor_id_key: str = "doctor_id",
    value_key: str = "_distance",
    score_key: str | None = None,
    transform: ScoreTransform = "inverse_distance",
) -> PatientRequest:
    candidates: list[Candidate] = []

    for row in rows:
        if doctor_id_key not in row:
            raise KeyError(f"Missing key '{doctor_id_key}' in search result row")

        doctor_id = str(row[doctor_id_key])

        raw_value = None
        if value_key in row and row[value_key] is not None:
            raw_value = float(row[value_key])

        if score_key is not None and score_key in row and row[score_key] is not None:
            score = float(row[score_key])
        elif raw_value is not None:
            score = raw_value_to_score(raw_value, transform=transform)
        else:
            raise ValueError(
                f"Row for doctor_id='{doctor_id}' has neither '{score_key}' nor '{value_key}'"
            )

        metadata = {
            key: value
            for key, value in row.items()
            if key not in {doctor_id_key, value_key, score_key}
        }

        candidates.append(
            Candidate(
                doctor_id=doctor_id,
                score=score,
                distance=raw_value if "distance" in value_key.lower() else None,
                metadata=metadata,
            )
        )

    return PatientRequest(patient_id=patient_id, candidates=candidates)