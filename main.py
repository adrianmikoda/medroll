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
    Physician,
    PatientRequest,
    Candidate,
    patient_from_lancedb_rows,
)

import config


TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

app = FastAPI(
    title="MedRoll — Patient-Physician Assignment System",
    version="1.0.0",
)

class AppState:
    def __init__(self):
        self.physicians: dict[str, dict[str, Any]] = {}
        self.patients: dict[str, dict[str, Any]] = {}
        self.patient_cache_path = os.path.join("./lancedb", "patients_gui_cache.json")
        self.assignment_config = AssignmentConfig(
            load_penalty_weight=0.05,
            load_penalty_exponent=1.0,
            unassigned_score=0.0,
            min_candidate_score=0.0,
        )
        self.database = None
        self.database_model_name: str | None = None
        self.db_ready = False
        self.last_assignment: dict[str, Any] | None = None

    def try_init_database(self):
        selected_model_name = config.get_selected_model()
        if self.database is not None and self.database_model_name == selected_model_name:
            return

        selected_vector_dim = config.get_selected_vector_dim()

        try:
            from transformer_service.database import Database
            self.database = Database(
                db_path="./lancedb",
                table_name="physicians_gui",
                model_name=selected_model_name,
                table_mode=config.get_selected_mode(),
                vector_dim=selected_vector_dim,
            )
            self.database_model_name = selected_model_name
            self.db_ready = True
            self.load_physicians_from_db()
            self.load_patients_from_cache()
            self.sync_physician_loads_from_patients()
            
        except Exception as e:
            print(f"[WARN] Could not initialize model/DB: {e}")
            self.db_ready = False

    def load_physicians_from_db(self):
        if self.database is None:
            return
        try:
            records = self.database.get_all_records()
            self.physicians.clear()
            for r in records:
                phys_id = r.get("physician_id")
                if not phys_id:
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

                self.physicians[phys_id] = {
                    "physician_id": phys_id,
                    "name": r.get("name") or phys_id,
                    "capacity": capacity,
                    "current_load": 0,
                    "filename": r.get("filename") or "",
                    "language": r.get("language") or "?",
                }
            print(f"[INFO] Loaded {len(self.physicians)} physicians from database cache.")
        except Exception as e:
            print(f"[WARN] Failed to load physicians from database: {e}")

    def load_patients_from_cache(self):
        self.patients.clear()
        if not os.path.exists(self.patient_cache_path):
            return

        try:
            with open(self.patient_cache_path, "r", encoding="utf-8") as f:
                payload = json.load(f)

            records = payload.get("patients", []) if isinstance(payload, dict) else payload
            if not isinstance(records, list):
                records = []

            for record in records:
                patient_id = record.get("patient_id")
                if not patient_id:
                    continue

                self.patients[patient_id] = {
                    "patient_id": patient_id,
                    "filename": record.get("filename") or "",
                    "content": record.get("content") or "",
                    "language": record.get("language") or "?",
                    "assigned_physician_id": record.get("assigned_physician_id"),
                    "assigned_slot_index": record.get("assigned_slot_index"),
                    "candidates": record.get("candidates") or [],
                }

            print(f"[INFO] Loaded {len(self.patients)} patients from cache.")
        except Exception as e:
            print(f"[WARN] Failed to load patients from cache: {e}")

    def save_patients_to_cache(self):
        try:
            os.makedirs(os.path.dirname(self.patient_cache_path), exist_ok=True)
            with open(self.patient_cache_path, "w", encoding="utf-8") as f:
                json.dump({"patients": list(self.patients.values())}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to save patients cache: {e}")

    def clear_patient_cache(self):
        self.patients.clear()
        try:
            if os.path.exists(self.patient_cache_path):
                os.remove(self.patient_cache_path)
        except Exception as e:
            print(f"[WARN] Failed to clear patients cache: {e}")

    def sync_physician_loads_from_patients(self):
        loads: dict[str, int] = {phys_id: 0 for phys_id in self.physicians}

        for patient in self.patients.values():
            assigned_physician_id = patient.get("assigned_physician_id")
            if assigned_physician_id in loads:
                loads[assigned_physician_id] += 1

        for phys_id, physician in self.physicians.items():
            physician["current_load"] = loads.get(phys_id, 0)

    def change_model_and_reset(self, new_model_key: str, new_mode: str):
        config.set_model(new_model_key)
        config.set_selected_mode(new_mode)
        self.physicians.clear()
        self.patients.clear()
        self.last_assignment = None
        self.database = None
        self.database_model_name = None
        self.db_ready = False
        self.try_init_database()


state = AppState()


class ConfigModel(BaseModel):
    load_penalty_weight: float = 0.05
    load_penalty_exponent: float = 1.0
    unassigned_score: float = 0.0
    min_candidate_score: float = 0.0
    model_key: str | None = None
    mode: str | None = None


class AssignRequest(BaseModel):
    patient_ids: list[str] | None = None


class SearchRequest(BaseModel):
    patient_id: str
    n: int = 5


class ManualCandidateInput(BaseModel):
    physician_id: str
    score: float


class ManualPatientInput(BaseModel):
    patient_id: str
    candidates: list[ManualCandidateInput]


class ManualAssignRequest(BaseModel):
    patients: list[ManualPatientInput]


@app.get("/api/health")
def health():
    return {
        "status": "online",
        "model_loaded": state.db_ready,
        "model_name": config.get_selected_model(),
        "model_key": config.SELECTED_MODEL_KEY,
        "physicians_count": len(state.physicians),
        "patients_count": len(state.patients),
    }


@app.post("/api/physicians")
async def add_physician(
    file: UploadFile = File(...),
    physician_id: str = Form(...),
    name: str = Form(""),
    capacity: int = Form(5),
):
    if physician_id in state.physicians:
        raise HTTPException(400, f"Physician '{physician_id}' already exists")

    file_path = os.path.join(TEMP_DIR, file.filename)
    try:
        with open(file_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        if file.filename.lower().endswith(".json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                if "content" not in loaded_data:
                    raise ValueError("Invalid JSON structure. Key 'content' is required.")
                result = {
                    "content": loaded_data["content"],
                    "filename": file.filename,
                    "language": loaded_data.get("language") or "?",
                }
            except Exception as e:
                raise HTTPException(400, f"Failed to parse JSON file: {e}")
        else:
            converter = FileConverter(file_path, session_id="gui")
            result_json = converter.convert_to_json()
            result = json.loads(result_json)

            if result.get("status") == "error":
                raise HTTPException(400, result.get("message"))

        if state.database is not None:
            try:
                state.database.add(
                    physician_id=physician_id,
                    content=result["content"],
                    filename=result["filename"],
                    name=name or physician_id,
                    capacity=capacity,
                    language=result.get("language", "?"),
                )
            except Exception as e:
                print(f"[WARN] DB add failed: {e}")

        state.physicians[physician_id] = {
            "physician_id": physician_id,
            "name": name or physician_id,
            "capacity": capacity,
            "current_load": 0,
            "filename": result["filename"],
            "language": result.get("language", "?"),
        }

        state.sync_physician_loads_from_patients()

        return {"status": "ok", "physician": state.physicians[physician_id]}
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


@app.get("/api/physicians")
def list_physicians():
    return {"physicians": list(state.physicians.values())}


@app.delete("/api/physicians/{physician_id}")
def delete_physician(physician_id: str):
    if physician_id not in state.physicians:
        raise HTTPException(404, f"Physician '{physician_id}' not found")
    del state.physicians[physician_id]
    if state.database is not None:
        try:
            state.database.delete(physician_id)
        except Exception as e:
            print(f"[WARN] Failed to delete physician '{physician_id}' from DB: {e}")
            
    # Unassign patients assigned to the deleted physician
    patients_updated = False
    for patient in state.patients.values():
        if patient.get("assigned_physician_id") == physician_id:
            patient["assigned_physician_id"] = None
            patient["assigned_slot_index"] = None
            patients_updated = True
            
    if patients_updated:
        state.save_patients_to_cache()
        
    state.sync_physician_loads_from_patients()

    return {"status": "ok", "deleted": physician_id}


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

        if file.filename.lower().endswith(".json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                if "content" not in loaded_data:
                    raise ValueError("Invalid JSON structure. Key 'content' is required.")
                result = {
                    "content": loaded_data["content"],
                    "filename": file.filename,
                    "language": loaded_data.get("language") or "?",
                }
            except Exception as e:
                raise HTTPException(400, f"Failed to parse JSON file: {e}")
        else:
            converter = FileConverter(file_path, session_id="gui")
            result_json = converter.convert_to_json()
            result = json.loads(result_json)

            if result.get("status") == "error":
                raise HTTPException(400, result.get("message"))

        state.patients[patient_id] = {
            "patient_id": patient_id,
            "filename": result["filename"],
            "content": result["content"],
            "language": result.get("language", "?"),
            "assigned_physician_id": None,
            "assigned_slot_index": None,
            "candidates": [],
        }

        state.save_patients_to_cache()

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
    state.save_patients_to_cache()
    state.sync_physician_loads_from_patients()
    return {"status": "ok", "deleted": patient_id}


def _patient_view(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "content"}


def _make_patient_record(
    patient_id: str,
    filename: str,
    content: str,
    language: str,
    candidates: list[dict[str, Any]] | None = None,
    assigned_physician_id: str | None = None,
    assigned_slot_index: int | None = None,
) -> dict[str, Any]:
    return {
        "patient_id": patient_id,
        "filename": filename,
        "content": content,
        "language": language,
        "assigned_physician_id": assigned_physician_id,
        "assigned_slot_index": assigned_slot_index,
        "candidates": candidates or [],
    }


def _build_patient_request(pid: str, patient: dict[str, Any]) -> PatientRequest | None:
    cands = patient.get("candidates", [])
    if not cands:
        return None

    candidates = [
        Candidate(
            physician_id=c["physician_id"],
            score=c.get("score", 1.0 - c.get("distance", 0.0)),
            raw_value=c.get("distance"),
            raw_value_type="cosine_distance",
        )
        for c in cands
    ]

    return PatientRequest(patient_id=pid, candidates=candidates)


def _apply_assignment_decisions(decisions) -> None:
    for decision in decisions:
        patient = state.patients.get(decision.patient_id)
        if patient is not None:
            patient["assigned_physician_id"] = decision.assigned_physician_id
            patient["assigned_slot_index"] = decision.assigned_slot_index

    state.save_patients_to_cache()
    state.sync_physician_loads_from_patients()


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
            "physician_id": row.get("physician_id", "?"),
            "filename": row.get("filename", "?"),
            "distance": row.get("_distance"),
            "score": 1.0 - row.get("_distance", 0.0),
        })

    state.patients[req.patient_id]["candidates"] = candidates
    state.save_patients_to_cache()
    return {"patient_id": req.patient_id, "results": candidates}


@app.post("/api/assign")
def run_assignment(req: AssignRequest):
    if not state.physicians:
        raise HTTPException(400, "No physicians registered")

    selected_mode = config.get_selected_mode()

    physician_objects = [
        Physician(
            physician_id=d["physician_id"],
            name=d["name"],
            capacity=d["capacity"],
            current_load=d["current_load"],
        )
        for d in state.physicians.values()
    ]

    patient_requests = []

    if selected_mode == "open":
        candidate_ids = req.patient_ids or list(state.patients.keys())
        for pid in candidate_ids:
            patient = state.patients.get(pid)
            if patient is None:
                continue

            if patient.get("assigned_physician_id") is not None:
                continue

            patient_request = _build_patient_request(pid, patient)
            if patient_request is not None:
                patient_requests.append(patient_request)
    else:
        candidate_ids = req.patient_ids or list(state.patients.keys())
        for pid in candidate_ids:
            patient = state.patients.get(pid)
            if patient is None:
                continue

            patient_request = _build_patient_request(pid, patient)
            if patient_request is not None:
                patient_requests.append(patient_request)

    if not patient_requests:
        if selected_mode == "open":
            raise HTTPException(400, "No new unassigned patients with search results to assign")
        raise HTTPException(400, "No patients with search results to assign")

    service = AssignmentService(config=state.assignment_config)
    if selected_mode == "overwrite":
        summary = service.rebalance_batch(
            patients_to_reassign=patient_requests,
            physicians=physician_objects,
        )
    else:
        summary = service.assign_new_patients(
            new_patients=patient_requests,
            physicians=physician_objects,
        )

    decisions = []
    for d in summary.decisions:
        decisions.append({
            "patient_id": d.patient_id,
            "assigned_physician_id": d.assigned_physician_id,
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
        "physician_loads": summary.physician_loads,
        "decisions": decisions,
    }

    _apply_assignment_decisions(summary.decisions)

    state.last_assignment = result
    return result


@app.post("/api/assign/manual")
def run_manual_assignment(req: ManualAssignRequest):
    if not state.physicians:
        raise HTTPException(400, "No physicians registered")

    physician_objects = [
        Physician(
            physician_id=d["physician_id"],
            name=d["name"],
            capacity=d["capacity"],
            current_load=d["current_load"],
        )
        for d in state.physicians.values()
    ]

    patient_requests = []
    for mp in req.patients:
        candidates = [
            Candidate(physician_id=c.physician_id, score=c.score)
            for c in mp.candidates
        ]
        patient_requests.append(
            PatientRequest(patient_id=mp.patient_id, candidates=candidates)
        )

    service = AssignmentService(config=state.assignment_config)
    selected_mode = config.get_selected_mode()
    if selected_mode == "overwrite":
        summary = service.rebalance_batch(
            patients_to_reassign=patient_requests,
            physicians=physician_objects,
        )
    else:
        summary = service.assign_new_patients(
            new_patients=patient_requests,
            physicians=physician_objects,
        )

    decisions = []
    for d in summary.decisions:
        decisions.append({
            "patient_id": d.patient_id,
            "assigned_physician_id": d.assigned_physician_id,
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
        "physician_loads": summary.physician_loads,
        "decisions": decisions,
    }

    _apply_assignment_decisions(summary.decisions)

    state.last_assignment = result
    return result


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
        "mode": config.get_selected_mode(),
        "modes": config.MODE_CHOICES,
    }


@app.put("/api/config")
def update_config(cfg: ConfigModel):
    try:
        state.assignment_config = AssignmentConfig(
            load_penalty_weight=cfg.load_penalty_weight,
            load_penalty_exponent=cfg.load_penalty_exponent,
            unassigned_score=cfg.unassigned_score,
            min_candidate_score=cfg.min_candidate_score,
        )
        model_changed = cfg.model_key is not None and cfg.model_key != config.SELECTED_MODEL_KEY
        mode_changed = cfg.mode is not None and cfg.mode != config.get_selected_mode()
        if model_changed:
            new_model_key = cfg.model_key or config.SELECTED_MODEL_KEY
            new_mode = cfg.mode or config.get_selected_mode()
            state.change_model_and_reset(new_model_key, new_mode)
        elif mode_changed:
            new_mode = cfg.mode or config.get_selected_mode()
            config.set_selected_mode(new_mode)
            if new_mode == "overwrite":
                state.change_model_and_reset(config.SELECTED_MODEL_KEY, new_mode)
        return {"status": "ok", "config": get_config()}
    except ValueError as e:
        raise HTTPException(400, detail=str(e))


@app.post("/api/demo/load")
def load_demo_data():
    """Load data physicians and patients for quick testing."""
    physicians_dir = "./data/physicians"
    patients_dir = "./data/patients"

    loaded_physicians = []
    loaded_patients = []

    if os.path.exists(physicians_dir):
        files = sorted([f for f in os.listdir(physicians_dir) if f.lower().endswith((".pdf", ".docx"))])
        for idx, filename in enumerate(files):
            path = os.path.join(physicians_dir, filename)
            physician_id = f"doc_{idx + 1}"
            name = os.path.splitext(filename)[0].replace("cv", "").replace("_", " ")
            capacity = 3

            try:
                converter = FileConverter(path, session_id="demo")
                result = json.loads(converter.convert_to_json())
                if result.get("status") == "error":
                    continue

                if state.database is not None:
                    try:
                        state.database.add(
                            physician_id=physician_id,
                            content=result["content"],
                            filename=result["filename"],
                            name=name,
                            capacity=capacity,
                            language=result.get("language", "?"),
                        )
                    except Exception:
                        pass

                state.physicians[physician_id] = {
                    "physician_id": physician_id,
                    "name": name,
                    "capacity": capacity,
                    "current_load": 0,
                    "filename": result["filename"],
                    "language": result.get("language", "?"),
                }
                loaded_physicians.append(physician_id)
            except Exception:
                traceback.print_exc()

    # Load all patients from `./data/patients`
    if os.path.exists(patients_dir):
        files = sorted([f for f in os.listdir(patients_dir) if f.lower().endswith((".pdf", ".docx"))])
        for idx, filename in enumerate(files):
            path = os.path.join(patients_dir, filename)
            patient_id = f"pat_{idx + 1}"

            try:
                converter = FileConverter(path, session_id="demo")
                result = json.loads(converter.convert_to_json())
                if result.get("status") == "error":
                    continue

                state.patients[patient_id] = {
                    "patient_id": patient_id,
                    "filename": result["filename"],
                    "content": result["content"],
                    "language": result.get("language", "?"),
                    "assigned_physician_id": None,
                    "assigned_slot_index": None,
                    "candidates": [],
                }
                loaded_patients.append(patient_id)
            except Exception:
                traceback.print_exc()

    state.save_patients_to_cache()
    state.sync_physician_loads_from_patients()

    return {
        "status": "ok",
        "loaded_physicians": loaded_physicians,
        "loaded_patients": loaded_patients,
    }


@app.post("/api/demo/load_json")
def load_json_demo_data():
    """Load JSON physicians and patients for testing."""
    physicians_dir = "./data/physicians_json"
    patients_dir = "./data/patients_json"

    loaded_physicians = []
    loaded_patients = []

    # Load all physicians from `./data/physicians_json`
    if os.path.exists(physicians_dir):
        files = sorted([f for f in os.listdir(physicians_dir) if f.lower().endswith(".json")])
        for idx, filename in enumerate(files):
            path = os.path.join(physicians_dir, filename)
            physician_id = f"doc_json_{idx + 1}"
            capacity = 3

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                name = os.path.splitext(orig_filename)[0].replace("cv_", "").replace("_simple_anonymization", " ")
                content = data.get("content", "")
                language = data.get("language", "?")

                if not content:
                    continue

                if state.database is not None:
                    try:
                        state.database.add(
                            physician_id=physician_id,
                            content=content,
                            filename=filename,
                            name=name,
                            capacity=capacity,
                            language=language,
                        )
                    except Exception:
                        pass

                state.physicians[physician_id] = {
                    "physician_id": physician_id,
                    "name": name,
                    "capacity": capacity,
                    "current_load": 0,
                    "filename": filename,
                    "language": language,
                }
                loaded_physicians.append(physician_id)
            except Exception:
                traceback.print_exc()

    # Load all patients from `./data/patients_json`
    if os.path.exists(patients_dir):
        files = sorted([f for f in os.listdir(patients_dir) if f.lower().endswith(".json")])
        for idx, filename in enumerate(files):
            path = os.path.join(patients_dir, filename)
            patient_id = f"pat_json_{idx + 1}"

            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                content = data.get("content", "")
                language = data.get("language", "?")

                if not content:
                    continue

                state.patients[patient_id] = {
                    "patient_id": patient_id,
                    "filename": filename,
                    "content": content,
                    "language": language,
                    "assigned_physician_id": None,
                    "assigned_slot_index": None,
                    "candidates": [],
                }
                loaded_patients.append(patient_id)
            except Exception:
                traceback.print_exc()

    state.save_patients_to_cache()
    state.sync_physician_loads_from_patients()

    return {
        "status": "ok",
        "loaded_physicians": loaded_physicians,
        "loaded_patients": loaded_patients,
    }


@app.on_event("startup")
async def startup():
    state.try_init_database()


app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def serve_index():
    return FileResponse("frontend/index.html")
