from __future__ import annotations

from .config import AssignmentConfig
from .models import AssignmentSummary, Doctor, PatientRequest
from .solver import GlobalCapacityAssignmentSolver


class AssignmentService:
    def __init__(self, config: AssignmentConfig | None = None) -> None:
        self.solver = GlobalCapacityAssignmentSolver(config=config)

    def assign_new_patients(
        self,
        new_patients: list[PatientRequest],
        doctors: list[Doctor],
    ) -> AssignmentSummary:
    
        return self.solver.solve_incremental(
            new_patients=new_patients,
            doctors=doctors,
        )

    def rebalance_batch(
        self,
        patients_to_reassign: list[PatientRequest],
        doctors: list[Doctor],
    ) -> AssignmentSummary:

        return self.solver.solve_rebalance(
            patients_to_reassign=patients_to_reassign,
            doctors=doctors,
        )