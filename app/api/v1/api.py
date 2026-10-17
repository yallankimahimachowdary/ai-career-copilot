from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.api.v1.endpoints import auth, health, resumes, job_postings, matches, coach, market, chat, graph

api_router = APIRouter()

# Public endpoint routers
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Accounts"])

# Authenticated endpoint routers (require valid Bearer token)
auth_deps = [Depends(get_current_user)]
api_router.include_router(resumes.router, prefix="/resumes", tags=["Resumes"], dependencies=auth_deps)
api_router.include_router(job_postings.router, prefix="/jobs", tags=["Job Postings"], dependencies=auth_deps)
api_router.include_router(matches.router, prefix="/matches", tags=["Matches & Recommendations"], dependencies=auth_deps)
api_router.include_router(coach.router, prefix="/coach", tags=["Interview Coach Agent"], dependencies=auth_deps)
api_router.include_router(market.router, prefix="/market", tags=["Market Intelligence Agent"], dependencies=auth_deps)
api_router.include_router(chat.router, prefix="/chat", tags=["Adaptive Intent Router & Chat"], dependencies=auth_deps)
api_router.include_router(graph.router, prefix="/graph", tags=["Knowledge Graph Agent"], dependencies=auth_deps)


