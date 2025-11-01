from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pathlib import Path
import time
from datetime import datetime

from app.services.gemini_service import GeminiService
from app.models.schemas import ProcessResponse
from app.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent.parent / "static")), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request, 
            "title": settings.PROJECT_NAME,
            "fields": settings.INVOICE_FIELDS,
            "version": settings.VERSION
        }
    )

@app.post("/api/v1/process")
async def process_invoice(file: UploadFile = File(...)):
    if file.content_type not in settings.ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400, 
            detail=f"Only {', '.join(settings.ALLOWED_MIME_TYPES)} files are supported"
        )
    
    try:
        start_time = time.time()
        contents = await file.read()
        
        if len(contents) > settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum limit of {settings.MAX_UPLOAD_SIZE / (1024 * 1024)}MB"
            )

        service = GeminiService()
        extracted_text, extracted_data = await service.process_invoice(
            contents, 
            file.content_type
        )

        processing_time = round(time.time() - start_time, 2)
        
        # Structure the response data
        # Flatten the data structure for frontend
        response_data = {
            "success": True,
            "extracted_text": extracted_text,
            "parsed_data": {
                "basic_info": {
                    "vendor": extracted_data["vendor"],
                    "invoice_number": extracted_data["invoice_number"],
                    "date": extracted_data["date"]
                },
                "amounts": {
                    "subtotal": extracted_data.get("subtotal", 0),
                    "total": extracted_data["total"],
                    "currency": extracted_data["currency"]
                },
                "tax_info": {
                    "gstin": extracted_data.get("tax_details", {}).get("gstin", ""),
                    "tax_details": [
                        {
                            "type": "CGST",
                            "rate": extracted_data.get("tax_details", {}).get("cgst_rate", 0),
                            "amount": extracted_data.get("tax_details", {}).get("cgst_amount", 0)
                        },
                        {
                            "type": "SGST",
                            "rate": extracted_data.get("tax_details", {}).get("sgst_rate", 0),
                            "amount": extracted_data.get("tax_details", {}).get("sgst_amount", 0)
                        },
                        {
                            "type": "IGST",
                            "rate": extracted_data.get("tax_details", {}).get("igst_rate", 0),
                            "amount": extracted_data.get("tax_details", {}).get("igst_amount", 0)
                        }
                    ],
                    "total_tax": extracted_data.get("tax_details", {}).get("total_tax", 0)
                },
                "items": extracted_data["items"],
                "metadata": {
                    "confidence_score": extracted_data.get("confidence_score", 95.0),
                    "processing_time": processing_time
                }
            }
        }
        print("Response data:", response_data)  # Debug log
        
        return JSONResponse(content=response_data)
    
    except HTTPException as he:
        raise he
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )

# Add health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "timestamp": datetime.now().isoformat()
    }