from datetime import datetime, time
from decimal import Decimal

from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)

from backend.common.schema import SchemaBase
from backend.plugin.ai_buddy_billing.enums import AIBuddyBillingPriceSyncStatus
from backend.plugin.ai_buddy_billing.utils.pricing import (
    DEFAULT_PRICE_MODEL_ID,
    DEFAULT_PRICE_PROVIDER_ID,
    is_default_price,
)


class AIBuddyBillingPriceQueryParam(SchemaBase):
    """AI Buddy 计费价格查询参数"""

    provider_id: int | None = Field(None, description='供应商 ID')
    model_id: str | None = Field(None, description='模型 ID')
    active: bool | None = Field(None, description='是否只查询生效中的价格')


class AIBuddyBillingPriceWindowParam(SchemaBase):
    """AI Buddy 峰谷价格时段

    同一价格版本可配置多个时段，按列表顺序匹配，先命中先生效；
    `start` 晚于 `end` 表示跨天时段（例如 22:00 - 02:00）；
    时段统一按全局时区 settings.DATETIME_TIMEZONE 判断，不支持单独指定时区
    """

    name: str = Field(min_length=1, max_length=64, description='时段名称，例如 peak / off_peak')
    days: list[int] = Field(default_factory=list, description='生效星期（ISO 1-7，空表示每天）')
    start: str = Field(pattern=r'^\d{2}:\d{2}$', description='时段开始时间，格式 HH:MM')
    end: str = Field(pattern=r'^\d{2}:\d{2}$', description='时段结束时间，格式 HH:MM')
    multiplier: Decimal = Field(gt=0, description='价格倍率，例如 0.5 表示五折')
    input_price: Decimal | None = Field(None, ge=0, description='时段内输入 token 每百万价格，留空沿用基础价')
    output_price: Decimal | None = Field(None, ge=0, description='时段内输出 token 每百万价格，留空沿用基础价')
    cache_read_price: Decimal | None = Field(None, ge=0, description='时段内缓存读取 token 每百万价格，留空沿用基础价')
    cache_write_price: Decimal | None = Field(None, ge=0, description='时段内缓存写入 token 每百万价格，留空沿用基础价')

    @field_serializer('multiplier')
    def serialize_multiplier(self, value: Decimal) -> str:
        """将倍率序列化为字符串，保证 JSONB 可存储且无精度损失"""
        return format(value, 'f')

    @field_serializer('input_price', 'output_price', 'cache_read_price', 'cache_write_price')
    def serialize_price(self, value: Decimal | None) -> str | None:
        """将时段单价序列化为字符串，保证 JSONB 可存储且无精度损失"""
        return None if value is None else format(value, 'f')

    @field_validator('days')
    @classmethod
    def validate_days(cls, value: list[int]) -> list[int]:
        """校验并去重生效星期"""
        invalid = [day for day in value if day not in {1, 2, 3, 4, 5, 6, 7}]
        if invalid:
            raise ValueError('生效星期必须是 ISO 星期 1-7')
        return sorted(set(value))

    @field_validator('start', 'end')
    @classmethod
    def validate_clock(cls, value: str) -> str:
        """校验 HH:MM 时间点"""
        try:
            time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError('时间点格式必须是 HH:MM') from exc
        return value


class AIBuddyBillingPriceTierParam(SchemaBase):
    """AI Buddy 上下文阶梯价格"""

    threshold: int = Field(gt=0, description='提示词 token 超过该阈值后启用阶梯价')
    input_price: Decimal | None = Field(None, ge=0, description='输入 token 每百万价格')
    output_price: Decimal | None = Field(None, ge=0, description='输出 token 每百万价格')
    cache_read_price: Decimal | None = Field(None, ge=0, description='缓存读取 token 每百万价格')
    cache_write_price: Decimal | None = Field(None, ge=0, description='缓存写入 token 每百万价格')

    @field_serializer('input_price', 'output_price', 'cache_read_price', 'cache_write_price')
    def serialize_price(self, value: Decimal | None) -> str | None:
        """将阶梯价序列化为字符串，保证 JSONB 可存储且无精度损失"""
        return None if value is None else format(value, 'f')

    @model_validator(mode='after')
    def validate_rates(self) -> 'AIBuddyBillingPriceTierParam':
        """校验阶梯价至少配置一项单价"""
        rates = (self.input_price, self.output_price, self.cache_read_price, self.cache_write_price)
        if all(rate is None for rate in rates):
            raise ValueError('阶梯价至少配置一项 token 单价')
        return self


class AIBuddyBillingPriceSchemaBase(SchemaBase):
    """AI Buddy 计费价格基础模型"""

    provider_id: int = Field(description='供应商 ID')
    model_id: str = Field(min_length=1, max_length=512, description='模型 ID')
    input_price: Decimal = Field(default=Decimal(0), ge=0, description='输入 token 每百万价格')
    output_price: Decimal = Field(default=Decimal(0), ge=0, description='输出 token 每百万价格')
    cache_read_price: Decimal = Field(default=Decimal(0), ge=0, description='缓存读取 token 每百万价格')
    cache_write_price: Decimal = Field(default=Decimal(0), ge=0, description='缓存写入 token 每百万价格')
    input_audio_price: Decimal = Field(default=Decimal(0), ge=0, description='音频输入 token 每百万价格')
    output_audio_price: Decimal = Field(default=Decimal(0), ge=0, description='音频输出 token 每百万价格')
    cache_audio_read_price: Decimal = Field(default=Decimal(0), ge=0, description='音频缓存读取 token 每百万价格')
    image_price: Decimal = Field(default=Decimal(0), ge=0, description='单张生成图片价格')
    time_windows: list[AIBuddyBillingPriceWindowParam] = Field(
        default_factory=list, description='峰谷价格时段，按顺序匹配先命中先生效'
    )
    context_tiers: list[AIBuddyBillingPriceTierParam] = Field(
        default_factory=list, description='上下文阶梯价格，按阈值升序生效'
    )
    effective_from: AwareDatetime | None = Field(None, description='价格生效时间，需携带时区偏移')
    effective_to: AwareDatetime | None = Field(None, description='价格失效时间，需携带时区偏移')

    @field_validator('context_tiers')
    @classmethod
    def validate_tiers(
        cls,
        value: list[AIBuddyBillingPriceTierParam],
    ) -> list[AIBuddyBillingPriceTierParam]:
        """按阈值去重并升序排列阶梯价"""
        tiers: dict[int, AIBuddyBillingPriceTierParam] = {}
        for tier in value:
            tiers.setdefault(tier.threshold, tier)
        return [tiers[threshold] for threshold in sorted(tiers)]

    @model_validator(mode='after')
    def validate_default_price(self) -> 'AIBuddyBillingPriceSchemaBase':
        """保底价必须同时使用供应商 ID 0 与模型 ID *"""
        default_provider = self.provider_id == DEFAULT_PRICE_PROVIDER_ID
        default_model = self.model_id == DEFAULT_PRICE_MODEL_ID
        if default_provider != default_model:
            raise ValueError('保底价必须同时使用供应商 ID 0 与模型 ID *')
        return self


class CreateAIBuddyBillingPriceParam(AIBuddyBillingPriceSchemaBase):
    """创建 AI Buddy 计费价格参数"""

    effective_from: AwareDatetime = Field(description='价格生效时间，需携带时区偏移')


class UpdateAIBuddyBillingPriceParam(SchemaBase):
    """更新 AI Buddy 计费价格参数"""

    input_price: Decimal = Field(default=Decimal(0), ge=0, description='输入 token 每百万价格')
    output_price: Decimal = Field(default=Decimal(0), ge=0, description='输出 token 每百万价格')
    cache_read_price: Decimal = Field(default=Decimal(0), ge=0, description='缓存读取 token 每百万价格')
    cache_write_price: Decimal = Field(default=Decimal(0), ge=0, description='缓存写入 token 每百万价格')
    input_audio_price: Decimal = Field(default=Decimal(0), ge=0, description='音频输入 token 每百万价格')
    output_audio_price: Decimal = Field(default=Decimal(0), ge=0, description='音频输出 token 每百万价格')
    cache_audio_read_price: Decimal = Field(default=Decimal(0), ge=0, description='音频缓存读取 token 每百万价格')
    image_price: Decimal = Field(default=Decimal(0), ge=0, description='单张生成图片价格')
    time_windows: list[AIBuddyBillingPriceWindowParam] = Field(default_factory=list, description='峰谷价格时段')
    context_tiers: list[AIBuddyBillingPriceTierParam] = Field(default_factory=list, description='上下文阶梯价格')
    effective_to: AwareDatetime | None = Field(None, description='价格失效时间，需携带时区偏移')


class GetAIBuddyBillingPriceDetail(AIBuddyBillingPriceSchemaBase):
    """AI Buddy 计费价格详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='价格 ID')
    currency: str = Field(description='计价币种')
    source: str = Field(description='价格来源')
    source_version: str | None = Field(None, description='价格来源版本')
    synced_at: datetime | None = Field(None, description='最近一次同步时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')

    @computed_field(description='是否为保底价')
    @property
    def is_default(self) -> bool:
        """是否为保底价"""
        return is_default_price(provider_id=self.provider_id, model_id=self.model_id)


class AIBuddyBillingPriceSyncParam(SchemaBase):
    """AI Buddy 价格同步参数"""

    provider_ids: list[int] | None = Field(None, description='供应商 ID 列表，空表示全部')
    model_ids: list[str] | None = Field(None, description='模型 ID 列表，空表示全部')
    overwrite_manual: bool = Field(False, description='是否覆盖人工修改过的价格')
    effective_from: AwareDatetime | None = Field(None, description='新价格生效时间，空表示当前时间')


class AIBuddyBillingPriceSyncFieldChange(SchemaBase):
    """AI Buddy 价格同步字段变化"""

    field: str = Field(description='价格字段')
    current: str | None = Field(None, description='当前值')
    next: str | None = Field(None, description='同步后的值')


class GetAIBuddyBillingPriceSyncItem(SchemaBase):
    """AI Buddy 价格同步明细"""

    provider_id: int = Field(description='供应商 ID')
    provider_name: str = Field(description='供应商名称')
    model_id: str = Field(description='模型 ID')
    status: AIBuddyBillingPriceSyncStatus = Field(description='同步状态')
    source_provider: str | None = Field(None, description='models.dev 命中的供应商')
    current_price_id: int | None = Field(None, description='当前生效价格 ID')
    changes: list[AIBuddyBillingPriceSyncFieldChange] = Field(default_factory=list, description='价格变化')
    missing_fields: list[str] = Field(default_factory=list, description='models.dev 未提供的价格字段')


class GetAIBuddyBillingPriceSyncDetail(SchemaBase):
    """AI Buddy 价格同步结果"""

    catalog_version: str = Field(description='models.dev 目录版本')
    scanned: int = Field(description='扫描的模型数量')
    created: int = Field(description='新增价格数量，预览时为待新增数量')
    updated: int = Field(description='更新价格数量，预览时为待更新数量')
    skipped: int = Field(description='跳过数量，包含未收录、无报价、人工锁定与价格未变化')
    items: list[GetAIBuddyBillingPriceSyncItem] = Field(default_factory=list, description='同步明细')
