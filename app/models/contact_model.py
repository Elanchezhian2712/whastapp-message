# app/models/contact_model.py
from pydantic import BaseModel
from typing import Optional

class Contact(BaseModel):
    name: str
    mobile: str
    link: Optional[str] = ""
