"""Local production-path prompt-injection regression endpoint."""

from fastapi import APIRouter, Depends

from ...application.security_test_service import run_untrusted_content_security_test
from ...schemas.security_test import SecurityTestReport
from ..dependencies import get_current_user

router = APIRouter(prefix="/security-tests", tags=["security-tests"])


@router.post(
    "/untrusted-content",
    response_model=SecurityTestReport,
    dependencies=[Depends(get_current_user)],
)
def run_untrusted_content_test() -> SecurityTestReport:
    """Execute real local code paths with mock external model and embedding providers."""
    return run_untrusted_content_security_test()
