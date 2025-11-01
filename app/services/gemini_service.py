# app/services/gemini_service.py

import google.generativeai as genai
from PIL import Image
from pdf2image import convert_from_bytes
from io import BytesIO
import json
import base64
from typing import Dict, Any
from app.config import settings

class GeminiService:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.0-flash')

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
            if mime_type.startswith('image/'):
                image = Image.open(BytesIO(file_content))
            elif mime_type == 'application/pdf':
                image = self._process_pdf(file_content)
            else:
                raise ValueError("Unsupported file type")

            # Convert to RGB if needed
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            # Resize image if too large (max 1600x1600)
            max_size = 1600
            if image.width > max_size or image.height > max_size:
                ratio = min(max_size/image.width, max_size/image.height)
                new_size = (int(image.width * ratio), int(image.height * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)

            # Convert to base64
            img_str = self._convert_to_base64(image)

            # Create prompt for the model
            prompt = """Analyze this invoice image and extract information in this exact JSON format. Be precise and accurate:
            {
                "vendor": "company name",
                "invoice_number": "reference number",
                "date": "YYYY-MM-DD",
                "subtotal": numeric_value,
                "tax_details": {
                    "gstin": "tax registration number",
                    "cgst_rate": percentage,
                    "cgst_amount": numeric_value,
                    "sgst_rate": percentage,
                    "sgst_amount": numeric_value,
                    "igst_rate": percentage,
                    "igst_amount": numeric_value,
                    "total_tax": numeric_value
                },
                "total": numeric_value,
                "currency": "USD/EUR/etc",
                "items": [
                    {
                        "description": "exact item description",
                        "quantity": numeric_value,
                        "unit_price": numeric_value,
                        "tax_rate": percentage,
                        "tax_amount": numeric_value,
                        "amount": numeric_value
                    }
                ]
            }

            IMPORTANT RULES:
            1. Extract ALL line items with exact descriptions
            2. Keep amounts as numeric values only (no currency symbols)
            3. Return valid JSON only, no additional text
            4. For Indian invoices, extract GST details (CGST, SGST, IGST)
            5. Calculate tax amounts if not explicitly shown
            6. If tax details are not found, set rates to 0 and amounts to 0
            7. Calculate total_tax as sum of all tax amounts"""

            # Generate response
            try:
                response = self.model.generate_content(
                    contents=[
                        {"text": prompt},
                        {"inline_data": {
                            "mime_type": "image/jpeg",
                            "data": img_str
                        }}
                    ],
                    generation_config={
                        "temperature": 0.1,
                        "top_p": 1,
                        "top_k": 32,
                        "max_output_tokens": 2048,
                    }
                )
                
                if not response or not hasattr(response, 'text'):
                    print("Error: Empty response from Gemini API")
                    raise ValueError("Empty response from Gemini API")

                extracted_text = response.text.strip()
                
                if not extracted_text:
                    print("Error: Empty text in response")
                    raise ValueError("Empty text in response")
                    
                print(f"Raw API response: {extracted_text}")  # Debug log
                
            except Exception as api_error:
                print(f"Gemini API Error: {str(api_error)}")
                raise ValueError(f"Gemini API Error: {str(api_error)}")

            # Clean up JSON string
            if "```json" in extracted_text:
                extracted_text = extracted_text.split("```json")[1].split("```")[0].strip()
            elif "```" in extracted_text:
                extracted_text = extracted_text.split("```")[1].strip()

            try:
                data = json.loads(extracted_text)
                
                # Process tax details
                tax_details = data.get("tax_details", {})
                processed_tax = {
                    "gstin": tax_details.get("gstin", ""),
                    "cgst_rate": float(tax_details.get("cgst_rate", 0)),
                    "cgst_amount": float(tax_details.get("cgst_amount", 0)),
                    "sgst_rate": float(tax_details.get("sgst_rate", 0)),
                    "sgst_amount": float(tax_details.get("sgst_amount", 0)),
                    "igst_rate": float(tax_details.get("igst_rate", 0)),
                    "igst_amount": float(tax_details.get("igst_amount", 0)),
                    "total_tax": float(tax_details.get("total_tax", 0))
                }

                processed_data = {
                    "vendor": data.get("vendor", ""),
                    "invoice_number": data.get("invoice_number", ""),
                    "date": data.get("date", ""),
                    "subtotal": float(data.get("subtotal", 0)),
                    "tax_details": processed_tax,
                    "total": float(data.get("total", 0)),
                    "currency": data.get("currency", "INR"),
                    "items": []
                }

                # Process line items with proper structure
                for item in data.get("items", []):
                    processed_item = {
                        "description": item.get("description", ""),
                        "quantity": float(item.get("quantity", 0)),
                        "unit_price": float(item.get("unit_price", 0)),
                        "tax_rate": float(item.get("tax_rate", 0)),
                        "tax_amount": float(item.get("tax_amount", 0)),
                        "amount": float(item.get("amount", 0))
                    }
                    processed_data["items"].append(processed_item)                # Add confidence score
                processed_data["confidence_score"] = 95.0  # Default confidence

                print(f"Processed data: {processed_data}")  # Debug log
                return extracted_text, processed_data

            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {str(e)}")
                # Return minimal valid data
                return extracted_text, {
                    "vendor": "",
                    "invoice_number": "",
                    "date": "",
                    "total": 0.0,
                    "currency": "USD",
                    "items": [],
                    "confidence_score": 0.0
                }

        except Exception as e:
            print(f"Processing Error: {str(e)}")
            raise Exception(f"Failed to process invoice: {str(e)}")