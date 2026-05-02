from __future__ import annotations

from pprint import pprint

from assignment_service import (
    AssignmentConfig,
    AssignmentService,
    Candidate,
    Doctor,
    PatientRequest,
)


def print_summary(title: str, summary) -> None:
    print(f"\n===== {title} =====")
    print(f"mode = {summary.mode}")

    print("\nDECISIONS:")
    for decision in summary.decisions:
        pprint(decision)

    print("\nDOCTOR LOADS:")
    pprint(summary.doctor_loads)

    print("\nSUMMARY:")
    print(f"assigned_count    = {summary.assigned_count}")
    print(f"unassigned_count  = {summary.unassigned_count}")
    print(f"total_base_score  = {summary.total_base_score:.4f}")
    print(f"total_penalty     = {summary.total_penalty:.4f}")
    print(f"total_final_score = {summary.total_final_score:.4f}")


def main() -> None:
    doctors = [
        Doctor(doctor_id="doc_1", name="Dr A", capacity=3, current_load=2),
        Doctor(doctor_id="doc_2", name="Dr B", capacity=3, current_load=1),
        Doctor(doctor_id="doc_3", name="Dr C", capacity=2, current_load=0),
    ]

    new_patients = [
        PatientRequest(
            patient_id="pat_new_1",
            candidates=[
                Candidate(doctor_id="doc_1", score=0.97),
                Candidate(doctor_id="doc_2", score=0.94),
                Candidate(doctor_id="doc_3", score=0.91),
            ],
        ),
        PatientRequest(
            patient_id="pat_new_2",
            candidates=[
                Candidate(doctor_id="doc_1", score=0.96),
                Candidate(doctor_id="doc_2", score=0.95),
                Candidate(doctor_id="doc_3", score=0.90),
            ],
        ),
        PatientRequest(
            patient_id="pat_new_3",
            candidates=[
                Candidate(doctor_id="doc_1", score=0.95),
                Candidate(doctor_id="doc_2", score=0.93),
                Candidate(doctor_id="doc_3", score=0.92),
            ],
        ),
    ]

    rebalance_patients = [
        PatientRequest(
            patient_id="pat_re_1",
            candidates=[
                Candidate(doctor_id="doc_1", score=0.97),
                Candidate(doctor_id="doc_2", score=0.94),
                Candidate(doctor_id="doc_3", score=0.91),
            ],
        ),
        PatientRequest(
            patient_id="pat_re_2",
            candidates=[
                Candidate(doctor_id="doc_1", score=0.96),
                Candidate(doctor_id="doc_2", score=0.95),
                Candidate(doctor_id="doc_3", score=0.90),
            ],
        ),
        PatientRequest(
            patient_id="pat_re_3",
            candidates=[
                Candidate(doctor_id="doc_1", score=0.95),
                Candidate(doctor_id="doc_2", score=0.93),
                Candidate(doctor_id="doc_3", score=0.92),
            ],
        ),
    ]

    config = AssignmentConfig(
        load_penalty_weight=0.25,
        load_penalty_exponent=2.0,
        unassigned_score=0.0,
        min_candidate_score=0.0,
    )

    service = AssignmentService(config=config)

    incremental_summary = service.assign_new_patients(
        new_patients=new_patients,
        doctors=doctors,
    )

    rebalance_summary = service.rebalance_batch(
        patients_to_reassign=rebalance_patients,
        doctors=doctors,
    )

    print_summary("INCREMENTAL / FREEZE EXISTING", incremental_summary)
    print_summary("REBALANCE BATCH", rebalance_summary)


if __name__ == "__main__":
    main()