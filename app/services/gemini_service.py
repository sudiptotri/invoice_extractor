import google.generativeai as genai
from PIL import Image
from pdf2image import convert_from_bytes
from io import BytesIO
import json
import base64
from typing import Dict, Any
from app.config import settings
import re
import asyncio


class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.0-flash")

    def _convert_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        buffered = BytesIO()
        image.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode()

    def _process_pdf(self, pdf_bytes: bytes) -> Image.Image:
        """Convert first page of PDF to PIL Image"""
        try:
            images = convert_from_bytes(pdf_bytes)
            return images[0] if images else None
        except Exception as e:
            print(f"PDF processing error: {str(e)}")
            raise ValueError("Failed to process PDF file")

    async def process_invoice(self, file_content: bytes, mime_type: str) -> tuple[str, Dict[str, Any]]:
        try:
            # Handle different file types
            if mime_type.startswith("image/"):
                image = Image.open(BytesIO(file_content))
            elif mime_type == "application/pdf":
                image = self._process_pdf(file_content)
            else:
                raise ValueError("Unsupported file type")

            if image.mode != "RGB":
                image = image.convert("RGB")

            # Resize large images
            max_size = 1600
            if image.width > max_size or image.height > max_size:
                ratio = min(max_size / image.width, max_size / image.height)
                new_size = (int(image.width * ratio), int(image.height * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            img_str = self._convert_to_base64(image)

            # 🔍 Detect document type
            first_2kb = file_content[:2048].decode(errors="ignore").lower()
            doc_type = "credit_note" if "credit note" in first_2kb else "invoice"

            # 🧾 Unified prompt
            prompt = f"""Analyze this document image — it could be an INVOICE or a CREDIT NOTE.
Document Type Detected: {doc_type.upper()}.

Extract all possible fields in this exact JSON structure:

{{
  "document_type": "invoice" or "credit_note",
  "vendor": "company name",
  "invoice_number": "reference number if invoice",
  "credit_note_number": "reference number if credit note",
  "date": "YYYY-MM-DD",
  "reason": "reason for credit note, if available",
  "subtotal": numeric_value,
  "tax_details": {{
      "gstin": "tax registration number",
      "cgst_rate": percentage,
      "cgst_amount": numeric_value,
      "sgst_rate": percentage,
      "sgst_amount": numeric_value,
      "igst_rate": percentage,
      "igst_amount": numeric_value,
      "total_tax": numeric_value
  }},
  "total": numeric_value,
  "currency": "INR/USD/EUR",
  "items": [
      {{
          "description": "exact item description",
          "quantity": numeric_value,
          "unit_price": numeric_value,
          "tax_rate": percentage,
          "tax_amount": numeric_value,
          "amount": numeric_value
      }}
  ],
  "confidence_score": 0–100
}}

IMPORTANT RULES:
1. Detect and include the correct document_type field.
2. Include GST details (CGST, SGST, IGST) where applicable.
3. Return valid JSON only — no extra text or code fences.
4. Keep all amounts numeric (no currency symbols).
5. If a field doesn’t exist, set it to null or 0.
6. Calculate total_tax as sum of all tax amounts.
7. Be precise and consistent with numeric values.
"""

            # Call Gemini (non-blocking)
            response = await asyncio.to_thread(
                self.model.generate_content,
                contents=[
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_str}},
                ],
                generation_config={
                    "temperature": 0.1,
                    "top_p": 1,
                    "top_k": 32,
                    "max_output_tokens": 2048,
                },
            )

            if not response or not hasattr(response, "text"):
                raise ValueError("Empty response from Gemini API")

            extracted_text = response.text.strip()
            if not extracted_text:
                raise ValueError("Empty text in response")

            print(f"Raw API response: {extracted_text}")

            # Clean up JSON string
            if "```json" in extracted_text:
                extracted_text = extracted_text.split("```json")[1].split("```")[0].strip()
            elif "```" in extracted_text:
                extracted_text = extracted_text.split("```")[1].strip()

            # Try parsing JSON safely
            try:
                data = json.loads(extracted_text)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", extracted_text, re.DOTALL)
                if match:
                    data = json.loads(match.group())
                else:
                    raise ValueError("Invalid JSON format in Gemini response")

            # Extract tax details
            tax_details = data.get("tax_details", {})
            processed_tax = {
                "gstin": tax_details.get("gstin", ""),
                "cgst_rate": float(tax_details.get("cgst_rate", 0)),
                "cgst_amount": float(tax_details.get("cgst_amount", 0)),
                "sgst_rate": float(tax_details.get("sgst_rate", 0)),
                "sgst_amount": float(tax_details.get("sgst_amount", 0)),
                "igst_rate": float(tax_details.get("igst_rate", 0)),
                "igst_amount": float(tax_details.get("igst_amount", 0)),
                "total_tax": float(tax_details.get("total_tax", 0)),
            }

            # Unified processed output (works for both invoices & credit notes)
            processed_data = {
                "document_type": data.get("document_type", doc_type),
                "vendor": data.get("vendor", ""),
                "invoice_number": data.get("invoice_number", ""),
                "credit_note_number": data.get("credit_note_number", ""),
                "reason": data.get("reason", ""),
                "date": data.get("date", ""),
                "subtotal": float(data.get("subtotal", 0)),
                "tax_details": processed_tax,
                "total": float(data.get("total", 0)),
                "currency": data.get("currency", "INR"),
                "items": [],
                "confidence_score": float(data.get("confidence_score", 95.0)),
            }

            # Handle items safely
            for item in data.get("items", []):
                processed_item = {
                    "description": item.get("description", ""),
                    "quantity": float(item.get("quantity", 0)),
                    "unit_price": float(item.get("unit_price", 0)),
                    "tax_rate": float(item.get("tax_rate", 0)),
                    "tax_amount": float(item.get("tax_amount", 0)),
                    "amount": float(item.get("amount", 0)),
                }
                processed_data["items"].append(processed_item)

            print(f"Processed data: {processed_data}")
            return extracted_text, processed_data

        except Exception as e:
            print(f"Processing Error: {str(e)}")
            raise Exception(f"Failed to process invoice: {str(e)}")
