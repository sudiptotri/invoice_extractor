from pydantic import BaseModel
from typing import List, Optional

class LineItem(BaseModel):
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: float

class InvoiceData(BaseModel):
    vendor: Optional[str] = None
    invoice_number: Optional[str] = None
    date: Optional[str] = None
    total: Optional[float] = None
    currency: Optional[str] = None
    line_items: List[LineItem] = []

class OcrResult(BaseModel):
    text: str
    confidence: float