from fastapi import APIRouter
from app.api.v1.endpoints import health, resumes, job_postings, matches, coach

api_router = APIRouter()

# Include endpoint routers
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(resumes.router, prefix="/resumes", tags=["Resumes"])
api_router.include_router(job_postings.router, prefix="/jobs", tags=["Job Postings"])
api_router.include_router(matches.router, prefix="/matches", tags=["Matches & Recommendations"])
api_router.include_router(coach.router, prefix="/coach", tags=["Interview Coach Agent"])

