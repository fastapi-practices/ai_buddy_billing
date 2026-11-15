from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.ai_buddy.crud.crud_model import ai_buddy_model_dao
from backend.plugin.ai_buddy.crud.crud_provider import ai_buddy_provider_dao
from backend.plugin.ai_buddy.enums import AIBuddyProviderType
from backend.plugin.ai_buddy.model import AIBuddyModel, AIBuddyProvider
from backend.plugin.ai_buddy_billing.crud.crud_ledger import ai_buddy_billing_ledger_dao
from backend.plugin.ai_buddy_billing.crud.crud_price import ai_buddy_billing_price_dao
from backend.plugin.ai_buddy_billing.enums import AIBuddyBillingPriceSource, AIBuddyBillingPriceSyncStatus
from backend.plugin.ai_buddy_billing.model import AIBuddyBillingPrice
from backend.plugin.ai_buddy_billing.schema.price import (
    AIBuddyBillingPriceSyncFieldChange,
    AIBuddyBillingPriceSyncParam,
    CreateAIBuddyBillingPriceParam,
    GetAIBuddyBillingPriceDetail,
    GetAIBuddyBillingPriceSyncDetail,
    GetAIBuddyBillingPriceSyncItem,
    UpdateAIBuddyBillingPriceParam,
)
from backend.plugin.ai_buddy_billing.utils.models_dev import Catalog, get_catalog
from backend.plugin.ai_buddy_billing.utils.pricing import (
    ALL_PRICE_FIELDS,
    PriceTerms,
    as_optional_decimal,
    merge_terms,
    normalize_tiers,
    terms_from_price,
)
from backend.utils.timezone import timezone

# 人工修改这些字段即视为人工定价，models.dev 后续同步默认不会覆盖
_MANUAL_EDIT_FIELDS = frozenset({
    'input_price',
    'output_price',
    'cache_read_price',
    'cache_write_price',
    'input_audio_price',
    'output_audio_price',
    'cache_audio_read_price',
    'image_price',
    'time_windows',
    'context_tiers',
})


@dataclass(frozen=True, slots=True)
class _SyncDecision:
    """单个模型的同步决策"""

    item: GetAIBuddyBillingPriceSyncItem
    terms: PriceTerms | None = None


class AIBuddyBillingPriceService:
    """AI Buddy 计费价格服务类"""

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        provider_id: int | None,
        model_id: str | None,
        active: bool | None,
    ) -> dict[str, Any]:
        """
        分页获取价格

        :param db: 数据库会话
        :param provider_id: 供应商 ID
        :param model_id: 模型 ID
        :param active: 是否只查询生效中的价格
        :return:
        """
        effective_time = timezone.now() if active else None
        stmt = await ai_buddy_billing_price_dao.get_select(
            provider_id=provider_id,
            model_id=model_id,
            active=active,
            effective_time=effective_time,
        )
        return await paging_data(db, stmt)

    @staticmethod
    async def get_all(
        *,
        db: AsyncSession,
        provider_id: int | None = None,
        model_id: str | None = None,
    ) -> list[GetAIBuddyBillingPriceDetail]:
        """
        获取所有生效中的价格

        :param db: 数据库会话
        :param provider_id: 供应商 ID
        :param model_id: 模型 ID
        :return:
        """
        rows = await ai_buddy_billing_price_dao.get_all_active(
            db,
            provider_id=provider_id,
            model_id=model_id,
            effective_time=timezone.now(),
        )
        return [GetAIBuddyBillingPriceDetail.model_validate(row) for row in rows]

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateAIBuddyBillingPriceParam) -> GetAIBuddyBillingPriceDetail:
        """
        创建价格，同一供应商与模型不允许重复添加

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        if obj.effective_to is not None and obj.effective_to <= obj.effective_from:
            raise errors.RequestError(msg='价格失效时间必须晚于生效时间')
        existed = await ai_buddy_billing_price_dao.get_unexpired(
            db,
            provider_id=obj.provider_id,
            model_id=obj.model_id,
            effective_time=obj.effective_from,
        )
        if existed is not None:
            raise errors.ConflictError(msg='该供应商与模型已配置价格，请直接修改')
        row = await ai_buddy_billing_price_dao.create(
            db,
            obj,
            source=AIBuddyBillingPriceSource.manual.value,
        )
        return GetAIBuddyBillingPriceDetail.model_validate(row)

    @staticmethod
    async def update(
        *,
        db: AsyncSession,
        pk: int,
        obj: UpdateAIBuddyBillingPriceParam,
    ) -> GetAIBuddyBillingPriceDetail:
        """
        更新价格

        :param db: 数据库会话
        :param pk: 价格 ID
        :param obj: 更新参数
        :return:
        """
        price = await ai_buddy_billing_price_dao.get(db, pk)
        if price is None:
            raise errors.NotFoundError(msg='计费价格不存在')
        if obj.effective_to is not None and obj.effective_to <= price.effective_from:
            raise errors.RequestError(msg='价格失效时间必须晚于生效时间')
        values = obj.model_dump(exclude_unset=True)
        if _MANUAL_EDIT_FIELDS & values.keys():
            values['source'] = AIBuddyBillingPriceSource.manual.value
            values['synced_at'] = None
        if values:
            await ai_buddy_billing_price_dao.update(db, pk=pk, values=values)
        return GetAIBuddyBillingPriceDetail.model_validate(await ai_buddy_billing_price_dao.get(db, pk))

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """
        删除价格

        :param db: 数据库会话
        :param pk: 价格 ID
        :return:
        """
        price = await ai_buddy_billing_price_dao.get(db, pk)
        if price is None:
            raise errors.NotFoundError(msg='计费价格不存在')
        if await ai_buddy_billing_ledger_dao.get_by_price(db, price_id=pk) is not None:
            raise errors.RequestError(msg='价格已用于结算，请改为设置失效时间')
        return await ai_buddy_billing_price_dao.delete(db, pk=pk)

    async def preview_sync(
        self, *, db: AsyncSession, obj: AIBuddyBillingPriceSyncParam
    ) -> GetAIBuddyBillingPriceSyncDetail:
        """
        预览 models.dev 价格同步差异

        :param db: 数据库会话
        :param obj: 同步参数
        :return:
        """
        return await self._sync(db=db, obj=obj, apply=False)

    async def sync(self, *, db: AsyncSession, obj: AIBuddyBillingPriceSyncParam) -> GetAIBuddyBillingPriceSyncDetail:
        """
        同步 models.dev 价格

        :param db: 数据库会话
        :param obj: 同步参数
        :return:
        """
        return await self._sync(db=db, obj=obj, apply=True)

    async def _sync(
        self,
        *,
        db: AsyncSession,
        obj: AIBuddyBillingPriceSyncParam,
        apply: bool,
    ) -> GetAIBuddyBillingPriceSyncDetail:
        """执行价格同步，预览与写入共用同一套决策"""
        catalog = await get_catalog()
        effective_from = obj.effective_from or timezone.now()
        # 价格按供应商与模型建档，因此同步覆盖系统内置与用户自建供应商
        providers = await ai_buddy_provider_dao.select_models(db, deleted=0)
        providers_by_id = {provider.id: provider for provider in providers}
        if obj.provider_ids:
            wanted = set(obj.provider_ids)
            providers_by_id = {pk: provider for pk, provider in providers_by_id.items() if pk in wanted}
        models = await ai_buddy_model_dao.get_all_by_providers(db, list(providers_by_id))
        if obj.model_ids:
            wanted_models = set(obj.model_ids)
            models = [model for model in models if model.model_id in wanted_models]
        unexpired = await ai_buddy_billing_price_dao.get_all_unexpired(db, effective_time=effective_from)
        prices_by_model = {(price.provider_id, price.model_id): price for price in unexpired}
        decisions = [
            self._decide(
                catalog=catalog,
                provider=providers_by_id[model.provider_id],
                model=model,
                current=prices_by_model.get((model.provider_id, model.model_id)),
                effective_from=effective_from,
                overwrite_manual=obj.overwrite_manual,
            )
            for model in models
        ]
        if apply:
            for decision in decisions:
                if decision.terms is None:
                    continue
                await self._persist(
                    db=db,
                    decision=decision,
                    catalog_version=catalog.version,
                    effective_from=effective_from,
                )
        items = [decision.item for decision in decisions]
        created = sum(1 for item in items if item.status == AIBuddyBillingPriceSyncStatus.create)
        updated = sum(1 for item in items if item.status == AIBuddyBillingPriceSyncStatus.update)
        return GetAIBuddyBillingPriceSyncDetail(
            catalog_version=catalog.version,
            scanned=len(items),
            created=created,
            updated=updated,
            skipped=len(items) - created - updated,
            items=items,
        )

    def _decide(
        self,
        *,
        catalog: Catalog,
        provider: AIBuddyProvider,
        model: AIBuddyModel,
        current: AIBuddyBillingPrice | None,
        effective_from: datetime,
        overwrite_manual: bool,
    ) -> _SyncDecision:
        """计算单个模型的同步决策"""
        base = terms_from_price(current) if current is not None else PriceTerms()
        entry = catalog.find(provider_type=AIBuddyProviderType(provider.type), model_id=model.model_id)
        item = GetAIBuddyBillingPriceSyncItem(
            provider_id=provider.id,
            provider_name=provider.name,
            model_id=model.model_id,
            status=AIBuddyBillingPriceSyncStatus.not_found.value,
            source_provider=entry.source if entry is not None else None,
            current_price_id=current.id if current is not None else None,
        )
        if entry is None:
            return _SyncDecision(item=item)
        rates = entry.rates
        if not rates:
            return _SyncDecision(item=item.model_copy(update={'status': AIBuddyBillingPriceSyncStatus.no_cost.value}))
        desired = merge_terms(base=base, rates=rates, tiers=entry.context_tiers)
        changes = self._diff(current=current, desired=desired)
        item = item.model_copy(
            update={
                'changes': changes,
                'missing_fields': [field for field in ALL_PRICE_FIELDS if field not in rates],
            }
        )
        if current is not None and current.effective_from > effective_from:
            status = AIBuddyBillingPriceSyncStatus.future_price
        elif current is None:
            status = AIBuddyBillingPriceSyncStatus.create
        elif not changes:
            status = AIBuddyBillingPriceSyncStatus.unchanged
        elif current.source != AIBuddyBillingPriceSource.models_dev and not overwrite_manual:
            status = AIBuddyBillingPriceSyncStatus.manual_locked
        else:
            status = AIBuddyBillingPriceSyncStatus.update
        return _SyncDecision(
            item=item.model_copy(update={'status': status.value}),
            terms=(
                desired
                if status in {AIBuddyBillingPriceSyncStatus.create, AIBuddyBillingPriceSyncStatus.update}
                else None
            ),
        )

    @staticmethod
    def _diff(*, current: AIBuddyBillingPrice | None, desired: PriceTerms) -> list[AIBuddyBillingPriceSyncFieldChange]:
        """对比当前价格与同步后的价格"""
        base = terms_from_price(current) if current is not None else PriceTerms()
        changes: list[AIBuddyBillingPriceSyncFieldChange] = []
        for field in ALL_PRICE_FIELDS:
            before = getattr(base, field)
            after = getattr(desired, field)
            if before == after:
                continue
            changes.append(
                AIBuddyBillingPriceSyncFieldChange(
                    field=field,
                    current=_format_money(before),
                    next=_format_money(after),
                )
            )
        if normalize_tiers(base.context_tiers) != normalize_tiers(desired.context_tiers):
            changes.append(
                AIBuddyBillingPriceSyncFieldChange(
                    field='context_tiers',
                    current=_format_tiers(base.context_tiers),
                    next=_format_tiers(desired.context_tiers),
                )
            )
        return changes

    @staticmethod
    async def _persist(
        *,
        db: AsyncSession,
        decision: _SyncDecision,
        catalog_version: str,
        effective_from: datetime,
    ) -> None:
        """写入新的价格版本并关闭上一版价格"""
        item = decision.item
        terms = decision.terms
        if terms is None:
            return
        provider_id: int = item.provider_id
        model_id: str = item.model_id
        await ai_buddy_billing_price_dao.close_active(
            db,
            provider_id=provider_id,
            model_id=model_id,
            effective_time=effective_from,
        )
        await ai_buddy_billing_price_dao.create(
            db,
            CreateAIBuddyBillingPriceParam(
                provider_id=provider_id,
                model_id=model_id,
                **{field: getattr(terms, field) for field in ALL_PRICE_FIELDS},
                time_windows=list(terms.time_windows),
                context_tiers=list(terms.context_tiers),
                effective_from=effective_from,
            ),
            source=AIBuddyBillingPriceSource.models_dev.value,
            source_version=catalog_version,
            synced_at=timezone.now(),
        )


def _format_money(value: Any) -> str | None:
    """格式化金额用于差异对比"""
    amount = as_optional_decimal(value)
    return None if amount is None else format(amount.normalize(), 'f')


def _format_tiers(tiers: Sequence[Mapping[str, Any]]) -> str | None:
    """格式化上下文阶梯价用于差异对比"""
    if not tiers:
        return None
    parts = []
    for tier in tiers:
        rates = ', '.join(
            f'{field}={_format_money(rate)}'
            for field, rate in tier.items()
            if field != 'threshold' and rate is not None
        )
        parts.append(f'{tier.get("threshold")}: {rates}')
    return '; '.join(parts) or None


ai_buddy_billing_price_service: AIBuddyBillingPriceService = AIBuddyBillingPriceService()
