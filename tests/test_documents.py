"""Unit tests for document signature validation and ICAP fail-closed behavior."""
import pytest

from itoms.services.documents import detect_file_type, parse_icap_verdict


def test_file_type_detection_uses_content_signatures():
    assert detect_file_type("report.pdf", b"%PDF-1.7 test") == ("pdf", "application/pdf")
    assert detect_file_type("report.pdf", b"<html>not a pdf</html>") is None
    assert detect_file_type("image.png", b"\x89PNG\r\n\x1a\ncontent") == ("png", "image/png")
    assert detect_file_type("payload.exe", b"MZ\x90\x00") is None


def test_office_file_requires_expected_container_members():
    import zipfile
    from io import BytesIO
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    assert detect_file_type("document.docx", buffer.getvalue()) == (
        "docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_icap_verdict_fails_closed():
    assert parse_icap_verdict(b"ICAP/1.0 204 No Content\r\n\r\n") [0] == "CLEAN"
    assert parse_icap_verdict(b"ICAP/1.0 200 OK\r\n\r\n") [0] == "INFECTED"
    assert parse_icap_verdict(b"HTTP/1.1 200 OK\r\n\r\n") [0] == "ERROR"
