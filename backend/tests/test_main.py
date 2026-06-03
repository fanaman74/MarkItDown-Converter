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
        assert res_json["suggested_filename"] == "03-06-26-sender-receiver-this_is_the_body_content_of_the_eml_email_message.md"

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
        assert res_json["suggested_filename"] == "03-06-26-sender-receiver-urgent_project_meeting_agenda.md"

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
        assert res_json["suggested_filename"] == "03-06-26-sender-receiver-le_café_et_le_résumé_de_la_réunion_importante.md"

def test_convert_eml_file_with_thread_and_footers():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # EML with body containing headers, thread quote, and Proton Mail footer
        eml_content = (
            b"From: sender@example.com\n"
            b"To: receiver@example.com\n"
            b"Subject: Meeting Summary\n"
            b"Date: Wed, 3 Jun 2026 11:27:00 +0200\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Hi Nathalie,\n\n"
            b"Can you review this summary of our meeting?\n\n"
            b"Sent with Proton Mail https://proton.me/ secure email.\n\n"
            b"--- Original Message ---\n"
            b"From: receiver@example.com\n"
            b"To: sender@example.com\n"
            b"Let's schedule a meeting next week."
        )
        files = {"file": ("test_thread.eml", eml_content, "message/rfc822")}
        data = {"output_dir": tmp_dir, "rename_eml": "true"}
        response = client.post("/convert", files=files, data=data)
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["status"] == "success"
        # The filename should be generated from 'Can you review this summary of our meeting?'
        # and NOT contain the Proton footer or original message thread.
        assert res_json["suggested_filename"] == "03-06-26-sender-receiver-can_you_review_this_summary_of_our_meeting.md"

def test_convert_eml_file_only_footer_fallback_to_subject():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # EML with body containing only greetings and Proton footer, but has a subject line
        eml_content = (
            b"From: sender@example.com\n"
            b"To: receiver@example.com\n"
            b"Subject: Weekly Status Update\n"
            b"Date: Wed, 3 Jun 2026 11:27:00 +0200\n"
            b"Content-Type: text/plain; charset=utf-8\n\n"
            b"Hi Nathalie,\n\n"
            b"Sent with Proton Mail secure email."
        )
        files = {"file": ("test_only_footer.eml", eml_content, "message/rfc822")}
        data = {"output_dir": tmp_dir, "rename_eml": "true"}
        response = client.post("/convert", files=files, data=data)
        assert response.status_code == 200
        res_json = response.json()
        assert res_json["status"] == "success"
        # The filename should fall back to the subject line 'Weekly Status Update'
        assert res_json["suggested_filename"] == "03-06-26-sender-receiver-weekly_status_update.md"


