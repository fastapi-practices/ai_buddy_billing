"""计费价格解析

统一说明：
- 目录价（供应商报价）固定按美元每百万 token 计价；
- 峰谷价通过价格时段倍率生效，倍率只作用于目录价；
- 上下文阶梯价在提示词 token 超过阈值后覆盖基础单价；
- 结算金额一律保留 8 位小数，便于和其他金额字段对齐
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from backend.plugin.ai_buddy_billing.utils.usage import BillingUsageRecord
from backend.utils.timezone import timezone

MONEY_QUANT = Decimal('0.00000001')
MILLION = Decimal(1_000_000)

TOKEN_PRICE_FIELDS: tuple[str, ...] = (
    'input_price',
    'output_price',
    'cache_read_price',
    'cache_write_price',
    'input_audio_price',
    'output_audio_price',
    'cache_audio_read_price',
)

TIER_PRICE_FIELDS: tuple[str, ...] = (
    'input_price',
    'output_price',
    'cache_read_price',
    'cache_write_price',
)

IMAGE_PRICE_FIELD = 'image_price'

ALL_PRICE_FIELDS: tuple[str, ...] = (*TOKEN_PRICE_FIELDS, IMAGE_PRICE_FIELD)

DEFAULT_PRICE_PROVIDER_ID = 0
DEFAULT_PRICE_MODEL_ID = '*'


@dataclass(frozen=True, slots=True)
class PriceTerms:
    """一条价格版本的全部计价条件"""

    input_price: Decimal = Decimal(0)
    output_price: Decimal = Decimal(0)
    cache_read_price: Decimal = Decimal(0)
    cache_write_price: Decimal = Decimal(0)
    input_audio_price: Decimal = Decimal(0)
    output_audio_price: Decimal = Decimal(0)
    cache_audio_read_price: Decimal = Decimal(0)
    image_price: Decimal = Decimal(0)
    time_windows: tuple[Mapping[str, Any], ...] = ()
    context_tiers: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class PriceQuote:
    """单次用量实际生效的计价结果"""

    rates: dict[str, Decimal]
    image_price: Decimal
    multiplier: Decimal
    tier: str | None
    window: str | None


def as_decimal(value: Any, default: Decimal = Decimal(0)) -> Decimal:
    """
    将任意金额字段转换为非负有限小数

    :param value: 原始金额
    :param default: 无法解析时使用的值
    :return:
    """
    if value is None or isinstance(value, bool):
        return default
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default
    return amount if amount.is_finite() and amount >= 0 else default


def as_optional_decimal(value: Any) -> Decimal | None:
    """
    将任意金额字段转换为可空小数

    :param value: 原始金额
    :return:
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() and amount >= 0 else None


def terms_from_price(price: Any) -> PriceTerms:
    """
    将价格记录转换为计价条件

    :param price: 价格记录
    :return:
    """
    return PriceTerms(
        **{field: as_decimal(getattr(price, field)) for field in TOKEN_PRICE_FIELDS},
        image_price=as_decimal(getattr(price, IMAGE_PRICE_FIELD)),
        time_windows=tuple(price.time_windows),
        context_tiers=tuple(price.context_tiers),
    )


def merge_terms(
    *,
    base: PriceTerms,
    rates: Mapping[str, Decimal],
    tiers: Sequence[Mapping[str, Any]],
) -> PriceTerms:
    """
    在基准价上覆盖同步到的价格，保留人工维护的图片价、音频缓存价与价格时段

    :param base: 基准价
    :param rates: 同步到的 token 单价
    :param tiers: 同步到的上下文阶梯价
    :return:
    """
    values = {field: rates.get(field, getattr(base, field)) for field in TOKEN_PRICE_FIELDS}
    return replace(
        base,
        **values,
        context_tiers=tuple(tiers) if tiers else base.context_tiers,
    )


def prompt_tokens(usage: BillingUsageRecord) -> int:
    """
    计算参与上下文阶梯判断的提示词 token 数

    :param usage: 用量记录
    :return:
    """
    return usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens


def normalize_tiers(tiers: Sequence[Mapping[str, Any]]) -> tuple[tuple[tuple[str, Any], ...], ...]:
    """
    归一化上下文阶梯价，便于比较数据库字符串与目录小数的差异

    目录价缺省的阶梯单价在数据库中会存为 None，归一化时一并忽略

    :param tiers: 上下文阶梯价
    :return:
    """
    normalized = []
    for tier in tiers:
        pairs = [('threshold', int(tier['threshold']))]
        pairs.extend(
            (key, amount)
            for key, value in tier.items()
            if key != 'threshold' and (amount := as_optional_decimal(value)) is not None
        )
        normalized.append(tuple(sorted(pairs)))
    return tuple(normalized)


def build_quote(
    *,
    terms: PriceTerms,
    usage_time: datetime,
    prompt_token_count: int,
) -> PriceQuote:
    """
    结合上下文阶梯与峰谷时段解析单次用量的计价

    优先级：基础价 → 上下文阶梯价 → 峰谷时段单价 → 峰谷倍率

    :param terms: 计价条件
    :param usage_time: 用量发生时间
    :param prompt_token_count: 提示词 token 数
    :return:
    """
    rates = {field: getattr(terms, field) for field in TOKEN_PRICE_FIELDS}
    tier = resolve_tier(terms.context_tiers, prompt_token_count)
    tier_label = None
    if tier is not None:
        tier_label = str(tier['threshold'])
        for field in TIER_PRICE_FIELDS:
            value = as_optional_decimal(tier[field])
            if value is not None:
                rates[field] = value
    window = resolve_window(terms.time_windows, usage_time)
    multiplier = Decimal(1)
    window_name = None
    if window is not None:
        window_name = str(window['name'])
        for field in TIER_PRICE_FIELDS:
            value = as_optional_decimal(window[field])
            if value is not None:
                rates[field] = value
        multiplier = as_decimal(window['multiplier'])
    return PriceQuote(
        rates=rates,
        image_price=terms.image_price,
        multiplier=multiplier,
        tier=tier_label,
        window=window_name,
    )


def resolve_tier(
    tiers: Sequence[Mapping[str, Any]],
    prompt_token_count: int,
) -> Mapping[str, Any] | None:
    """
    匹配提示词 token 命中的最高上下文阶梯

    :param tiers: 上下文阶梯价
    :param prompt_token_count: 提示词 token 数
    :return:
    """
    matched: Mapping[str, Any] | None = None
    for item in tiers:
        threshold = item['threshold']
        if prompt_token_count <= threshold:
            continue
        if matched is None or threshold > matched['threshold']:
            matched = item
    return matched


def resolve_window(
    windows: Sequence[Mapping[str, Any]],
    usage_time: datetime,
) -> Mapping[str, Any] | None:
    """
    按顺序匹配命中的价格时段，先匹配到的时间段生效

    时段统一使用全局时区（settings.DATETIME_TIMEZONE）判断

    :param windows: 价格时段列表
    :param usage_time: 用量发生时间
    :return:
    """
    local_time = timezone.from_datetime(usage_time)
    for window in windows:
        if _in_window(window=window, local_time=local_time):
            return window
    return None


def calculate_cost(*, usage: BillingUsageRecord, quote: PriceQuote) -> Decimal:
    """
    按每百万 token 单价、图片单价与峰谷倍率计算单次响应费用

    峰谷倍率只作用于 token 费用，图片按张计价不受时段影响

    :param usage: 用量记录
    :param quote: 生效的计价
    :return:
    """
    tokens = {
        'input_price': usage.input_tokens,
        'output_price': usage.output_tokens,
        'cache_read_price': usage.cache_read_tokens,
        'cache_write_price': usage.cache_write_tokens,
        'input_audio_price': usage.input_audio_tokens,
        'output_audio_price': usage.output_audio_tokens,
        'cache_audio_read_price': usage.cache_audio_read_tokens,
    }
    cost = sum(
        (Decimal(count) * quote.rates[field] / MILLION for field, count in tokens.items()),
        Decimal(0),
    )
    image_cost = Decimal(usage.generated_images) * quote.image_price
    return (cost * quote.multiplier + image_cost).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def _in_window(*, window: Mapping[str, Any], local_time: datetime) -> bool:
    """判断本地时间是否落在价格时段内"""
    start = time.fromisoformat(window['start'])
    end = time.fromisoformat(window['end'])
    days = set(window['days'])
    weekday = local_time.isoweekday()
    clock = local_time.time()
    if start == end:
        return not days or weekday in days
    if start < end:
        return (not days or weekday in days) and start <= clock < end
    # 跨天时段：当天起始时间之后匹配，或次日结束时间之前匹配
    if (not days or weekday in days) and clock >= start:
        return True
    previous_weekday = 7 if weekday == 1 else weekday - 1
    return (not days or previous_weekday in days) and clock < end


def is_default_price(*, provider_id: int, model_id: str) -> bool:
    """
    判断是否为保底价

    :param provider_id: 供应商 ID
    :param model_id: 模型 ID
    :return:
    """
    return provider_id == DEFAULT_PRICE_PROVIDER_ID and model_id == DEFAULT_PRICE_MODEL_ID
