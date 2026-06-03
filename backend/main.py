import os
import tempfile
import shutil
import email
from email.policy import default
import markdownify
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

def convert_eml_to_markdown(file_path: str) -> str:
    try:
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=default)
        
        headers = []
        for header in ["From", "To", "Cc", "Subject", "Date"]:
            if msg[header]:
                headers.append(f"**{header}:** {msg[header]}")
        
        body = ""
        # Get plain text or html body
        body_part = msg.get_body(preferencelist=('plain', 'html'))
        if body_part:
            content = body_part.get_content()
            if body_part.get_content_type() == 'text/html':
                body = markdownify.markdownify(content)
            else:
                body = content
        else:
            # Walk parts as fallback
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="ignore")
                    break
                elif part.get_content_type() == "text/html":
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="ignore")
                    body = markdownify.markdownify(html)
                    break
        
        markdown_content = "\n".join(headers) + "\n\n" + body
        return markdown_content
    except Exception as e:
        raise ValueError(f"Failed to parse EML file: {str(e)}")

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
    output_dir: str = Form(None)
):
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
        if ext.lower() == ".eml":
            markdown_content = convert_eml_to_markdown(tmp_path)
        else:
            result = md.convert(tmp_path)
            markdown_content = result.text_content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    target_path = None
    if output_dir:
        if not os.path.exists(output_dir) or not os.path.isdir(output_dir):
            raise HTTPException(status_code=400, detail="Invalid output directory")

        # Create output directory "md" in the target folder
        target_md_dir = os.path.join(output_dir, "md")
        os.makedirs(target_md_dir, exist_ok=True)

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
