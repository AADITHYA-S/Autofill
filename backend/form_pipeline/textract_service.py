import boto3
import json
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image


class TextractClient:
    def __init__(self):
        self.client = boto3.client("textract", region_name="us-east-1")

    def analyze_doc(self, input_path: str | Path) -> dict[str, Any]:
        with open(input_path, "rb") as f:
            image_bytes = f.read()

        return self.analyze_bytes(image_bytes)

    def analyze_bytes(self, image_bytes: bytes) -> dict[str, Any]:
        if not image_bytes:
            raise ValueError("Uploaded file is empty")

        response = self.client.analyze_document(
            Document={"Bytes": image_bytes},
            FeatureTypes=["FORMS", "TABLES"],
        )

        for block in response.get("Blocks", []):
            if block.get("BlockType") == "SELECTION_ELEMENT":
                print("\n========== CHECKBOX ==========")
                print("Status:", block.get("SelectionStatus"))
                print("Geometry:", block.get("Geometry"))
                print("==============================")

        return response

    async def extract(self, uploaded_file) -> dict[str, Any]:
        image_bytes = await uploaded_file.read()

        if hasattr(uploaded_file, "seek"):
            await uploaded_file.seek(0)

        return self.analyze_bytes(image_bytes)

    async def extract_pdf(self, uploaded_file) -> list[tuple[Any, dict[str, Any]]]:
        """
        Render each PDF page to a PNG using PyMuPDF, then send each page
        to Textract. Returns (PIL RGB image, Textract response) for each page,
        preserving the existing return format expected by the form pipeline.
        """
        pdf_bytes = await uploaded_file.read()

        if hasattr(uploaded_file, "seek"):
            await uploaded_file.seek(0)

        if not pdf_bytes:
            raise ValueError("Uploaded file is empty")

        results: list[tuple[Any, dict[str, Any]]] = []

        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
                if document.page_count == 0:
                    raise ValueError("Uploaded PDF contains no pages")

                for pdf_page in document:
                    # Render at 2x scale for OCR clarity, without requiring Poppler.
                    pixmap = pdf_page.get_pixmap(
                        matrix=fitz.Matrix(2, 2),
                        alpha=False,
                    )
                    png_bytes = pixmap.tobytes("png")

                    with Image.open(BytesIO(png_bytes)) as image:
                        page_image = image.convert("RGB")

                    response = self.analyze_bytes(png_bytes)
                    results.append((page_image, response))

        except fitz.FileDataError as exc:
            raise ValueError("Uploaded file is not a valid readable PDF") from exc

        return results

    @staticmethod
    def _image_bytes(image: Any) -> bytes:
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def save_response(
        self,
        response: dict[str, Any],
        input_path: str | Path,
        output_folder: str = "textractResponse",
    ) -> Path:
        form_name = Path(input_path).stem
        output_filename = f"textract_{form_name}.json"
        output_path = Path(output_folder) / output_filename

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(response, f, indent=4)

        print(f"Output saved to {output_path}")
        return output_path


if __name__ == "__main__":
    # Usage example for an image file (not a PDF).
    client = TextractClient()
    input_path = "InputImages/doc1.jpeg"
    response = client.analyze_doc(input_path)
    client.save_response(response, input_path)
