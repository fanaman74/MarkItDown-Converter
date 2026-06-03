# MarkItDown-Converter

A local desktop web utility designed to recursively parse documents (`.pdf`, `.docx`, `.msg`, `.eml`) in any directory and convert them to Markdown. It utilizes Microsoft's **MarkItDown** library on a Python FastAPI backend and provides a modern, interactive React + Vite frontend with Tailwind CSS.

---

## Features
*   **Recursive Directory Scanning**: Scans any selected local folder for supported file formats.
*   **Directory Structure Replication**: Replicates the original nested subfolder structures inside the output directory.
*   **Output Location Strategies**:
    *   **In-Place**: Generates an `md/` folder inside the source directory.
    *   **Custom Destination**: Replicates the structure inside `md_convert/` at any other location selected on your local disk.
*   **Queue-Based Processing**: Processes files sequentially, featuring start/cancel batch commands, progress tracking, and failure explanation with individual file retry capabilities.
*   **Real-time Output Preview**: An interactive sidebar showing file conversion status and full Markdown previews (with clipboard copy).
*   **Custom EML parsing**: Integrated custom HTML-to-Markdown email parsing using Python's standard `email` package and `markdownify` for reliable `.eml` conversions.

---

## Tech Stack
*   **Backend**: Python FastAPI, Uvicorn, python-multipart, markitdown, markdownify, pytest, httpx.
*   **Frontend**: React (Vite), Tailwind CSS v4.

---

## Installation & Setup

### 1. Prerequisite
Ensure you have **Python 3.10+** (tested up to Python 3.14) and **Node.js** installed on your machine.

### 2. Backend Installation
```bash
# Setup virtual environment
python3 -m venv backend/venv
backend/venv/bin/pip install -r backend/requirements.txt
```

### 3. Frontend Installation
```bash
# Install npm packages
cd frontend
npm install
```

---

## Running the Application

Start both the backend and frontend dev servers concurrently:

### 1. Launch Backend
```bash
backend/venv/bin/uvicorn backend.main:app --reload --port 8000
```

### 2. Launch Frontend
```bash
cd frontend
npm run dev
```

Open your browser and navigate to: **`http://localhost:5180`**
