from typing import Optional
from pydantic import BaseModel, Field

class JobProfile(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    work_mode: str = ""
    minimum_experience_years: Optional[float] = Field(default=None, ge=0)
    maximum_experience_years: Optional[float] = Field(default=None, ge=0)
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    responsibilities: list[str] = []
    education: list[str] = []
    certifications: list[str] = []
    domains: list[str] = []
    extraction_notes: list[str] = []
