from decimal import Decimal

from pydantic import Field

from backend.common.schema import SchemaBase


class GetAIBuddyBillingCurrencyDetail(SchemaBase):
    """AI Buddy 计费币种

    所有金额在数据库与接口中都以结算币种（USD）存储，这里返回的只是展示配置，
    前端按 `amount * rate` 换算展示，不参与任何计费计算
    """

    settlement_currency: str = Field(description='结算币种，所有金额的存储单位')
    code: str = Field(description='展示币种代码')
    symbol: str = Field(description='展示币种符号')
    rate: Decimal = Field(description='1 单位结算币种可兑换的展示币种数量')
    decimals: int = Field(description='展示小数位')
