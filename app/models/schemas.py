from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

class LineItem(BaseModel):
    description: str = Field(
        ..., 
        description="Item description or name, can contain multiple lines"
    )
    quantity: float = Field(
        default=1.0, 
        description="Quantity of items",
        ge=0  # Ensure quantity is not negative
    )
    unit_price: float = Field(
        ...,  # Make unit_price required
        description="Price per unit",
        ge=0  # Ensure price is not negative
    )
    amount: float = Field(
        ..., 
        description="Total amount for this line item",
        ge=0  # Ensure amount is not negative
    )

    @validator('amount')
    def validate_amount(cls, v, values):
        """Validate that amount equals quantity * unit_price"""
        if 'quantity' in values and 'unit_price' in values:
            expected = round(values['quantity'] * values['unit_price'], 2)
            if abs(v - expected) > 0.01:  # Allow small rounding differences
                v = expected
        return v

    @validator('description')
    def clean_description(cls, v):
        """Clean and format multiline descriptions"""
        if v:
            # Replace multiple spaces with single space
            v = ' '.join(v.split())
            # Replace \n with actual newlines
            v = v.replace('\\n', '\n')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "description": "ACP101 Accounting Package\nAnnual Subscription",
                "quantity": 3.0,
                "unit_price": 450.00,
                "amount": 1350.00
            }
        }

class InvoiceData(BaseModel):
    vendor: str = Field(..., description="Company name or vendor")
    invoice_number: str = Field(..., description="Invoice reference number")
    date: str = Field(..., description="Invoice date (YYYY-MM-DD)")
    total: float = Field(..., description="Total invoice amount")
    currency: str = Field(..., description="Currency code (e.g., USD)")
    items: List[LineItem] = Field(default_factory=list, description="List of invoice line items")

    @validator('total')
    def validate_total(cls, v, values):
        """Validate that total equals sum of line item amounts"""
        if 'items' in values and values['items']:
            expected = round(sum(item.amount for item in values['items']), 2)
            if abs(v - expected) > 0.01:  # Allow small rounding differences
                v = expected
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "vendor": "ABC Company",
                "invoice_number": "INV-2025-001",
                "date": "2025-01-15",
                "total": 4100.00,
                "currency": "USD",
                "items": [
                    {
                        "description": "ACP101 Accounting Package\nAnnual Subscription",
                        "quantity": 3.0,
                        "unit_price": 450.00,
                        "amount": 1350.00
                    }
                ]
            }
        }

class ProcessResponse(BaseModel):
    success: bool
    extracted_text: Optional[str] = None
    parsed_data: Optional[InvoiceData] = None
    error: Optional[str] = None