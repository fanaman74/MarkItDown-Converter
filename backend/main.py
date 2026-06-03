import os
import tempfile
import shutil
import email
from email.policy import default
import re
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

def sanitize_filename(name: str, max_len: int = 100) -> str:
    # Remove any character that is not alphanumeric, space, hyphen, or underscore
    cleaned = re.sub(r'[^\w\s\-]', '', name)
    # Replace spaces and hyphens with single underscores
    cleaned = re.sub(r'[\s\-]+', '_', cleaned.strip())
    # Truncate
    return cleaned[:max_len].lower()

def summarize_body_for_filename(text: str) -> str:
    stop_words = {
        "the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "at", "from",
        "by", "for", "with", "about", "against", "between", "into", "through", "during",
        "before", "after", "above", "below", "to", "of", "in", "on", "is", "are", "was",
        "were", "be", "been", "being", "have", "has", "had", "having", "do", "does",
        "did", "doing", "would", "should", "could", "ought", "i", "you", "he", "she",
        "it", "we", "they", "this", "that", "these", "those", "am", "as", "their",
        "our", "my", "your", "his", "her", "its", "them", "us", "him", "me", "hope", "well",
        "thanks", "regards", "best", "hello", "dear", "hi"
    }
    pleasantry_patterns = [
        re.compile(r'^(hi|hello|dear|hey|good\s+(morning|afternoon|evening))\b', re.IGNORECASE),
        re.compile(r'^how\s+(are|is)\s+(you|things|everything)\b', re.IGNORECASE),
        re.compile(r'^hope\s+you\s+(are|doing)\s+well\b', re.IGNORECASE),
        re.compile(r'^hope\s+this\s+finds\s+you\s+well\b', re.IGNORECASE),
        re.compile(r'^(thanks|thank\s+you|best\s+regards|sincerely|regards)\b', re.IGNORECASE)
    ]
    
    # Split text into lines/paragraphs
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    
    valid_sentences = []
    for line in lines:
        # Split each line into sentences
        sentences = re.split(r'(?<=[.!?])\s+', line)
        for s in sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            # Skip pleasantry sentences
            if any(p.match(s_clean) for p in pleasantry_patterns):
                continue
            # Skip greeting line structures ending with comma/exclamation
            if len(s_clean.split()) <= 4 and (s_clean.endswith(',') or s_clean.endswith('!')):
                if any(word in s_clean.lower() for word in ["hi", "hello", "dear", "hey", "thanks", "regards"]):
                    continue
            # Skip short sentences (less than 4 words)
            if len(s_clean.split()) < 4:
                continue
            valid_sentences.append(s_clean)
            
    if not valid_sentences:
        # Fallback to the first line with content
        for line in lines:
            if line.strip():
                valid_sentences.append(line.strip())
                break
                
    if not valid_sentences:
        return "untitled_email"
        
    # Score sentences based on word frequency of non-stopwords
    all_words = re.findall(r'\b[^\W\d_]{3,}\b', text.lower())
    filtered_words = [w for w in all_words if w not in stop_words]
    freq = {}
    for w in filtered_words:
        freq[w] = freq.get(w, 0) + 1
        
    best_sentence = valid_sentences[0]
    best_score = -1
    for s in valid_sentences:
        words_in_s = re.findall(r'\b[^\W\d_]{3,}\b', s.lower())
        score = sum(freq.get(w, 0) for w in words_in_s if w not in stop_words)
        normalized_score = score / len(words_in_s) if len(words_in_s) > 0 else 0
        if normalized_score > best_score:
            best_score = normalized_score
            best_sentence = s
            
    words = best_sentence.split()
    if len(words) > 15:
        best_sentence = " ".join(words[:15])
    return best_sentence

def convert_eml_to_markdown(file_path: str) -> tuple[str, str]:
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
        
        # Determine suggested filename based on Subject or keywords
        subject = msg["Subject"]
        suggested_name = ""
        if subject and subject.strip():
            # Strip common Re:/Fwd: prefixes
            clean_subject = re.sub(r'^(re|fwd|fw|re\s*\[\d+\]):\s*', '', subject, flags=re.IGNORECASE).strip()
            if clean_subject:
                suggested_name = sanitize_filename(clean_subject)
                
        if not suggested_name:
            suggested_name = sanitize_filename(summarize_body_for_filename(body))
            
        return markdown_content, f"{suggested_name}.md"
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
    output_dir: str = Form(None),
    rename_eml: bool = Form(True)
):
    # Extract file extension and name
    orig_filename = file.filename
    base_name, ext = os.path.splitext(orig_filename)

    # Save file to temporary storage to process with markitdown
    suffix = ext.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        shutil.copyfileobj(file.file, tmp_file)
        tmp_path = tmp_file.name

    suggested_filename = None
    try:
        # Convert file to markdown
        if ext.lower() == ".eml":
            markdown_content, sug_name = convert_eml_to_markdown(tmp_path)
            if rename_eml:
                suggested_filename = sug_name
        else:
            result = md.convert(tmp_path)
            markdown_content = result.text_content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversion error: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Use suggested name or fallback to original
    target_name = suggested_filename if suggested_filename else f"{base_name}.md"

    target_path = None
    if output_dir:
        if not os.path.exists(output_dir) or not os.path.isdir(output_dir):
            raise HTTPException(status_code=400, detail="Invalid output directory")

        # Create output directory "md" or custom target
        target_md_dir = os.path.join(output_dir, "md")
        os.makedirs(target_md_dir, exist_ok=True)

        # Collision prevention logic
        clean_base, clean_ext = os.path.splitext(target_name)
        target_path = os.path.join(target_md_dir, target_name)
        counter = 1
        while os.path.exists(target_path):
            target_path = os.path.join(target_md_dir, f"{clean_base}_{counter}{clean_ext}")
            counter += 1

        # Save converted markdown
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to write markdown file: {str(e)}")

    return {
        "filename": orig_filename,
        "suggested_filename": suggested_filename,
        "saved_path": target_path,
        "markdown": markdown_content,
        "status": "success",
        "error": None
    }
