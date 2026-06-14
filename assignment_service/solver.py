from __future__ import annotations

from collections import Counter
from dataclasses import replace
from math import isfinite
from typing import Literal

import numpy as np
from scipy.optimize import linear_sum_assignment

from .config import AssignmentConfig, compute_slot_penalty
from .models import (
    AssignmentDecision,
    AssignmentSummary,
    Candidate,
    Doctor,
    DoctorSlot,
    PatientRequest,
)

BIG_M = 1e9
AssignmentMode = Literal["incremental", "rebalance"]


class GlobalCapacityAssignmentSolver:
    def __init__(self, config: AssignmentConfig | None = None) -> None:
        self.config = config or AssignmentConfig()

    def solve_incremental(
        self,
        new_patients: list[PatientRequest],
        doctors: list[Doctor],
    ) -> AssignmentSummary:

        return self._solve_internal(
            patients=new_patients,
            doctors=doctors,
            mode="incremental",
        )

    def solve_rebalance(
        self,
        patients_to_reassign: list[PatientRequest],
        doctors: list[Doctor],
    ) -> AssignmentSummary:

        rebalance_doctors = [
            replace(doctor, current_load=0)
            for doctor in doctors
        ]

        return self._solve_internal(
            patients=patients_to_reassign,
            doctors=rebalance_doctors,
            mode="rebalance",
        )

    def _solve_internal(
        self,
        patients: list[PatientRequest],
        doctors: list[Doctor],
        mode: AssignmentMode,
    ) -> AssignmentSummary:
        doctor_map = self._build_doctor_map(doctors)
        self._validate_patients(patients)

        if not patients:
            return AssignmentSummary(
                mode=mode,
                decisions=[],
                doctor_loads={doctor.doctor_id: doctor.current_load for doctor in doctors},
                total_base_score=0.0,
                total_penalty=0.0,
                total_final_score=0.0,
                assigned_count=0,
                unassigned_count=0,
            )

        slots = self._build_slots(doctors)

        candidate_maps: list[dict[str, Candidate]] = []
        rank_maps: list[dict[str, int]] = []

        for patient in patients:
            candidate_map, rank_map = self._prepare_candidates(patient, doctor_map)
            candidate_maps.append(candidate_map)
            rank_maps.append(rank_map)

        cost_matrix = self._build_cost_matrix(
            patients=patients,
            slots=slots,
            candidate_maps=candidate_maps,
        )

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        row_to_col = {row: col for row, col in zip(row_ind, col_ind)}

        decisions: list[AssignmentDecision] = []
        assigned_per_doctor: Counter[str] = Counter()

        total_base_score = 0.0
        total_penalty = 0.0
        total_final_score = 0.0
        assigned_count = 0

        real_slot_count = len(slots)

        for row_idx, patient in enumerate(patients):
            col_idx = row_to_col[row_idx]

            if col_idx < real_slot_count and cost_matrix[row_idx, col_idx] < BIG_M / 2:
                slot = slots[col_idx]
                candidate = candidate_maps[row_idx][slot.doctor_id]
                candidate_rank = rank_maps[row_idx][slot.doctor_id]

                base_score = candidate.score
                slot_penalty = slot.penalty
                final_score = base_score - slot_penalty

                decisions.append(
                    AssignmentDecision(
                        patient_id=patient.patient_id,
                        assigned_doctor_id=slot.doctor_id,
                        assigned_slot_index=slot.slot_index,
                        candidate_rank=candidate_rank,
                        base_score=base_score,
                        slot_penalty=slot_penalty,
                        final_score=final_score,
                        mode=mode,
                        reason="assigned",
                    )
                )

                assigned_per_doctor[slot.doctor_id] += 1
                total_base_score += base_score
                total_penalty += slot_penalty
                total_final_score += final_score
                assigned_count += 1

            else:
                decisions.append(
                    AssignmentDecision(
                        patient_id=patient.patient_id,
                        assigned_doctor_id=None,
                        assigned_slot_index=None,
                        candidate_rank=None,
                        base_score=0.0,
                        slot_penalty=0.0,
                        final_score=self.config.unassigned_score,
                        mode=mode,
                        reason="left_unassigned",
                    )
                )
                total_final_score += self.config.unassigned_score

        doctor_loads = {
            doctor.doctor_id: doctor.current_load + assigned_per_doctor[doctor.doctor_id]
            for doctor in doctors
        }

        return AssignmentSummary(
            mode=mode,
            decisions=decisions,
            doctor_loads=doctor_loads,
            total_base_score=total_base_score,
            total_penalty=total_penalty,
            total_final_score=total_final_score,
            assigned_count=assigned_count,
            unassigned_count=len(patients) - assigned_count,
        )

    def _build_doctor_map(self, doctors: list[Doctor]) -> dict[str, Doctor]:
        doctor_map: dict[str, Doctor] = {}

        for doctor in doctors:
            if doctor.doctor_id in doctor_map:
                raise ValueError(f"Duplicate doctor_id detected: {doctor.doctor_id}")

            if doctor.capacity < 0:
                raise ValueError(f"Doctor '{doctor.doctor_id}' has negative capacity")

            if doctor.current_load < 0:
                raise ValueError(f"Doctor '{doctor.doctor_id}' has negative current_load")

            if doctor.current_load > doctor.capacity:
                raise ValueError(
                    f"Doctor '{doctor.doctor_id}' has current_load > capacity"
                )

            doctor_map[doctor.doctor_id] = doctor

        return doctor_map

    def _validate_patients(self, patients: list[PatientRequest]) -> None:
        seen_patient_ids: set[str] = set()

        for patient in patients:
            if patient.patient_id in seen_patient_ids:
                raise ValueError(f"Duplicate patient_id detected: {patient.patient_id}")
            seen_patient_ids.add(patient.patient_id)

            for candidate in patient.candidates:
                if not isfinite(candidate.score):
                    raise ValueError(
                        f"Patient '{patient.patient_id}' has non-finite candidate score"
                    )

    def _build_slots(self, doctors: list[Doctor]) -> list[DoctorSlot]:
        slots: list[DoctorSlot] = []

        for doctor in doctors:
            for relative_idx in range(1, doctor.remaining_capacity + 1):
                absolute_slot_index = doctor.current_load + relative_idx
                penalty = compute_slot_penalty(
                    absolute_slot_index=absolute_slot_index,
                    doctor_capacity=doctor.capacity,
                    config=self.config,
                )

                slots.append(
                    DoctorSlot(
                        doctor_id=doctor.doctor_id,
                        slot_index=absolute_slot_index,
                        penalty=penalty,
                    )
                )

        return slots

    def _prepare_candidates(
        self,
        patient: PatientRequest,
        doctor_map: dict[str, Doctor],
    ) -> tuple[dict[str, Candidate], dict[str, int]]:
        best_by_doctor: dict[str, Candidate] = {}

        for candidate in patient.candidates:
            doctor = doctor_map.get(candidate.doctor_id)
            if doctor is None:
                continue

            if doctor.remaining_capacity <= 0:
                continue

            if candidate.score < self.config.min_candidate_score:
                continue

            existing = best_by_doctor.get(candidate.doctor_id)
            if existing is None or candidate.score > existing.score:
                best_by_doctor[candidate.doctor_id] = candidate

        ranked = sorted(
            best_by_doctor.values(),
            key=lambda item: item.score,
            reverse=True,
        )

        candidate_map = {candidate.doctor_id: candidate for candidate in ranked}
        rank_map = {
            candidate.doctor_id: rank
            for rank, candidate in enumerate(ranked, start=1)
        }

        return candidate_map, rank_map

    def _build_cost_matrix(
        self,
        patients: list[PatientRequest],
        slots: list[DoctorSlot],
        candidate_maps: list[dict[str, Candidate]],
    ) -> np.ndarray:
        patient_count = len(patients)
        real_slot_count = len(slots)

        total_columns = real_slot_count + patient_count
        matrix = np.full((patient_count, total_columns), BIG_M, dtype=float)

        for row_idx, _patient in enumerate(patients):
            candidate_map = candidate_maps[row_idx]

            for col_idx, slot in enumerate(slots):
                candidate = candidate_map.get(slot.doctor_id)
                if candidate is None:
                    continue

                final_score = candidate.score - slot.penalty
                matrix[row_idx, col_idx] = -final_score

            matrix[row_idx, real_slot_count:] = -self.config.unassigned_score

        return matrix