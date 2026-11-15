from collections.abc import Sequence
from decimal import Decimal

from pydantic_ai import ModelResponse
from pydantic_ai.tools import RunContext
from pydantic_ai_harness.spend import Budget, PriceFunc

from backend.plugin.ai_buddy.dataclasses import ChatAgentDeps
from backend.plugin.ai_buddy_billing.model import AIBuddyBillingBudget, AIBuddyBillingPrice
from backend.plugin.ai_buddy_billing.utils.pricing import (
    DEFAULT_PRICE_MODEL_ID,
    build_quote,
    calculate_cost,
    is_default_price,
    prompt_tokens,
    terms_from_price,
)
from backend.plugin.ai_buddy_billing.utils.usage import BillingUsageRecord


def _user_scope(ctx: RunContext[ChatAgentDeps]) -> str:
    """按运行用户隔离预算计数"""
    return f'user:{ctx.deps.user_id}'


def build_spend_budgets(*, budgets: Sequence[AIBuddyBillingBudget]) -> tuple[Budget[ChatAgentDeps], ...]:
    """
    将计费预算转换为 Harness 预算

    :param budgets: 启用的计费预算
    :return:
    """
    return tuple(
        Budget(
            usd=budget.usd_limit,
            tokens=budget.token_limit,
            window=budget.window,
            scope=_user_scope,
            warn_at=budget.warn_at,
            name=f'billing-{budget.window}',
        )
        for budget in budgets
    )


def _group_prices(
    *,
    prices: Sequence[AIBuddyBillingPrice],
    primary_model_id: str | None,
) -> tuple[dict[str, AIBuddyBillingPrice], AIBuddyBillingPrice | None]:
    """
    按模型分组生效价格，同时取出保底价

    :param prices: 当前生效价格
    :param primary_model_id: 本轮主模型 ID
    :return:
    """
    default_price = next(
        (price for price in prices if is_default_price(provider_id=price.provider_id, model_id=price.model_id)),
        None,
    )
    price_by_model: dict[str, AIBuddyBillingPrice] = {}
    ambiguous: set[str] = set()
    for price in prices:
        if price.model_id == primary_model_id:
            price_by_model[price.model_id] = price
    for price in prices:
        if price.model_id == primary_model_id or price.model_id == DEFAULT_PRICE_MODEL_ID:
            continue
        if price.model_id in ambiguous:
            continue
        if price.model_id not in price_by_model:
            price_by_model[price.model_id] = price
        else:
            price_by_model.pop(price.model_id)
            ambiguous.add(price.model_id)
    return price_by_model, default_price


def build_spend_price(
    *,
    prices: Sequence[AIBuddyBillingPrice],
    primary_model_id: str | None,
) -> PriceFunc | None:
    """
    构建 Billing 历史价格定价函数

    这里返回的金额与预算上限必须使用同一单位：账单按 USD 存储，
    因此预算（Budget.usd）也按 USD 配置；峰谷倍率与上下文阶梯价在计价时已经生效，
    模型未配置价格时按保底价估算

    :param prices: 当前生效价格
    :param primary_model_id: 本轮主模型 ID
    :return:
    """
    price_by_model, default_price = _group_prices(prices=prices, primary_model_id=primary_model_id)
    if not price_by_model and default_price is None:
        return None

    def price_response(response: ModelResponse) -> Decimal | None:
        """按 Billing 历史价格计算单次模型响应费用"""
        model_id = response.model_name or primary_model_id
        price = price_by_model.get(model_id or '') or default_price
        if price is None:
            return None
        usage = response.usage
        details = usage.details or {}
        generated_images = max(
            int(details.get('generated_images') or 0),
            int(details.get('images') or 0),
            int(details.get('output_images') or 0),
        )
        record = BillingUsageRecord(
            response_index=0,
            run_id=response.run_id,
            model_id=model_id or '',
            usage_time=response.timestamp,
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            cache_read_tokens=usage.cache_read_tokens or 0,
            cache_write_tokens=usage.cache_write_tokens or 0,
            input_audio_tokens=usage.input_audio_tokens or 0,
            output_audio_tokens=usage.output_audio_tokens or 0,
            cache_audio_read_tokens=usage.cache_audio_read_tokens or 0,
            output_reasoning_tokens=usage.output_reasoning_tokens or 0,
            generated_images=generated_images,
            provider_cost=None,
            details={},
        )
        quote = build_quote(
            terms=terms_from_price(price),
            usage_time=record.usage_time,
            prompt_token_count=prompt_tokens(record),
        )
        return calculate_cost(usage=record, quote=quote)

    return price_response
