from __future__ import annotations

import pyarrow as pa
import json
from typing import Any

import lancedb
from lancedb.pydantic import LanceModel, Vector
from sentence_transformers import SentenceTransformer

from converter_service.file_converter import FileConverter

class Database:
    def __init__(
        self,
        db_path: str = "./lancedb",
        table_name: str = "physicians",
        table_mode: str = "overwrite",
        model_name: str = "nvidia/llama-embed-nemotron-8b",
        vector_dim: int = 4096
    ) -> None:

        self.model = SentenceTransformer(
            model_name,
            trust_remote_code=True,
            model_kwargs={"attn_implementation": "eager"},
            processor_kwargs={"padding_side": "left"},
        )
        self.db = lancedb.connect(db_path)
        self.table_name = table_name

        existing_tables = set(self.db.table_names())

        dynamic_schema = pa.schema([
            pa.field("physician_id", pa.string()),
            pa.field("filename", pa.string()),
            pa.field("text", pa.string()),
            pa.field("vector", pa.list_(pa.float32(), list_size=vector_dim)),
            pa.field("name", pa.string()),
            pa.field("capacity", pa.int32()),
            pa.field("language", pa.string())
        ])

        if table_mode == "overwrite":
            self.tbl = self.db.create_table(
                table_name,
                schema=dynamic_schema,
                mode="overwrite",
            )
        elif table_name in existing_tables:
            self.tbl = self.db.open_table(table_name)
            try:
                    vector_field = self.tbl.schema.field("vector")
                    if hasattr(vector_field.type, "list_size") and vector_field.type.list_size != vector_dim:
                        self.tbl = self.db.create_table(
                            table_name,
                            schema=dynamic_schema,
                            mode="overwrite",
                        )
            except Exception:
                self.tbl = self.db.create_table(
                    table_name,
                    schema=dynamic_schema,
                    mode="overwrite",
                )
        else:
            self.tbl = self.db.create_table(
                table_name,
                schema=dynamic_schema,
                mode="create",
            )

    def encode_physician_text(self, text: str) -> list[float]:
        return self.model.encode_document(text).tolist()
    
    def encode_patient_query(self, text: str) -> list[float]:
        task = "Given a question, retrieve passages that answer the question"
        query = f"Instruct: {task}\nQuery: {text}"
        return self.model.encode_query(query).tolist()

    def add(
        self,
        physician_id: str,
        content: str,
        filename: str,
        name: str = "",
        capacity: int = 5,
        language: str = "?"
    ) -> None:
        row = {
            "physician_id": physician_id,
            "filename": filename,
            "text": content,
            "vector": self.encode_physician_text(content),
            "name": name or physician_id,
            "capacity": capacity,
            "language": language,
        }
        self.tbl.add([row])

    def get_all_records(self) -> list[dict[str, Any]]:
        try:
            return self.tbl.to_pandas().to_dict(orient="records")
        except Exception as e:
            print(f"[WARN] Error fetching records from LanceDB: {e}")
            return []

    def delete(self, physician_id: str) -> None:
        try:
            self.tbl.delete(f"physician_id = '{physician_id}'")
        except Exception as e:
            print(f"[WARN] Error deleting record from LanceDB: {e}")

    def search(self, query: str, n: int = 5) -> list[dict[str, Any]]:
        query_vector = self.encode_patient_query(query)

        results_df = (
            self.tbl.search(query_vector)
            .distance_type("cosine")
            .limit(n)
            .to_pandas()
        )

        return results_df.to_dict(orient="records")
