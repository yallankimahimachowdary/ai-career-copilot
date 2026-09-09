import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.db.session import get_db
from app.models.resume import Resume
from app.schemas.resume import (
    ParsedResume,
    ResumeDetailResponse,
    ResumeListItemResponse,
    ResumeUploadResponse,
    SimilarResumeResponse,
)
from app.services.embedding_service import embedding_service
from app.services.extractor import ExtractionError, extract_text
from app.services.parser_agent import parser_agent

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Target job description or skill query")
    limit: int = Field(default=5, ge=1, le=50, description="Max results to return")


@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and Parse Resume",
    description="Uploads a PDF, DOCX, or TXT resume, extracts raw text, executes Parser Agent for structured data, computes dense embedding, and stores it in PostgreSQL/pgvector.",
)
async def upload_resume(
    file: UploadFile = File(..., description="Resume document (.pdf, .docx, .txt)"),
    db: AsyncSession = Depends(get_db),
) -> ResumeUploadResponse:
    # 1. Validate file extension
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type '{file_ext}'. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. Read content & validate file size
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not read uploaded file: {str(e)}")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size limit of {settings.MAX_UPLOAD_SIZE_MB}MB",
        )

    # 3. Extract text
    try:
        raw_text = extract_text(content, file.filename or f"resume{file_ext}")
    except ExtractionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))

    # 4. Save file to disk
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    unique_id = str(uuid.uuid4())
    stored_filename = f"{unique_id}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, stored_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # 5. Parse resume with Parser Agent
    parsed_resume: ParsedResume = await parser_agent.parse(raw_text)

    # 6. Generate semantic embedding
    embed_text = embedding_service.construct_embed_text(parsed_resume)
    embedding_vector = await embedding_service.get_embedding(embed_text)

    # 7. Persist record in database
    now = datetime.now(timezone.utc)
    resume_record = Resume(
        id=unique_id,
        filename=file.filename or stored_filename,
        file_path=file_path,
        file_type=file_ext.lstrip("."),
        raw_text=raw_text,
        candidate_name=parsed_resume.contact_info.name,
        email=parsed_resume.contact_info.email,
        phone=parsed_resume.contact_info.phone,
        parsed_data=parsed_resume.model_dump(),
        embedding=embedding_vector,
        created_at=now,
        updated_at=now,
    )

    try:
        db.add(resume_record)
        await db.commit()
        await db.refresh(resume_record)
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to persist resume record in database: {e}")
        # Clean up saved file on disk if DB persist fails
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to persist resume to database.")

    return ResumeUploadResponse(
        id=resume_record.id,
        filename=resume_record.filename,
        candidate_name=resume_record.candidate_name,
        email=resume_record.email,
        parsed_data=parsed_resume,
        embedding_dimension=len(embedding_vector),
        created_at=resume_record.created_at or now,
    )


@router.get(
    "",
    response_model=List[ResumeListItemResponse],
    summary="List Resumes",
    description="List uploaded resumes with metadata and skills count.",
)
async def list_resumes(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> List[ResumeListItemResponse]:
    result = await db.execute(select(Resume).order_by(Resume.created_at.desc()).offset(skip).limit(limit))
    resumes = result.scalars().all()

    items = []
    for r in resumes:
        skills = r.parsed_data.get("skills", []) if isinstance(r.parsed_data, dict) else []
        items.append(
            ResumeListItemResponse(
                id=r.id,
                filename=r.filename,
                candidate_name=r.candidate_name,
                email=r.email,
                skills_count=len(skills),
                created_at=r.created_at,
            )
        )
    return items


@router.get(
    "/{resume_id}",
    response_model=ResumeDetailResponse,
    summary="Get Resume Details",
    description="Retrieve full details and structured parsed resume for a specific ID.",
)
async def get_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
) -> ResumeDetailResponse:
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Resume with ID '{resume_id}' not found.")

    return ResumeDetailResponse(
        id=resume.id,
        filename=resume.filename,
        file_type=resume.file_type,
        candidate_name=resume.candidate_name,
        email=resume.email,
        phone=resume.phone,
        raw_text=resume.raw_text,
        parsed_data=ParsedResume.model_validate(resume.parsed_data),
        created_at=resume.created_at,
        updated_at=resume.updated_at,
    )


@router.delete(
    "/{resume_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Resume",
    description="Delete a resume from the database and remove the associated file from disk.",
)
async def delete_resume(
    resume_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Resume).where(Resume.id == resume_id))
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Resume with ID '{resume_id}' not found.")

    file_path = resume.file_path
    await db.delete(resume)
    await db.commit()

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            logger.warning(f"Could not remove local file {file_path}: {e}")

    return None


@router.post(
    "/search/similar",
    response_model=List[SimilarResumeResponse],
    summary="Semantic Resume Search",
    description="Search for similar resumes using vector cosine distance against a query or job description.",
)
async def search_similar_resumes(
    search_req: SemanticSearchRequest,
    db: AsyncSession = Depends(get_db),
) -> List[SimilarResumeResponse]:
    # Compute query vector
    query_vector = await embedding_service.get_embedding(search_req.query)

    try:
        # Cosine distance ordering using pgvector
        stmt = (
            select(
                Resume.id,
                Resume.filename,
                Resume.candidate_name,
                Resume.embedding.cosine_distance(query_vector).label("distance"),
            )
            .where(Resume.embedding.is_not(None))
            .order_by("distance")
            .limit(search_req.limit)
        )
        result = await db.execute(stmt)
        rows = result.all()

        results = []
        for row in rows:
            # Cosine similarity = 1 - cosine distance
            sim_score = max(0.0, 1.0 - float(row.distance))
            results.append(
                SimilarResumeResponse(
                    id=row.id,
                    filename=row.filename,
                    candidate_name=row.candidate_name,
                    similarity_score=round(sim_score, 4),
                )
            )
        return results
    except Exception as e:
        logger.error(f"Semantic search query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vector search query could not be executed.",
        )
