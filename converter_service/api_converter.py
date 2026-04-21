import os
import shutil
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from .file_converter import FileConverter

app = FastAPI(
    title = "Medical Document Converter API",
    description="API to convert PDF/DOCX files to JSON - personal data anonymization",
    version="1.0.0"
)

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)

@app.get("/")
def home():
    return {"status": "online", "message": "API run"}

@app.post("/convert/{session_id}")
async def convert_file(session_id: str, file: UploadFile = File(...)):
    # main endpoint
    file_path = os.path.join(TEMP_DIR, file.filename) # type: ignore

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        converter = FileConverter(file_path, session_id)
        result_json = converter.convert_to_json()

        result_data = json.loads(result_json)
        
        if result_data.get("status") == "error":
            raise HTTPException(status_code=400, detail=result_data.get("message"))
        
        return result_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if os.path.exists(file_path):
            os.remove(file_path) 
