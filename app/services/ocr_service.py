import google.generativeai as genai
from PIL import Image
from io import BytesIO
from app.models import OcrResult
from app.config import settings

class OcrService:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel('gemini-pro-vision')

    @staticmethod
    async def extract_text(file_bytes: bytes) -> OcrResult:
        try:
            # Initialize Gemini
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            model = genai.GenerativeModel('gemini-pro-vision')
            
            # Convert bytes to PIL Image
            image = Image.open(BytesIO(file_bytes))
            
            # Create prompt for OCR
            prompt = """
            Act as an OCR engine. Look at this invoice image carefully and extract all the text content.
            Return only the extracted text, maintaining the layout and structure as much as possible.
            Include all numbers, dates, amounts, and text content visible in the image.
            """

            # Generate response from Gemini
            response = model.generate_content([prompt, image])
            extracted_text = response.text

            return OcrResult(
                text=extracted_text,
                confidence=0.95  # Gemini doesn't provide confidence scores, using default high value
            )

        except Exception as e:
            print(f"OCR Error: {str(e)}")
            raise Exception(f"Failed to perform OCR: {str(e)}")