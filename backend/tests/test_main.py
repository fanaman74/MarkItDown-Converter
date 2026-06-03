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

def test_convert_eml_file():
    with tempfile.TemporaryDirectory() as tmp_dir:
        eml_content = (
            b"From: sender@example.com\n"
            b"To: receiver@example.com\n"
            b"Subject: Test Subject EML\n"
            b"Date: Wed, 3 Jun 2026 11:27:00 +0200\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"This is the body content of the EML email message."
        )
        files = {"file": ("test_email.eml", eml_content, "message/rfc822")}
        data = {"output_dir": tmp_dir, "rename_eml": "true"}
        response = client.post("/convert", files=files, data=data)
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["status"] == "success"
        assert "**Subject:** Test Subject EML" in res_json["markdown"]
        assert "This is the body content of the EML" in res_json["markdown"]
        assert res_json["suggested_filename"] == "test_subject_eml.md"

def test_convert_eml_file_no_subject():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # EML with no subject
        eml_content = (
            b"From: sender@example.com\n"
            b"To: receiver@example.com\n"
            b"Date: Wed, 3 Jun 2026 11:27:00 +0200\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Urgent project meeting agenda! We need to discuss billing and deployment schedule."
        )
        files = {"file": ("test_no_subject.eml", eml_content, "message/rfc822")}
        data = {"output_dir": tmp_dir, "rename_eml": "true"}
        response = client.post("/convert", files=files, data=data)
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["status"] == "success"
        # Should extract keywords like: project, meeting, agenda, billing, deployment, etc.
        suggested = res_json["suggested_filename"]
        assert suggested.endswith(".md")
        # Check that it extracted words of length >= 3 and not stopwords
        assert "project" in suggested or "meeting" in suggested or "agenda" in suggested

def test_convert_eml_file_unicode_no_subject():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # EML with no subject, but with French accented content
        eml_content = (
            b"From: sender@example.com\n"
            b"To: receiver@example.com\n"
            b"Date: Wed, 3 Jun 2026 11:27:00 +0200\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Le caf\xc3\xa9 et le r\xc3\xa9sum\xc3\xa9 de la r\xc3\xa9union importante."
        )
        files = {"file": ("test_french.eml", eml_content, "message/rfc822")}
        data = {"output_dir": tmp_dir, "rename_eml": "true"}
        response = client.post("/convert", files=files, data=data)
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["status"] == "success"
        suggested = res_json["suggested_filename"]
        assert suggested.endswith(".md")
        # Should extract 'café' and 'résumé' and 'réunion'
        assert "café" in suggested or "résumé" in suggested or "réunion" in suggested


