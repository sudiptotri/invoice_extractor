from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Dict, Optional

class Settings(BaseSettings):
    # Basic application settings
    PROJECT_NAME: str = "Invoice Reader"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # API and authentication
    GOOGLE_API_KEY: str
    
    # File paths and directories
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    STATIC_DIR: Path = BASE_DIR / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    
    # Model settings
    GEMINI_MODEL: str = "gemini-2.5-flash"
    TEMPERATURE: float = 0.1
    MAX_OUTPUT_TOKENS: int = 2048
    
    # File upload settings
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_MIME_TYPES: list = ["image/jpeg", "image/png", "application/pdf"]

    # Invoice field configurations
    INVOICE_FIELDS: Dict = {
        "basic_info": {
            "title": "Basic Information",
            "icon": "document-text",
            "fields": {
                "vendor": {"label": "Vendor Name", "type": "text"},
                "invoice_number": {"label": "Invoice Number", "type": "text"},
                "date": {"label": "Invoice Date", "type": "date"}
            }
        },
        "amounts": {
            "title": "Financial Details",
            "icon": "currency-dollar",
            "fields": {
                "total": {"label": "Total Amount", "type": "currency"},
                "currency": {"label": "Currency", "type": "text"}
            }
        },
        "line_items": {
            "title": "Line Items",
            "icon": "list",
            "fields": {
                "description": {"label": "Description", "type": "text"},
                "quantity": {"label": "Quantity", "type": "number"},
                "unit_price": {"label": "Unit Price", "type": "currency"},
                "amount": {"label": "Amount", "type": "currency"}
            }
        }
    }

    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Ensure required directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.STATIC_DIR.mkdir(parents=True, exist_ok=True)