# Local Folder to Markdown Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web application allowing users to select a folder, enter its local absolute path, convert PDF/DOCX/MSG/EML files to Markdown using Microsoft's MarkItDown, and save them automatically in an `md` subfolder.

**Architecture:** A Python FastAPI backend running locally processes files uploaded one-by-one by a React frontend. The backend validates paths and saves converted markdown directly to the target folder, preventing naming collisions. The frontend displays real-time progress, a file list queue, and an interactive markdown preview drawer.

**Tech Stack:** FastAPI, Uvicorn, python-multipart, markitdown[all], pytest, React, Vite, Tailwind CSS.

---

## User Review Required

> [!IMPORTANT]
> The application requires running two separate local servers concurrently:
> 1. FastAPI Backend: `uvicorn main:app --reload --port 8000` (run in `backend/` directory)
> 2. Vite Frontend: `npm run dev` (run in `frontend/` directory, accessible at `http://localhost:5173`)
>
> The user must provide the absolute directory path in the frontend input text field so the local backend knows where to write the `md` output folder.

## Open Questions

None. The user has selected the directory input approach with automatic nested `md` folder creation, file-by-file queue processing, and output flattening with suffix collision resolution.

---

## Proposed Changes

### Backend Component (Python FastAPI)

#### [NEW] [requirements.txt](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/backend/requirements.txt)
Python backend requirements.

#### [NEW] [main.py](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/backend/main.py)
The primary FastAPI server script containing routes for validation and file conversion.

#### [NEW] [test_main.py](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/backend/tests/test_main.py)
Test suite for checking path validation, markdown conversion, and filename collision prevention.

---

### Frontend Component (React + Vite + Tailwind)

#### [NEW] [tailwind.config.js](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/frontend/tailwind.config.js)
Tailwind configuration for custom dark-neutral colors, Outfit/Inter typography, and glassmorphic designs.

#### [NEW] [App.jsx](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/frontend/src/App.jsx)
Main frontend application containing file picker dropzone, path validation, progress queue, and preview drawer.

---

## Task Breakdown

### Task 1: Backend Setup and Environment
* **Files**:
  * Create: [requirements.txt](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/backend/requirements.txt)
* [ ] **Step 1: Create requirements.txt**
  Create `backend/requirements.txt` with dependencies:
  ```
  fastapi==0.111.0
  uvicorn==0.30.1
  python-multipart==0.0.9
  markitdown==0.0.1a4
  pytest==8.2.2
  httpx==0.27.0
  ```
* [ ] **Step 2: Initialize python virtual environment**
  Run commands to create the environment in `backend/venv` and install requirements:
  ```bash
  python3 -m venv backend/venv
  backend/venv/bin/pip install -r backend/requirements.txt
  ```
* [ ] **Step 3: Verify installation**
  Run: `backend/venv/bin/python -c "import fastapi, markitdown; print('Success')"`
  Expected: Output `Success`
* [ ] **Step 4: Commit**
  ```bash
  git add backend/requirements.txt
  git commit -m "chore: backend setup with requirements.txt"
  ```

---

### Task 2: Implement FastAPI App & Path Validation
* **Files**:
  * Create: [main.py](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/backend/main.py)
* [ ] **Step 1: Create main.py with base configuration and CORS**
  Write the initial FastAPI code with CORS allowed from `http://localhost:5173` and `/validate-path` endpoint:
  ```python
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
  ```
* [ ] **Step 2: Commit**
  ```bash
  git add backend/main.py
  git commit -m "feat: add base fastapi server with validate-path endpoint"
  ```

---

### Task 3: Implement MarkItDown Conversion Backend Logic
* **Files**:
  * Modify: [main.py](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/backend/main.py)
* [ ] **Step 1: Add MarkItDown import and /convert endpoint to main.py**
  Add full `/convert` endpoint implementation:
  ```python
  # Add imports at top
  import tempfile
  import shutil
  from fastapi import UploadFile, File
  from markitdown import MarkItDown

  # Initialize MarkItDown once
  md = MarkItDown()

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
  ```
* [ ] **Step 2: Commit**
  ```bash
  git add backend/main.py
  git commit -m "feat: add single file conversion endpoint with collision prevention"
  ```

---

### Task 4: Write Backend Tests and Verify
* **Files**:
  * Create: [test_main.py](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/backend/tests/test_main.py)
* [ ] **Step 1: Write test_main.py checking endpoints**
  Create `backend/tests/test_main.py` with test cases:
  ```python
  import os
  import tempfile
  from fastapi.testclient import TestClient
  from backend.main import app

  client = TestClient(app)

  def test_validate_path():
      with tempfile.TemporaryDirectory() as tmp_dir:
          # Valid path
          response = client.post("/validate-path", data={"path": tmp_dir})
          assert response.status_code == 200
          assert response.json()["valid"] is True

          # Invalid path
          response = client.post("/validate-path", data={"path": "/nonexistent/path/here"})
          assert response.status_code == 200
          assert response.json()["valid"] is False

  def test_convert_txt_file():
      with tempfile.TemporaryDirectory() as tmp_dir:
          file_content = b"Hello, this is a test document."
          files = {"file": ("test.txt", file_content, "text/plain")}
          data = {"output_dir": tmp_dir}
          response = client.post("/convert", files=files, data=data)
          assert response.status_code == 200
          res_json = response.json()
          assert res_json["status"] == "success"
          assert "test.txt" in res_json["filename"]
          assert "Hello, this is a test document." in res_json["markdown"]
          
          # Check file saved on disk
          saved_file = res_json["saved_path"]
          assert os.path.exists(saved_file)
          with open(saved_file, "r") as f:
              assert f.read() == res_json["markdown"]

          # Re-upload duplicate file to check collision prevention
          files2 = {"file": ("test.txt", file_content, "text/plain")}
          response2 = client.post("/convert", files=files2, data=data)
          assert response2.status_code == 200
          assert response2.json()["saved_path"].endswith("test_1.md")
  ```
* [ ] **Step 2: Run pytest**
  Run: `backend/venv/bin/pytest backend/tests/test_main.py -v`
  Expected: 2 passing tests
* [ ] **Step 3: Commit**
  ```bash
  git add backend/tests/test_main.py
  git commit -m "test: add integration tests for path validation and conversion"
  ```

---

### Task 5: Initialize React Frontend
* **Files**:
  * Create: [frontend/package.json](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/frontend/package.json) (via Vite scaffold)
* [ ] **Step 1: Check vite options using --help**
  Run command:
  ```bash
  npx -y create-vite@latest --help
  ```
* [ ] **Step 2: Scaffold Vite App**
  Run command:
  ```bash
  npx -y create-vite@latest frontend --template react
  ```
* [ ] **Step 3: Install tailwindcss dependencies**
  Run command:
  ```bash
  cd frontend && npm install && npm install -D tailwindcss postcss autoprefixer
  ```
* [ ] **Step 4: Initialize Tailwind**
  Run command:
  ```bash
  cd frontend && npx tailwindcss init -p
  ```
* [ ] **Step 5: Setup tailwind.config.js**
  Write configuration in `frontend/tailwind.config.js` to enable styling for all src files:
  ```javascript
  /** @type {import('tailwindcss').Config} */
  export default {
    content: [
      "./index.html",
      "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
      extend: {
        fontFamily: {
          sans: ['Inter', 'Outfit', 'sans-serif'],
        },
      },
    },
    plugins: [],
  }
  ```
* [ ] **Step 6: Update index.css**
  Write standard Tailwind directives in `frontend/src/index.css`:
  ```css
  @tailwind base;
  @tailwind components;
  @tailwind utilities;

  body {
    background-color: #0f172a;
    color: #f8fafc;
    margin: 0;
    font-family: 'Inter', sans-serif;
  }
  ```
* [ ] **Step 7: Commit**
  ```bash
  git add frontend/
  git commit -m "chore: scaffold react frontend and configure tailwind"
  ```

---

### Task 6: Implement Path Configuration & Debounced Path Validation
* **Files**:
  * Modify: [App.jsx](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/frontend/src/App.jsx)
* [ ] **Step 1: Implement base Layout and Directory configuration in App.jsx**
  Write React structure in `frontend/src/App.jsx` with target path validation:
  ```jsx
  import React, { useState, useEffect } from 'react';

  export default function App() {
    const [targetPath, setTargetPath] = useState('');
    const [pathValid, setPathValid] = useState(null); // null, true, false
    const [pathError, setPathError] = useState('');

    useEffect(() => {
      if (!targetPath) {
        setPathValid(null);
        setPathError('');
        return;
      }
      const delayDebounceFn = setTimeout(async () => {
        try {
          const formData = new FormData();
          formData.append('path', targetPath);
          const res = await fetch('http://localhost:8000/validate-path', {
            method: 'POST',
            body: formData,
          });
          const data = await res.json();
          if (data.valid) {
            setPathValid(true);
            setPathError('');
          } else {
            setPathValid(false);
            setPathError(data.error);
          }
        } catch (err) {
          setPathValid(false);
          setPathError('Could not connect to FastAPI server. Ensure backend is running.');
        }
      }, 500);

      return () => clearTimeout(delayDebounceFn);
    }, [targetPath]);

    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center p-6 font-sans">
        <header className="w-full max-w-5xl mb-8 text-center md:text-left flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-extrabold bg-gradient-to-r from-violet-400 via-indigo-300 to-cyan-400 bg-clip-text text-transparent">
              Folder to Markdown Converter
            </h1>
            <p className="text-slate-400 mt-1">Convert folder documents locally with Microsoft MarkItDown</p>
          </div>
        </header>

        <main className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="flex flex-col gap-6">
            {/* Config Panel */}
            <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-6 shadow-xl">
              <h2 className="text-xl font-bold mb-4 text-violet-300">1. Setup Local Target</h2>
              <div className="flex flex-col gap-2">
                <label className="text-sm font-semibold text-slate-300">Local Absolute Folder Path</label>
                <input
                  type="text"
                  placeholder="/Users/fred/Documents/my_docs"
                  value={targetPath}
                  onChange={(e) => setTargetPath(e.target.value)}
                  className="bg-slate-950 border border-slate-800 focus:border-violet-500 focus:ring-1 focus:ring-violet-500 rounded-lg px-4 py-2.5 text-sm text-slate-200 outline-none transition"
                />
                {pathValid === true && (
                  <span className="text-xs text-green-400 font-medium">✓ Valid and writable path</span>
                )}
                {pathValid === false && (
                  <span className="text-xs text-red-400 font-medium">✗ {pathError}</span>
                )}
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }
  ```
* [ ] **Step 2: Commit**
  ```bash
  git add frontend/src/App.jsx
  git commit -m "feat: add layout and absolute path input with debounced validation"
  ```

---

### Task 7: Implement Folder Dropzone and Local File Filtering
* **Files**:
  * Modify: [App.jsx](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/frontend/src/App.jsx)
* [ ] **Step 1: Update App.jsx with drag and drop input and filtered queue list**
  Replace components in `frontend/src/App.jsx` to render folder select input and list pending conversions:
  ```jsx
  // Add state hooks
  const [queue, setQueue] = useState([]);
  
  // File filtering logic
  const handleFolderSelect = (event) => {
    const files = Array.from(event.target.files);
    const allowedExts = ['.pdf', '.docx', '.msg', '.eml'];
    const filtered = files
      .filter(f => allowedExts.some(ext => f.name.toLowerCase().endsWith(ext)))
      .map(f => ({
        file: f,
        status: 'pending', // 'pending' | 'processing' | 'success' | 'error'
        markdown: '',
        savedPath: '',
        errorMsg: '',
      }));
    setQueue(filtered);
  };
  ```
  Provide the dropzone rendering JSX:
  ```jsx
  {/* Drag and Drop Zone */}
  <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-6 shadow-xl flex flex-col gap-4">
    <h2 className="text-xl font-bold text-violet-300">2. Select Local Folder</h2>
    <div className="relative border-2 border-dashed border-slate-700/60 hover:border-violet-500 rounded-xl p-8 flex flex-col items-center justify-center cursor-pointer hover:bg-slate-900/40 transition">
      <input
        type="file"
        webkitdirectory="true"
        directory="true"
        multiple
        onChange={handleFolderSelect}
        className="absolute inset-0 opacity-0 cursor-pointer"
      />
      <div className="text-center">
        <p className="text-base font-semibold text-slate-300">Click or drag folder here</p>
        <p className="text-xs text-slate-500 mt-1">Converts PDF, DOCX, MSG, and EML documents</p>
      </div>
    </div>
  </div>
  ```
* [ ] **Step 2: Commit**
  ```bash
  git add frontend/src/App.jsx
  git commit -m "feat: add folder select input and file filtering"
  ```

---

### Task 8: Implement Concurrency-controlled Upload Queue
* **Files**:
  * Modify: [App.jsx](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/frontend/src/App.jsx)
* [ ] **Step 1: Implement queue processing logic in App.jsx**
  Write state-controlled file submission logic in `frontend/src/App.jsx` with start/cancel features:
  ```jsx
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);

  const startConversion = async () => {
    if (queue.length === 0 || !pathValid) return;
    setIsProcessing(true);
    setCurrentIndex(0);

    const activeQueue = [...queue];

    for (let i = 0; i < activeQueue.length; i++) {
      if (!isProcessing && i > 0) {
        // Let's implement active cancel support checking state ref or local variable
      }
      
      // Update item status to processing
      activeQueue[i].status = 'processing';
      setQueue([...activeQueue]);

      try {
        const formData = new FormData();
        formData.append('file', activeQueue[i].file);
        formData.append('output_dir', targetPath);

        const response = await fetch('http://localhost:8000/convert', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed during conversion');
        }

        const data = await response.json();
        activeQueue[i].status = 'success';
        activeQueue[i].markdown = data.markdown;
        activeQueue[i].savedPath = data.saved_path;
      } catch (err) {
        activeQueue[i].status = 'error';
        activeQueue[i].errorMsg = err.message;
      }

      setCurrentIndex(i + 1);
      setQueue([...activeQueue]);
    }
    setIsProcessing(false);
  };
  ```
  Provide layout styling with progress bar:
  ```jsx
  {/* Progress Bar & Actions */}
  {queue.length > 0 && (
    <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-6 shadow-xl">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-bold text-slate-200">Processing Progress</h3>
          <span className="text-xs text-slate-400">
            {currentIndex} of {queue.length} files converted
          </span>
        </div>
        <button
          onClick={startConversion}
          disabled={isProcessing || !pathValid}
          className="px-4 py-2 bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm font-bold shadow-lg shadow-indigo-500/20 transition"
        >
          {isProcessing ? 'Converting...' : 'Start Conversion'}
        </button>
      </div>

      <div className="w-full bg-slate-950 rounded-full h-2">
        <div
          className="bg-gradient-to-r from-violet-500 to-indigo-500 h-2 rounded-full transition-all duration-300"
          style={{ width: `${(currentIndex / queue.length) * 100}%` }}
        />
      </div>
    </div>
  )}
  ```
* [ ] **Step 2: Commit**
  ```bash
  git add frontend/src/App.jsx
  git commit -m "feat: implement conversion loop with progress indicators"
  ```

---

### Task 9: Implement File Preview Panel Drawer
* **Files**:
  * Modify: [App.jsx](file:///Users/fred/Documents/VibeCoding/antigravity/mdconverter/frontend/src/App.jsx)
* [ ] **Step 1: Write interactive Preview Panel drawer**
  Implement details panel inside `App.jsx` showing the selected file's title, output location, raw markdown text container, and clipboard copying controls:
  ```jsx
  const [selectedFile, setSelectedFile] = useState(null);

  // JSX to select files from the list:
  // onClick={() => setSelectedFile(item)}
  
  // Preview panel layout:
  {selectedFile && (
    <div className="bg-slate-900/60 border border-slate-800/80 backdrop-blur-xl rounded-2xl p-6 shadow-xl flex flex-col max-h-[80vh]">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
        <div>
          <h3 className="font-bold text-slate-200 max-w-[200px] truncate">{selectedFile.file.name}</h3>
          <p className="text-xs text-slate-400">Path: {selectedFile.savedPath || 'Not saved'}</p>
        </div>
        <button
          onClick={() => navigator.clipboard.writeText(selectedFile.markdown)}
          className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold rounded-lg transition"
        >
          Copy Markdown
        </button>
      </div>
      <div className="overflow-y-auto bg-slate-950/80 border border-slate-800 rounded-xl p-4 flex-1">
        {selectedFile.status === 'success' ? (
          <pre className="text-xs text-slate-300 font-mono whitespace-pre-wrap">{selectedFile.markdown}</pre>
        ) : (
          <p className="text-sm text-red-400 font-medium">Failed conversion: {selectedFile.errorMsg}</p>
        )}
      </div>
    </div>
  )}
  ```
* [ ] **Step 2: Commit**
  ```bash
  git add frontend/src/App.jsx
  git commit -m "feat: add interactive file preview panel drawer with clipboard integration"
  ```

---

### Task 10: Manual Verification & Cleanup
* [ ] **Step 1: Verify full run concurrently**
  Startup uvicorn and vite:
  Backend: `backend/venv/bin/uvicorn backend.main:app --reload --port 8000`
  Frontend: `cd frontend && npm run dev`
* [ ] **Step 2: Run conversion checks**
  Check that the folder selects correctly, lists PDFs, converts files, saves to `md/`, and previews markdown text.
* [ ] **Step 3: Commit final layout changes**
  ```bash
  git commit -am "chore: finalize configuration settings and styling polish"
  ```

---

## Verification Plan

### Automated Tests
* Run `pytest backend/tests/test_main.py -v` to check validation of path folders, parsing text files, and suffix duplicate resolving.

### Manual Verification
1. Launch `uvicorn backend.main:app --reload --port 8000` and `npm run dev` in the React frontend.
2. Select a test folder via the picker. Verify file matching filters (.pdf, .docx, .msg, .eml).
3. Confirm validation updates automatically for absolute path folder inputs.
4. Execute batch conversions and check that files are written locally to the nested `md` folder on disk.
5. Click list queue items to inspect Markdown contents inside the previewer drawer.
