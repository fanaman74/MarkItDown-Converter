import os
from fastapi import FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Local Folder to Markdown Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/validate-path")
async def validate_path(path: str = Form(...)):
    if not os.path.exists(path):
        return {"valid": False, "error": f"Path '{path}' does not exist on local disk."}
    if not os.path.isdir(path):
        return {"valid": False, "error": f"Path '{path}' is not a directory."}
    if not os.access(path, os.W_OK):
        return {"valid": False, "error": f"Directory '{path}' is not writeable."}
    return {"valid": True, "error": None}
