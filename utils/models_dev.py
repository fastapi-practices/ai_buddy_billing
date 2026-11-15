"""models.dev 模型目录访问

价格同步按供应商类型映射到 models.dev 的 provider，并在缺失时按回退链继续查找
"""

import asyncio

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any

import httpx

from starlette.concurrency import run_in_threadpool

from backend.common.exception import errors
from backend.common.log import log
from backend.plugin.ai_buddy.enums import AIBuddyProviderType

MODELS_DEV_API_URL = 'https://models.dev/api.json'
MODELS_DEV_TIMEOUT_SECONDS = 30
MODELS_DEV_CACHE_SECONDS = 3600

PROVIDER_IDS: dict[AIBuddyProviderType, str] = {
    AIBuddyProviderType.openai: 'openai',
    AIBuddyProviderType.anthropic: 'anthropic',
    AIBuddyProviderType.google: 'google',
    AIBuddyProviderType.xai: 'xai',
    AIBuddyProviderType.openrouter: 'openrouter',
    AIBuddyProviderType.openai_responses: 'openai',
}

SOURCE_PROVIDERS: tuple[str, ...] = ('openrouter', 'opencode-go', 'opencode')

COST_RATE_FIELDS: dict[str, str] = {
    'input': 'input_price',
    'output': 'output_price',
    'cache_read': 'cache_read_price',
    'cache_write': 'cache_write_price',
    'input_audio': 'input_audio_price',
    'output_audio': 'output_audio_price',
}

TIER_RATE_FIELDS: dict[str, str] = {
    'input': 'input_price',
    'output': 'output_price',
    'cache_read': 'cache_read_price',
    'cache_write': 'cache_write_price',
}

CONTEXT_TIER_THRESHOLD = 200_000


@dataclass(frozen=True, slots=True)
class CatalogModel:
    """models.dev 中的单个模型"""

    source: str
    model_id: str
    data: dict[str, Any]

    @property
    def rates(self) -> dict[str, Decimal]:
        """模型基础价格，单位为美元每百万 token"""
        cost = self.data.get('cost')
        if not isinstance(cost, dict):
            return {}
        rates: dict[str, Decimal] = {}
        for key, field in COST_RATE_FIELDS.items():
            rate = as_rate(cost.get(key))
            if rate is not None:
                rates[field] = rate
        return rates

    @property
    def context_tiers(self) -> list[dict[str, Any]]:
        """模型上下文阶梯价格"""
        cost = self.data.get('cost')
        if not isinstance(cost, dict):
            return []
        tiers: dict[int, dict[str, Any]] = {}
        raw_tiers = cost.get('tiers')
        if isinstance(raw_tiers, list):
            for item in raw_tiers:
                if not isinstance(item, dict):
                    continue
                threshold = _tier_threshold(item)
                if threshold is not None:
                    _merge_tier(tiers, threshold=threshold, item=item)
        over_200k = cost.get('context_over_200k')
        if isinstance(over_200k, dict):
            _merge_tier(tiers, threshold=CONTEXT_TIER_THRESHOLD, item=over_200k)
        return [tiers[threshold] for threshold in sorted(tiers)]


@dataclass(frozen=True, slots=True)
class Catalog:
    """models.dev 模型目录"""

    version: str
    providers: dict[str, Any]

    def find(self, *, provider_type: AIBuddyProviderType, model_id: str) -> CatalogModel | None:
        """
        在目录中查找模型

        :param provider_type: AI Buddy 供应商类型
        :param model_id: 模型标识
        :return:
        """
        return find_model(self.providers, provider_type=provider_type, model_id=model_id)


_catalog: Catalog | None = None
_catalog_expires_at = 0.0
_catalog_lock = asyncio.Lock()


async def get_catalog(*, refresh: bool = False) -> Catalog:
    """
    获取 models.dev 模型目录，默认复用进程内缓存

    :param refresh: 是否强制重新下载
    :return:
    """
    global _catalog, _catalog_expires_at
    if not refresh and _catalog is not None and monotonic() < _catalog_expires_at:
        return _catalog
    async with _catalog_lock:
        if not refresh and _catalog is not None and monotonic() < _catalog_expires_at:
            return _catalog
        catalog = await fetch_catalog()
        _catalog = catalog
        _catalog_expires_at = monotonic() + MODELS_DEV_CACHE_SECONDS
        return catalog


async def fetch_catalog() -> Catalog:
    """
    下载 models.dev 最新完整模型目录

    :return:
    """
    started = monotonic()
    try:
        async with httpx.AsyncClient(timeout=MODELS_DEV_TIMEOUT_SECONDS) as client:
            response = await client.get(MODELS_DEV_API_URL)
            response.raise_for_status()
            downloaded = monotonic()
            payload = await run_in_threadpool(response.json)
    except (httpx.HTTPError, ValueError) as exc:
        raise errors.RequestError(msg='获取 models.dev 模型数据失败，请稍后重试') from exc
    if not isinstance(payload, dict):
        raise errors.RequestError(msg='获取 models.dev 模型数据失败，请稍后重试')
    log.info(
        f'models.dev 目录获取耗时: download={(downloaded - started) * 1000:.2f}ms '
        f'parse={(monotonic() - downloaded) * 1000:.2f}ms bytes={len(response.content)}'
    )
    return Catalog(
        version=datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        providers=payload,
    )


def find_model(
    providers: dict[str, Any],
    *,
    provider_type: AIBuddyProviderType,
    model_id: str,
) -> CatalogModel | None:
    """
    按供应商映射与回退链在目录中查找模型

    :param providers: 模型目录
    :param provider_type: AI Buddy 供应商类型
    :param model_id: 模型标识
    :return:
    """
    sources = tuple(dict.fromkeys((PROVIDER_IDS[provider_type], *SOURCE_PROVIDERS)))
    for source in sources:
        entry = _lookup(providers, source=source, model_id=model_id)
        if entry is not None:
            return CatalogModel(source=source, model_id=model_id, data=entry)
    canonical_model_id = model_id.rsplit('/', 1)[-1].lower()
    for source in sources:
        models = _models_of(providers, source)
        for key, entry in models.items():
            if not isinstance(entry, dict) or not entry.get('id'):
                continue
            candidates = {key.rsplit('/', 1)[-1].lower(), str(entry.get('id')).rsplit('/', 1)[-1].lower()}
            canonical = entry.get('canonical_model_id')
            if isinstance(canonical, str):
                candidates.add(canonical.rsplit('/', 1)[-1].lower())
            if canonical_model_id in candidates:
                return CatalogModel(source=source, model_id=key, data=entry)
    return None


def as_rate(value: Any) -> Decimal | None:
    """
    将目录中的价格字段转换为非负有限小数

    :param value: 原始价格
    :return:
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        rate = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return rate if rate.is_finite() and rate >= 0 else None


def _models_of(providers: dict[str, Any], source: str) -> dict[str, Any]:
    """获取目录中指定供应商的模型集合"""
    provider = providers.get(source)
    models = provider.get('models') if isinstance(provider, dict) else None
    return models if isinstance(models, dict) else {}


def _lookup(providers: dict[str, Any], *, source: str, model_id: str) -> dict[str, Any] | None:
    """在指定供应商下精确查找模型，命中大小写变体时同样返回"""
    models = _models_of(providers, source)
    entry = models.get(model_id)
    if entry is None:
        lowered = model_id.lower()
        entry = next((item for key, item in models.items() if key.lower() == lowered), None)
    if not isinstance(entry, dict) or not entry.get('id'):
        return None
    return entry


def _tier_threshold(item: dict[str, Any]) -> int | None:
    """读取阶梯价格的上下文阈值"""
    tier = item.get('tier')
    if not isinstance(tier, dict) or tier.get('type') != 'context':
        return None
    size = tier.get('size')
    return size if type(size) is int and size > 0 else None


def _merge_tier(target: dict[int, dict[str, Any]], *, threshold: int, item: dict[str, Any]) -> None:
    """按阈值合并阶梯价格，已存在的字段不覆盖"""
    rates = {field: rate for key, field in TIER_RATE_FIELDS.items() if (rate := as_rate(item.get(key))) is not None}
    if not rates:
        return
    tier = target.setdefault(threshold, {'threshold': threshold})
    for field, rate in rates.items():
        tier.setdefault(field, rate)
