from typing import Optional

from pydantic import BaseModel, Field, validator


class MedicationPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    dosage: Optional[str] = Field(None, max_length=80)
    form: Optional[str] = Field(None, max_length=80)
    category: Optional[str] = Field(None, max_length=60)
    photo_file_id: Optional[str] = Field(None, max_length=256)
    notes: Optional[str] = Field(None, max_length=500)
    dose_units: Optional[str] = Field(None, max_length=40)
    dose_size: Optional[float] = 1.0
    pack_total: Optional[float] = 0.0
    stock_remaining: Optional[float] = None

    @validator("dose_size", "pack_total", "stock_remaining", pre=True, always=True)
    def _ensure_float(cls, value, field):
        if value in (None, "", "null"):
            if field.name == "stock_remaining":
                return None
            return 0.0
        return float(value)


class RestockArgs(BaseModel):
    med_id: int
    quantity: float
    note: Optional[str] = None


class SetStockArgs(BaseModel):
    med_id: int
    value: float
