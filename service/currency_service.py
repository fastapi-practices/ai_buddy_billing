from decimal import Decimal

from backend.core.conf import settings
from backend.plugin.ai_buddy_billing.schema.currency import GetAIBuddyBillingCurrencyDetail

SETTLEMENT_CURRENCY = 'USD'
"""结算币种，所有金额字段的统一存储单位"""


class AIBuddyBillingCurrencyService:
    """AI Buddy 计费币种服务类"""

    @staticmethod
    def get() -> GetAIBuddyBillingCurrencyDetail:
        """
        获取计费展示币种

        :return:
        """
        rate = settings.AI_BUDDY_BILLING_DISPLAY_CURRENCY_RATE
        return GetAIBuddyBillingCurrencyDetail(
            settlement_currency=SETTLEMENT_CURRENCY,
            code=settings.AI_BUDDY_BILLING_DISPLAY_CURRENCY,
            symbol=settings.AI_BUDDY_BILLING_DISPLAY_CURRENCY_SYMBOL,
            rate=rate if rate > 0 else Decimal(1),
            decimals=max(settings.AI_BUDDY_BILLING_DISPLAY_CURRENCY_DECIMALS, 0),
        )


ai_buddy_billing_currency_service: AIBuddyBillingCurrencyService = AIBuddyBillingCurrencyService()
