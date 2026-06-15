from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AssignmentConfig:
    # Jak mocno karzę za zapełnianie kolejnych slotów lekarza (physician).
    load_penalty_weight: float = 0.05

    # Jak szybko kara rośnie.
    # 1.0 -> liniowo
    # 2.0 -> kwadratowo
    load_penalty_exponent: float = 1.0

    
    unassigned_score: float = 0.0

    # próg minimalnego wyniku kandydata, poniżej którego pacjent nie zostanie przypisany do żadnego lekarza (physician)
    min_candidate_score: float = float("-inf")


def compute_slot_penalty(
    absolute_slot_index: int,
    physician_capacity: int,
    config: AssignmentConfig,
) -> float:
    if physician_capacity <= 0:
        raise ValueError("physician_capacity must be > 0")

    utilization = absolute_slot_index / physician_capacity
    return config.load_penalty_weight * (utilization ** config.load_penalty_exponent)