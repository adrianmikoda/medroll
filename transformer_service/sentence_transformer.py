import os
import lancedb
import pandas as pd
from lancedb.pydantic import Vector, LanceModel
from sentence_transformers import SentenceTransformer
from typing import List
from converter_service.file_converter import FileConverter
import json
from tqdm import tqdm

class MySchema(LanceModel):
    filename: str
    text: str
    vector: Vector(384) # type: ignore

class Database():
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.db = lancedb.connect("./lancedb")
        self.tbl = self.db.create_table("data", schema=MySchema, mode="overwrite")

    def add(self, data: str, filename: str) -> None:
        data_with_embeddings = {"filename": filename,
                                "text": data, 
                                "vector": self.model.encode(data).tolist()} 
        self.tbl.add([data_with_embeddings])

    def search(self, query: str, n: int) -> None:
        query_vector = self.model.encode(query).tolist()
        results_df = self.tbl.search(query_vector).limit(n).to_pandas()

        if results_df.empty:
            print("No results found.")
        else:
            for idx, row in results_df.iterrows():
                distance = row.get('_distance', 0)
                print(f"\n[{idx+1}] File: {row['filename']} (Distance: {distance:.4f})") # type: ignore

def main():
    data_directory = "./fake_data/cvs/"
    data_filenames = ["cv_kardiochirurg.pdf",
                      "cv_ortopeda.pdf",
                      "cv_psychiatra.pdf"]
    
    query_directory = "./fake_data/medical_records/"
    query_filenames = ["karta_1.pdf",
                       "karta_2.pdf",
                       "karta_3.pdf"]

    database = Database()
    print("\n\n")

    for filename in tqdm(data_filenames):
        data = json.loads(FileConverter(f"{data_directory}{filename}", "1").convert_to_json())
        database.add(data["content"], data["filename"])
    print(f"succesfully loaded all data from {data_directory}")
    print("\n\n")

    for filename in query_filenames:
        print(filename)
        data = json.loads(FileConverter(f"{query_directory}{filename}", "1").convert_to_json())
        database.search(data["content"], 3)
    
if __name__ == "__main__":
    main()
