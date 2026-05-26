from __future__ import annotations

import os
import json
import shutil
import traceback
from typing import Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from converter_service.file_converter import FileConverter
from assignment_service import (
    AssignmentConfig,
    AssignmentService,
    Doctor,
    PatientRequest,
    Candidate,
    patient_from_lancedb_rows,
)

import config


TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

app = FastAPI(
    title="MedRoll — Patient-Doctor Assignment System",
    version="1.0.0",
)

class AppState:
    def __init__(self):
        self.doctors: dict[str, dict[str, Any]] = {}
        self.patients: dict[str, dict[str, Any]] = {}
        self.assignment_config = AssignmentConfig(
            load_penalty_weight=0.05,
            load_penalty_exponent=1.0,
            unassigned_score=0.0,
            min_candidate_score=0.0,
        )
        self.database = None
        self.db_ready = False
        self.last_assignment: dict[str, Any] | None = None

    def try_init_database(self, table_mode: str = "cache"):
        if self.database is not None and table_mode == "cache":
            return

        selected_model_name = config.get_selected_model()
        selected_vector_dim = config.get_selected_vector_dim()

        try:
            from transformer_service.database import Database
            self.database = Database(
                db_path="./lancedb",
                table_name="doctors_gui",
                model_name=selected_model_name,
                table_mode=table_mode,
                vector_dim=selected_vector_dim,
            )
            self.db_ready = True
            if table_mode == "cache":
                self.load_doctors_from_db()
        except Exception as e:
            print(f"[WARN] Could not initialize model/DB: {e}")
            self.db_ready = False

    def load_doctors_from_db(self):
        if self.database is None:
            return
        try:
            records = self.database.get_all_records()
            self.doctors.clear()
            for r in records:
                doc_id = r.get("doctor_id")
                if not doc_id:
                    continue
                capacity = r.get("capacity", 5)
                try:
                    import math
                    if isinstance(capacity, float) and math.isnan(capacity):
                        capacity = 5
                    else:
                        capacity = int(capacity)
                except Exception:
                    capacity = 5

                self.doctors[doc_id] = {
                    "doctor_id": doc_id,
                    "name": r.get("name") or doc_id,
                    "capacity": capacity,
                    "current_load": 0,
                    "filename": r.get("filename") or "",
                    "content_preview": (r.get("text") or "")[:300],
                    "language": r.get("language") or "?",
                }
            print(f"[INFO] Loaded {len(self.doctors)} doctors from database cache.")
        except Exception as e:
            print(f"[WARN] Failed to load doctors from database: {e}")

    def change_model_and_reset(self, new_model_key: str):
        config.set_model(new_model_key)
        self.doctors.clear()
        self.patients.clear()
        self.last_assignment = None
        self.database = None
        self.db_ready = False
        self.try_init_database(table_mode="overwrite")


state = AppState()


# ── Pydantic request/response models ─────────────────────────────
class ConfigModel(BaseModel):
    load_penalty_weight: float = 0.05
    load_penalty_exponent: float = 1.0
    unassigned_score: float = 0.0
    min_candidate_score: float = 0.0
    model_key: str | None = None


class AssignRequest(BaseModel):
    patient_ids: list[str] | None = None  # None = all patients


class SearchRequest(BaseModel):
    patient_id: str
    n: int = 5


class ManualCandidateInput(BaseModel):
    doctor_id: str
    score: float


class ManualPatientInput(BaseModel):
    patient_id: str
    candidates: list[ManualCandidateInput]


class ManualAssignRequest(BaseModel):
    patients: list[ManualPatientInput]


# ── Health ────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {
        "status": "online",
        "model_loaded": state.db_ready,
        "model_name": config.get_selected_model(),
        "model_key": config.SELECTED_MODEL_KEY,
        "doctors_count": len(state.doctors),
        "patients_count": len(state.patients),
    }


# ── Doctors ───────────────────────────────────────────────────────
@app.post("/api/doctors")
async def add_doctor(
    file: UploadFile = File(...),
    doctor_id: str = Form(...),
    name: str = Form(""),
    capacity: int = Form(5),
):
    if doctor_id in state.doctors:
        raise HTTPException(400, f"Doctor '{doctor_id}' already exists")

    file_path = os.path.join(TEMP_DIR, file.filename)
    try:
        with open(file_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        converter = FileConverter(file_path, session_id="gui")
        result_json = converter.convert_to_json()
        result = json.loads(result_json)

        if result.get("status") == "error":
            raise HTTPException(400, result.get("message"))

        # Try to add to vector DB
        if state.database is not None:
            try:
                state.database.add(
                    doctor_id=doctor_id,
                    data=result["content"],
                    filename=result["filename"],
                    name=name or doctor_id,
                    capacity=capacity,
                    language=result.get("language", "?"),
                )
            except Exception as e:
                print(f"[WARN] DB add failed: {e}")

        state.doctors[doctor_id] = {
            "doctor_id": doctor_id,
            "name": name or doctor_id,
            "capacity": capacity,
            "current_load": 0,
            "filename": result["filename"],
            "content_preview": result["content"][:300],
            "language": result.get("language", "?"),
        }

        return {"status": "ok", "doctor": state.doctors[doctor_id]}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@app.get("/api/doctors")
def list_doctors():
    return {"doctors": list(state.doctors.values())}


@app.delete("/api/doctors/{doctor_id}")
def delete_doctor(doctor_id: str):
    if doctor_id not in state.doctors:
        raise HTTPException(404, f"Doctor '{doctor_id}' not found")
    del state.doctors[doctor_id]
    return {"status": "ok", "deleted": doctor_id}


# ── Patients ──────────────────────────────────────────────────────
@app.post("/api/patients")
async def add_patient(
    file: UploadFile = File(...),
    patient_id: str = Form(...),
):
    if patient_id in state.patients:
        raise HTTPException(400, f"Patient '{patient_id}' already exists")

    file_path = os.path.join(TEMP_DIR, file.filename)
    try:
        with open(file_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        converter = FileConverter(file_path, session_id="gui")
        result_json = converter.convert_to_json()
        result = json.loads(result_json)

        if result.get("status") == "error":
            raise HTTPException(400, result.get("message"))

        state.patients[patient_id] = {
            "patient_id": patient_id,
            "filename": result["filename"],
            "content_preview": result["content"][:300],
            "content": result["content"],
            "language": result.get("language", "?"),
            "candidates": [],  # filled by search
        }

        return {"status": "ok", "patient": _patient_view(state.patients[patient_id])}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@app.get("/api/patients")
def list_patients():
    return {"patients": [_patient_view(p) for p in state.patients.values()]}


@app.delete("/api/patients/{patient_id}")
def delete_patient(patient_id: str):
    if patient_id not in state.patients:
        raise HTTPException(404, f"Patient '{patient_id}' not found")
    del state.patients[patient_id]
    return {"status": "ok", "deleted": patient_id}


def _patient_view(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "content"}


# ── Search ────────────────────────────────────────────────────────
@app.post("/api/search")
def search_patient(req: SearchRequest):
    if not state.db_ready or state.database is None:
        raise HTTPException(503, "Vector database / model not loaded")

    patient = state.patients.get(req.patient_id)
    if patient is None:
        raise HTTPException(404, f"Patient '{req.patient_id}' not found")

    rows = state.database.search(query=patient["content"], n=req.n)

    candidates = []
    for row in rows:
        candidates.append({
            "doctor_id": row.get("doctor_id", "?"),
            "filename": row.get("filename", "?"),
            "distance": row.get("_distance"),
            "score": 1.0 - row.get("_distance", 0.0),
        })

    state.patients[req.patient_id]["candidates"] = candidates
    return {"patient_id": req.patient_id, "results": candidates}


# ── Assignment ────────────────────────────────────────────────────
@app.post("/api/assign")
def run_assignment(req: AssignRequest):
    if not state.doctors:
        raise HTTPException(400, "No doctors registered")

    doctor_objects = [
        Doctor(
            doctor_id=d["doctor_id"],
            name=d["name"],
            capacity=d["capacity"],
            current_load=d["current_load"],
        )
        for d in state.doctors.values()
    ]

    patient_ids = req.patient_ids or list(state.patients.keys())
    patient_requests = []

    for pid in patient_ids:
        patient = state.patients.get(pid)
        if patient is None:
            continue

        cands = patient.get("candidates", [])
        if not cands:
            continue

        candidates = [
            Candidate(
                doctor_id=c["doctor_id"],
                score=c.get("score", 1.0 - c.get("distance", 0.0)),
                raw_value=c.get("distance"),
                raw_value_type="cosine_distance",
            )
            for c in cands
        ]

        patient_requests.append(
            PatientRequest(patient_id=pid, candidates=candidates)
        )

    if not patient_requests:
        raise HTTPException(400, "No patients with search results to assign")

    service = AssignmentService(config=state.assignment_config)
    summary = service.assign_new_patients(
        new_patients=patient_requests,
        doctors=doctor_objects,
    )

    decisions = []
    for d in summary.decisions:
        decisions.append({
            "patient_id": d.patient_id,
            "assigned_doctor_id": d.assigned_doctor_id,
            "assigned_slot_index": d.assigned_slot_index,
            "candidate_rank": d.candidate_rank,
            "base_score": round(d.base_score, 4),
            "slot_penalty": round(d.slot_penalty, 4),
            "final_score": round(d.final_score, 4),
            "reason": d.reason,
        })

    result = {
        "mode": summary.mode,
        "assigned_count": summary.assigned_count,
        "unassigned_count": summary.unassigned_count,
        "total_base_score": round(summary.total_base_score, 4),
        "total_penalty": round(summary.total_penalty, 4),
        "total_final_score": round(summary.total_final_score, 4),
        "doctor_loads": summary.doctor_loads,
        "decisions": decisions,
    }

    # Update doctor loads
    for doc_id, load in summary.doctor_loads.items():
        if doc_id in state.doctors:
            state.doctors[doc_id]["current_load"] = load

    state.last_assignment = result
    return result


# ── Manual assignment (without model) ─────────────────────────────
@app.post("/api/assign/manual")
def run_manual_assignment(req: ManualAssignRequest):
    if not state.doctors:
        raise HTTPException(400, "No doctors registered")

    doctor_objects = [
        Doctor(
            doctor_id=d["doctor_id"],
            name=d["name"],
            capacity=d["capacity"],
            current_load=d["current_load"],
        )
        for d in state.doctors.values()
    ]

    patient_requests = []
    for mp in req.patients:
        candidates = [
            Candidate(doctor_id=c.doctor_id, score=c.score)
            for c in mp.candidates
        ]
        patient_requests.append(
            PatientRequest(patient_id=mp.patient_id, candidates=candidates)
        )

    service = AssignmentService(config=state.assignment_config)
    summary = service.assign_new_patients(
        new_patients=patient_requests,
        doctors=doctor_objects,
    )

    decisions = []
    for d in summary.decisions:
        decisions.append({
            "patient_id": d.patient_id,
            "assigned_doctor_id": d.assigned_doctor_id,
            "assigned_slot_index": d.assigned_slot_index,
            "candidate_rank": d.candidate_rank,
            "base_score": round(d.base_score, 4),
            "slot_penalty": round(d.slot_penalty, 4),
            "final_score": round(d.final_score, 4),
            "reason": d.reason,
        })

    result = {
        "mode": summary.mode,
        "assigned_count": summary.assigned_count,
        "unassigned_count": summary.unassigned_count,
        "total_base_score": round(summary.total_base_score, 4),
        "total_penalty": round(summary.total_penalty, 4),
        "total_final_score": round(summary.total_final_score, 4),
        "doctor_loads": summary.doctor_loads,
        "decisions": decisions,
    }

    for doc_id, load in summary.doctor_loads.items():
        if doc_id in state.doctors:
            state.doctors[doc_id]["current_load"] = load

    state.last_assignment = result
    return result


# ── Config ────────────────────────────────────────────────────────
@app.get("/api/config")
def get_config():
    c = state.assignment_config
    return {
        "load_penalty_weight": c.load_penalty_weight,
        "load_penalty_exponent": c.load_penalty_exponent,
        "unassigned_score": c.unassigned_score,
        "min_candidate_score": c.min_candidate_score,
        "model_key": config.SELECTED_MODEL_KEY,
        "models": list(config.MODEL_CHOICES.keys()),
    }


@app.put("/api/config")
def update_config(cfg: ConfigModel):
    state.assignment_config = AssignmentConfig(
        load_penalty_weight=cfg.load_penalty_weight,
        load_penalty_exponent=cfg.load_penalty_exponent,
        unassigned_score=cfg.unassigned_score,
        min_candidate_score=cfg.min_candidate_score,
    )
    if cfg.model_key and cfg.model_key != config.SELECTED_MODEL_KEY:
        state.change_model_and_reset(cfg.model_key)
    return {"status": "ok", "config": get_config()}


# ── Demo data loader ──────────────────────────────────────────────
@app.post("/api/demo/load")
def load_demo_data():
    """Load fake_data doctors and patients for quick testing."""
    doctor_files = [
        {"doctor_id": "doc_cardio", "filename": "cv_kardiochirurg.pdf", "capacity": 3, "name": "Kardiochirurg"},
        {"doctor_id": "doc_ortho", "filename": "cv_ortopeda.pdf", "capacity": 3, "name": "Ortopeda"},
        {"doctor_id": "doc_psych", "filename": "cv_psychiatra.pdf", "capacity": 3, "name": "Psychiatra"},
    ]
    patient_files = [
        {"patient_id": "pat_1", "filename": "karta_1.pdf"},
        {"patient_id": "pat_2", "filename": "karta_2.pdf"},
        {"patient_id": "pat_3", "filename": "karta_3.pdf"},
    ]

    loaded_doctors = []
    loaded_patients = []

    for doc in doctor_files:
        path = f"./fake_data/cvs/{doc['filename']}"
        if not os.path.exists(path):
            continue

        try:
            converter = FileConverter(path, session_id="demo")
            result = json.loads(converter.convert_to_json())
            if result.get("status") == "error":
                continue

            if state.database is not None:
                try:
                    state.database.add(
                        doctor_id=doc["doctor_id"],
                        data=result["content"],
                        filename=result["filename"],
                        name=doc["name"],
                        capacity=doc["capacity"],
                        language=result.get("language", "?"),
                    )
                except Exception:
                    pass

            state.doctors[doc["doctor_id"]] = {
                "doctor_id": doc["doctor_id"],
                "name": doc["name"],
                "capacity": doc["capacity"],
                "current_load": 0,
                "filename": result["filename"],
                "content_preview": result["content"][:300],
                "language": result.get("language", "?"),
            }
            loaded_doctors.append(doc["doctor_id"])
        except Exception:
            traceback.print_exc()

    for pat in patient_files:
        path = f"./fake_data/medical_records/{pat['filename']}"
        if not os.path.exists(path):
            continue

        try:
            converter = FileConverter(path, session_id="demo")
            result = json.loads(converter.convert_to_json())
            if result.get("status") == "error":
                continue

            state.patients[pat["patient_id"]] = {
                "patient_id": pat["patient_id"],
                "filename": result["filename"],
                "content_preview": result["content"][:300],
                "content": result["content"],
                "language": result.get("language", "?"),
                "candidates": [],
            }
            loaded_patients.append(pat["patient_id"])
        except Exception:
            traceback.print_exc()

    return {
        "status": "ok",
        "loaded_doctors": loaded_doctors,
        "loaded_patients": loaded_patients,
    }


@app.on_event("startup")
async def startup():
    state.try_init_database()


app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def serve_index():
    return FileResponse("frontend/index.html")
