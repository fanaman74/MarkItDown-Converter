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
