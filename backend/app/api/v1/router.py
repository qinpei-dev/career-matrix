"""Aggregate version 1 API routers."""

from fastapi import APIRouter

from .analyses import router as analyses_router
from .analysis_tasks import router as analysis_tasks_router
from .agent_runs import router as agent_runs_router
from .documents import router as documents_router
from .jobs import router as jobs_router
from .profiles import router as profiles_router
from .retrieval import router as retrieval_router
from .security_tests import router as security_tests_router

router = APIRouter(prefix="/api/v1")
router.include_router(profiles_router)
router.include_router(jobs_router)
router.include_router(analyses_router)
router.include_router(analysis_tasks_router)
router.include_router(documents_router)
router.include_router(retrieval_router)
router.include_router(agent_runs_router)
router.include_router(security_tests_router)
