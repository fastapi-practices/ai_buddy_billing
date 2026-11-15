from fastapi import APIRouter

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.plugin.ai_buddy_billing.schema.currency import GetAIBuddyBillingCurrencyDetail
from backend.plugin.ai_buddy_billing.service.currency_service import ai_buddy_billing_currency_service

router = APIRouter()


@router.get(
    '',
    summary='获取 AI Buddy 计费展示币种',
    dependencies=[DependsJwtAuth],
)
async def get_ai_buddy_billing_currency() -> ResponseSchemaModel[GetAIBuddyBillingCurrencyDetail]:
    data = ai_buddy_billing_currency_service.get()
    return response_base.success(data=data)
