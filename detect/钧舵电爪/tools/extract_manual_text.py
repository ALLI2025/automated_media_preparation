#!/usr/bin/env python3
import sys
from pathlib import Path

def extract_pdf_text(pdf_path: Path) -> str:
    # 1) pdfminer
    try:
        from pdfminer.high_level import extract_text
        txt = extract_text(str(pdf_path))
        if txt and txt.strip():
            return txt
    except Exception:
        pass
    # 2) PyPDF
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        txt = "\n".join(page.extract_text() or "" for page in reader.pages)
        if txt and txt.strip():
            return txt
    except Exception:
        pass
    # 3) PyMuPDF (fitz)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_path))
        parts = []
        for page in doc:
            parts.append(page.get_text("text"))
        txt = "\n".join(parts)
        if txt and txt.strip():
            return txt
    except Exception:
        pass
    return ""

def main():
    root = Path(__file__).resolve().parent.parent
    pdf = root / "JODELL钧舵ERG32-150系列旋转电伺服电动夹爪通用详细说明书V1.5.pdf"
    if not pdf.exists():
        print(f"❌ 找不到说明书文件: {pdf}")
        sys.exit(1)

    print(f"🔎 提取文本: {pdf}")
    text = extract_pdf_text(pdf)
    out = root / "manual_text.txt"
    out.write_text(text or "", encoding="utf-8")
    print(f"✅ 已生成: {out} (长度 {len(text)})")

if __name__ == "__main__":
    main()