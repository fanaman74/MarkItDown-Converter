import os
import tempfile
import shutil
from fastapi import FastAPI, Form, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from markitdown import MarkItDown

app = FastAPI(title="Local Folder to Markdown Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5180"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MarkItDown once
md = MarkItDown()

@app.post("/validate-path")
async def validate_path(path: str = Form(...)):
    if not os.path.exists(path):
        return {"valid": False, "error": f"Path '{path}' does not exist on local disk."}
    if not os.path.isdir(path):
        return {"valid": False, "error": f"Path '{path}' is not a directory."}
    if not os.access(path, os.W_OK):
        return {"valid": False, "error": f"Directory '{path}' is not writeable."}
    return {"valid": True, "error": None}

@app.post("/convert")
async def convert_file(
    file: UploadFile = File(...),
    output_dir: str = Form(...)
):
    if not os.path.exists(output_dir) or not os.path.isdir(output_dir):
        raise HTTPException(status_code=400, detail="Invalid output directory")

    # Create output directory "md" in the target folder
    target_md_dir = os.path.join(output_dir, "md")
    os.makedirs(target_md_dir, exist_ok=True)

    # Extract file extension and name
    orig_filename = file.filename
    base_name, ext = os.path.splitext(orig_filename)

    # Save file to temporary storage to process with markitdown
    suffix = ext.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    try:
        # Convert file to markdown
        result = md.convert(tmp_path)
        markdown_content = result.text_content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MarkItDown error: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Collision prevention logic
    target_filename = f"{base_name}.md"
    target_path = os.path.join(target_md_dir, target_filename)
    counter = 1
    while os.path.exists(target_path):
        target_filename = f"{base_name}_{counter}.md"
        target_path = os.path.join(target_md_dir, target_filename)
        counter += 1

    # Save converted markdown
    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write markdown file: {str(e)}")

    return {
        "filename": orig_filename,
        "saved_path": target_path,
        "markdown": markdown_content,
        "status": "success",
        "error": None
    }
