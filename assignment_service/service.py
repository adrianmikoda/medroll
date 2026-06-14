from __future__ import annotations

from .config import AssignmentConfig
from .models import AssignmentSummary, Physician, PatientRequest
from .solver import GlobalCapacityAssignmentSolver


class AssignmentService:
    def __init__(self, config: AssignmentConfig | None = None) -> None:
        self.solver = GlobalCapacityAssignmentSolver(config=config)

    def assign_new_patients(
        self,
        new_patients: list[PatientRequest],
        physicians: list[Physician],
    ) -> AssignmentSummary:
    
        return self.solver.solve_incremental(
            new_patients=new_patients,
            physicians=physicians,
        )

    def rebalance_batch(
        self,
        patients_to_reassign: list[PatientRequest],
        physicians: list[Physician],
    ) -> AssignmentSummary:

        return self.solver.solve_rebalance(
            patients_to_reassign=patients_to_reassign,
            physicians=physicians,
        )