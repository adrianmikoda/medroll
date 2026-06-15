import os
import shutil
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from .file_converter import FileConverter
from .llm.processor import MedicalProcessor

medical_llm = None

app = FastAPI(
    title="Medical Document Converter API",
    description="API to convert PDF/DOCX files to JSON - personal data anonymization",
    version="1.0.0",
)

TEMP_DIR = "temp_uploads"
os.makedirs(TEMP_DIR, exist_ok=True)


@app.get("/")
def home():
    status = "ready" if medical_llm is not None else "waiting for first request"
    return {"status": "online", "llm_engine": status}


@app.post("/convert/{session_id}")
async def convert_file(session_id: str, file: UploadFile = File(...)):
    global medical_llm
    if medical_llm is None:
        print("INITIALIZING LLM ENGINE... Please wait, loading model to GPUs.")
        try:
            medical_llm = MedicalProcessor()
            print("Medical LLM successfully initialized!")
        except Exception as e:
            medical_llm = None
            raise HTTPException(
                status_code=500, detail=f"Failed to load LLM Engine: {str(e)}"
            )
        
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    file_path = None
    try:
        file_path = os.path.join(TEMP_DIR, file.filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        converter = FileConverter(file_path, session_id, processor=medical_llm)
        result_json = await converter.convert()

        result_data = json.loads(result_json)

        if isinstance(result_data, dict) and result_data.get("status") == "error":
            raise HTTPException(
                status_code=400, detail=result_data.get("message")
            )

        return result_data

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Document processing error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
