from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator


class ContactInfo(BaseModel):
    name: Optional[str] = Field(None, description="Full name of candidate")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    location: Optional[str] = Field(None, description="City, State, Country")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn profile URL")
    github_url: Optional[str] = Field(None, description="GitHub profile URL")
    portfolio_url: Optional[str] = Field(None, description="Portfolio or personal website")


class WorkExperience(BaseModel):
    title: str = Field(..., description="Job title / role")
    company: str = Field(..., description="Company or organization name")
    location: Optional[str] = Field(None, description="Job location")
    start_date: Optional[str] = Field(None, description="Start date (e.g. Jan 2022)")
    end_date: Optional[str] = Field(None, description="End date (e.g. Present)")
    is_current: bool = Field(False, description="Whether this is current role")
    description: List[str] = Field(default_factory=list, description="Bullet points/achievements")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data):
        if isinstance(data, dict):
            if "job_title" in data and "title" not in data:
                data["title"] = data.pop("job_title")
            if "role" in data and "title" not in data:
                data["title"] = data.pop("role")
            if "position" in data and "title" not in data:
                data["title"] = data.pop("position")
            if "organization" in data and "company" not in data:
                data["company"] = data.pop("organization")
            if "employer" in data and "company" not in data:
                data["company"] = data.pop("employer")
            if data.get("title") is None:
                data["title"] = "Professional"
            if data.get("company") is None:
                data["company"] = "Organization"
            if data.get("description") is None:
                data["description"] = []
            elif isinstance(data.get("description"), str):
                data["description"] = [data["description"]]
        return data


class Education(BaseModel):
    institution: str = Field(..., description="University / College / School name")
    degree: Optional[str] = Field(None, description="Degree type (e.g. B.S., M.S.)")
    field_of_study: Optional[str] = Field(None, description="Major / specialization")
    graduation_year: Optional[str] = Field(None, description="Graduation year or date")
    gpa: Optional[str] = Field(None, description="GPA or grade")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data):
        if isinstance(data, dict):
            if "school" in data and "institution" not in data:
                data["institution"] = data.pop("school")
            if "university" in data and "institution" not in data:
                data["institution"] = data.pop("university")
            if "college" in data and "institution" not in data:
                data["institution"] = data.pop("college")
            if data.get("institution") is None:
                data["institution"] = "Educational Institution"
        return data


class Project(BaseModel):
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project summary")
    technologies: List[str] = Field(default_factory=list, description="Technologies used")
    url: Optional[str] = Field(None, description="Project link or repo")

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data):
        if isinstance(data, dict):
            if "title" in data and "name" not in data:
                data["name"] = data.pop("title")
            if "project_name" in data and "name" not in data:
                data["name"] = data.pop("project_name")
            if data.get("name") is None:
                data["name"] = "Project"
            if isinstance(data.get("technologies"), str):
                data["technologies"] = [t.strip() for t in data["technologies"].split(",") if t.strip()]
            elif data.get("technologies") is None:
                data["technologies"] = []
        elif isinstance(data, str):
            data = {"name": data}
        return data


class ParsedResume(BaseModel):
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    summary: Optional[str] = Field(None, description="Professional summary / objective")
    skills: List[str] = Field(default_factory=list, description="List of technical & soft skills")
    experience: List[WorkExperience] = Field(default_factory=list, description="Work history")
    education: List[Education] = Field(default_factory=list, description="Educational background")
    projects: List[Project] = Field(default_factory=list, description="Key projects")
    certifications: List[str] = Field(default_factory=list, description="Certifications and licenses")

    @model_validator(mode="before")
    @classmethod
    def normalize_resume(cls, data):
        if not isinstance(data, dict):
            return data

        # 1. Flatten skills if dict or nested structures
        raw_skills = data.get("skills")
        if isinstance(raw_skills, dict):
            flattened = []
            for val in raw_skills.values():
                if isinstance(val, list):
                    for item in val:
                        if isinstance(item, str):
                            flattened.append(item.strip())
                        elif isinstance(item, dict):
                            flattened.extend([str(v).strip() for v in item.values() if v])
                elif isinstance(val, str):
                    flattened.extend([s.strip() for s in val.split(",") if s.strip()])
            data["skills"] = list(dict.fromkeys(flattened))
        elif isinstance(raw_skills, list):
            flattened = []
            for item in raw_skills:
                if isinstance(item, str):
                    flattened.append(item.strip())
                elif isinstance(item, dict):
                    for sub_val in item.values():
                        if isinstance(sub_val, list):
                            flattened.extend([str(s).strip() for s in sub_val if s])
                        elif isinstance(sub_val, str):
                            flattened.extend([s.strip() for s in sub_val.split(",") if s.strip()])
            data["skills"] = list(dict.fromkeys(flattened))
        elif isinstance(raw_skills, str):
            data["skills"] = [s.strip() for s in raw_skills.split(",") if s.strip()]

        # 2. Flatten certifications if dicts, objects or comma-separated string
        raw_certs = data.get("certifications")
        if isinstance(raw_certs, list):
            flat_certs = []
            for cert in raw_certs:
                if isinstance(cert, str):
                    flat_certs.append(cert.strip())
                elif isinstance(cert, dict):
                    name = cert.get("name") or cert.get("title") or cert.get("certificate") or cert.get("certification")
                    issuer = cert.get("issuer") or cert.get("organization") or cert.get("issuing_organization") or cert.get("authority")
                    date = cert.get("date") or cert.get("year") or cert.get("issue_date")
                    parts = [p for p in [name, f"({issuer})" if issuer else None, date] if p]
                    if parts:
                        flat_certs.append(" ".join(parts))
                    elif name:
                        flat_certs.append(str(name))
                    else:
                        flat_certs.append(", ".join(f"{k}: {v}" for k, v in cert.items() if v))
            data["certifications"] = flat_certs
        elif isinstance(raw_certs, str):
            data["certifications"] = [s.strip() for s in raw_certs.split(",") if s.strip()]

        return data


class ResumeUploadResponse(BaseModel):
    id: str = Field(..., description="Unique resume ID")
    filename: str = Field(..., description="Uploaded file name")
    candidate_name: Optional[str] = Field(None, description="Extracted candidate name")
    email: Optional[str] = Field(None, description="Extracted email")
    parsed_data: ParsedResume = Field(..., description="Structured parsed resume details")
    embedding_dimension: int = Field(..., description="Dimension of computed vector embedding")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Upload timestamp",
    )


class ResumeDetailResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    raw_text: str
    parsed_data: ParsedResume
    created_at: datetime
    updated_at: datetime


class ResumeListItemResponse(BaseModel):
    id: str
    filename: str
    candidate_name: Optional[str] = None
    email: Optional[str] = None
    skills_count: int
    created_at: datetime


class SimilarResumeResponse(BaseModel):
    id: str
    filename: str
    candidate_name: Optional[str] = None
    similarity_score: float
