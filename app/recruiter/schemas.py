from pydantic import BaseModel, Field


class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    company: str = Field(min_length=2, max_length=200)
    location: str = 'Remote'
    employment_type: str = 'Full Time'
    description: str = ''
    required_skills: str | list[str] = ''
    source: str = 'Manual'
    external_id: str | None = None
    minimum_experience_years: float | None = Field(default=None, ge=0)


class JobDescriptionAnalyzeIn(BaseModel):
    description: str = Field(min_length=1, max_length=100_000)


class CandidateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=255)
    location: str = ''
    years_experience: float = Field(default=0, ge=0, le=80)
    skills: str | list[str] = ''
    availability: str = 'Available'
    resume_id: int | None = None
    resume_candidate_id: str | None = Field(default=None, max_length=32)
    current_role: str = Field(default='', max_length=255)
    profile: dict = Field(default_factory=dict)
    work_authorization: str = Field(default='', max_length=120)
    notes: str = Field(default='', max_length=10_000)


class CandidateProfileUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    location: str | None = None
    years_experience: float | None = Field(default=None, ge=0, le=80)
    skills: str | list[str] | None = None
    availability: str | None = Field(default=None, max_length=50)
    current_role: str | None = Field(default=None, max_length=255)
    profile: dict | None = None
    work_authorization: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=10_000)


class MatchRunIn(BaseModel):
    job_id: int


class SubmissionIn(BaseModel):
    job_id: int
    candidate_id: int
    vendor: str = Field(min_length=1, max_length=255)
    consent_share: bool = False
    consent_contact: bool = False
    notes: str = ''


class SubmissionStatusIn(BaseModel):
    status: str


class SettingsIn(BaseModel):
    ai_model: str = Field(default='gemini-2.5-flash', min_length=1, max_length=120)
    match_threshold: int = Field(default=70, ge=0, le=100)


class IntegrationIn(BaseModel):
    provider: str
    enabled: bool = True
    config_json: str = '{}'
