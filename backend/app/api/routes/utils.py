from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr

from app.api.deps import get_current_active_superuser
from app.models import Message
from app.utils import generate_test_email, send_email, APIResponse

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=APIResponse[Message],
)
def test_email(email_to: EmailStr) -> APIResponse[Message]:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return APIResponse.success_response(
        Message(message="Test email sent"),
        status_code=201
    )


@router.get("/health/")
async def health_check() -> bool:
    return True
