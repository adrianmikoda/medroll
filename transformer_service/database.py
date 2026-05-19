from __future__ import annotations

import json
from typing import Any

import lancedb
from lancedb.pydantic import LanceModel, Vector
from sentence_transformers import SentenceTransformer

from converter_service.file_converter import FileConverter


class DoctorProfileSchema(LanceModel):
    doctor_id: str
    filename: str
    text: str
    vector: Vector(384)  # type: ignore


class Database:
    def __init__(
        self,
        db_path: str = "./lancedb",
        table_name: str = "doctors",
        model_name: str = "all-MiniLM-L6-v2",
        table_mode: str = "overwrite",
    ) -> None:
        self.model = SentenceTransformer(model_name)
        self.db = lancedb.connect(db_path)
        self.table_name = table_name

        existing_tables = set(self.db.table_names())

        if table_mode == "overwrite":
            self.tbl = self.db.create_table(
                table_name,
                schema=DoctorProfileSchema,
                mode="overwrite",
            )
        elif table_name in existing_tables:
            self.tbl = self.db.open_table(table_name)
        else:
            self.tbl = self.db.create_table(
                table_name,
                schema=DoctorProfileSchema,
                mode="create",
            )

    def encode_text(self, text: str) -> list[float]:
        # Normalizuję embedding, żeby cosine miało sensowną i stabilną geometrię.
        return self.model.encode(
            text,
            normalize_embeddings=True,
        ).tolist()

    def add(self, doctor_id: str, data: str, filename: str) -> None:
        row = {
            "doctor_id": doctor_id,
            "filename": filename,
            "text": data,
            "vector": self.encode_text(data),
        }
        self.tbl.add([row])

    def add_file(self, doctor_id: str, file_path: str, session_id: str = "1") -> dict[str, Any]:
        data = json.loads(FileConverter(file_path, session_id).convert_to_json())
        self.add_json(doctor_id=doctor_id, data=data)
        
        return data
    
    def add_json(self, doctor_id, data: dict[str, Any]) -> None:
        if data.get("status") == "error":
            raise ValueError(data["message"])

        self.add(
            doctor_id=doctor_id,
            data=data["content"],
            filename=data["filename"],
        )

    def search(self, query: str, n: int = 5) -> list[dict[str, Any]]:
        query_vector = self.encode_text(query)

        results_df = (
            self.tbl.search(query_vector)
            .distance_type("cosine")
            .limit(n)
            .to_pandas()
        )

        return results_df.to_dict(orient="records")

    def search_file(
        self,
        file_path: str,
        session_id: str = "1",
        n: int = 5,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        data = json.loads(FileConverter(file_path, session_id).convert_to_json())

        if data.get("status") == "error":
            raise ValueError(data["message"])

        rows = self.search(query=data["content"], n=n)
        return data, rows
