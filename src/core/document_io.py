"""Document I/O: read PDF/Word, save to Word/text."""

from pathlib import Path


def read_pdf(path: str) -> str:
    from PyPDF2 import PdfReader
    reader = PdfReader(path)
    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text)
    return "\n\n".join(texts)


def read_word(path: str) -> str:
    from docx import Document
    doc = Document(path)
    return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_document(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return read_pdf(path)
    elif ext in (".docx", ".doc"):
        return read_word(path)
    elif ext == ".txt":
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {ext}")


def save_to_word(text: str, path: str):
    from docx import Document
    doc = Document()
    for line in text.split("\n"):
        if line.startswith("## "):
            doc.add_heading(line[3:], level=2)
        elif line.startswith("# "):
            doc.add_heading(line[2:], level=1)
        elif line.startswith("- "):
            doc.add_paragraph(line[2:], style="List Bullet")
        elif line.strip():
            doc.add_paragraph(line)
    doc.save(path)
