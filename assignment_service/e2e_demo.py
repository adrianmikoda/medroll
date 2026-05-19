from __future__ import annotations

from pprint import pprint

from assignment_service import (
    AssignmentConfig,
    AssignmentService,
    Doctor,
    patient_from_lancedb_rows,
)
from transformer_service.database import Database


def print_retrieval(patient_id: str, rows: list[dict]) -> None:
    print(f"\nRetrieval for {patient_id}:")
    for idx, row in enumerate(rows, start=1):
        distance = row.get("_distance", None)
        print(
            f"[{idx}] doctor_id={row.get('doctor_id')} | "
            f"filename={row.get('filename')} | "
            f"distance={distance}"
        )


def main() -> None:
    doctor_files = [
        {
            "doctor_id": "doc_cardio",
            "filename": "cv_kardiochirurg.pdf",
            "capacity": 2,
            "current_load": 0,
            "name": "Kardiochirurg",
        },
        {
            "doctor_id": "doc_ortho",
            "filename": "cv_ortopeda.pdf",
            "capacity": 2,
            "current_load": 0,
            "name": "Ortopeda",
        },
        {
            "doctor_id": "doc_psych",
            "filename": "cv_psychiatra.pdf",
            "capacity": 2,
            "current_load": 0,
            "name": "Psychiatra",
        },
    ]

    patient_files = [
        {"patient_id": "pat_1", "filename": "karta_1.pdf"},
        {"patient_id": "pat_2", "filename": "karta_2.pdf"},
        {"patient_id": "pat_3", "filename": "karta_3.pdf"},
    ]

    database = Database(
        db_path="./lancedb",
        table_name="doctors",
        model_name="nvidia/llama-embed-nemotron-8b",
        table_mode="overwrite",
    )

    doctor_objects: list[Doctor] = []

    for doctor in doctor_files:
        path = f"./fake_data/cvs/{doctor['filename']}"
        database.add_file(
            doctor_id=doctor["doctor_id"],
            file_path=path,
            session_id="1",
        )

        doctor_objects.append(
            Doctor(
                doctor_id=doctor["doctor_id"],
                capacity=doctor["capacity"],
                current_load=doctor["current_load"],
                name=doctor["name"],
            )
        )

    patient_requests = []

    for patient in patient_files:
        path = f"./fake_data/medical_records/{patient['filename']}"
        _patient_doc, rows = database.search_file(
            file_path=path,
            session_id="1",
            n=3,
        )

        print_retrieval(patient["patient_id"], rows)

        patient_request = patient_from_lancedb_rows(
            patient_id=patient["patient_id"],
            rows=rows,
            doctor_id_key="doctor_id",
            raw_value_key="_distance",
            raw_value_strategy="cosine_distance",
            raw_value_type="cosine_distance",
        )
        patient_requests.append(patient_request)

    service = AssignmentService(
        config=AssignmentConfig(
            load_penalty_weight=0.05,
            load_penalty_exponent=1.0,
            unassigned_score=0.0,
            min_candidate_score=0.0,
        )
    )

    summary = service.assign_new_patients(
        new_patients=patient_requests,
        doctors=doctor_objects,
    )

    print("\n===== FINAL ASSIGNMENT =====")
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


if __name__ == "__main__":
    main()
