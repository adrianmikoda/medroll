from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Doctor:
    doctor_id: str
    capacity: int
    current_load: int = 0
    name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def remaining_capacity(self) -> int:
        return max(0, self.capacity - self.current_load)

@dataclass(slots=True)
class Candidate:
    doctor_id: str
    score: float
    raw_value: float | None = None
    raw_value_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class PatientRequest:
    patient_id: str
    candidates: list[Candidate]
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class DoctorSlot:
    doctor_id: str
    slot_index: int
    penalty: float

@dataclass(slots=True)
class AssignmentDecision:
    patient_id: str
    assigned_doctor_id: str | None
    assigned_slot_index: int | None
    candidate_rank: int | None
    base_score: float
    slot_penalty: float
    final_score: float
    mode: str
    reason: str

@dataclass(slots=True)
class AssignmentSummary:
    mode: str
    decisions: list[AssignmentDecision]
    doctor_loads: dict[str, int]
    total_base_score: float
    total_penalty: float
    total_final_score: float
    assigned_count: int
    unassigned_count: int
