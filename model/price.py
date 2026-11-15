from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class AIBuddyBillingPrice(Base):
    """AI Buddy 模型价格表"""

    __tablename__ = 'ai_buddy_billing_price'
    __table_args__ = (
        sa.UniqueConstraint(
            'provider_id',
            'model_id',
            'effective_from',
            'deleted',
            name='uk_ai_buddy_billing_price_provider_model_effective_deleted',
        ),
        sa.Index(
            'uk_ai_buddy_billing_price_active',
            'provider_id',
            'model_id',
            unique=True,
            postgresql_where=sa.text('effective_to IS NULL AND deleted = 0'),
        ),
        {'comment': 'AI Buddy 模型价格'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    provider_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='AI Buddy 供应商 ID')
    model_id: Mapped[str] = mapped_column(sa.String(512), index=True, comment='AI Buddy 模型 ID')
    effective_from: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True, comment='价格生效时间')
    input_price: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8), default=Decimal(0), comment='输入 token 每百万价格')
    output_price: Mapped[Decimal] = mapped_column(
        sa.Numeric(20, 8), default=Decimal(0), comment='输出 token 每百万价格'
    )
    cache_read_price: Mapped[Decimal] = mapped_column(
        sa.Numeric(20, 8), default=Decimal(0), comment='缓存读取 token 每百万价格'
    )
    cache_write_price: Mapped[Decimal] = mapped_column(
        sa.Numeric(20, 8), default=Decimal(0), comment='缓存写入 token 每百万价格'
    )
    input_audio_price: Mapped[Decimal] = mapped_column(
        sa.Numeric(20, 8), default=Decimal(0), comment='音频输入 token 每百万价格'
    )
    output_audio_price: Mapped[Decimal] = mapped_column(
        sa.Numeric(20, 8), default=Decimal(0), comment='音频输出 token 每百万价格'
    )
    cache_audio_read_price: Mapped[Decimal] = mapped_column(
        sa.Numeric(20, 8), default=Decimal(0), comment='音频缓存读取 token 每百万价格'
    )
    image_price: Mapped[Decimal] = mapped_column(sa.Numeric(20, 8), default=Decimal(0), comment='单张生成图片价格')
    currency: Mapped[str] = mapped_column(sa.String(16), default='USD', comment='计价币种，固定为 USD')
    time_windows: Mapped[list[dict]] = mapped_column(
        JSONB,
        default_factory=list,
        server_default=sa.text("'[]'::jsonb"),
        comment='峰谷价格时段，命中后的倍率作用于 token 费用',
    )
    context_tiers: Mapped[list[dict]] = mapped_column(
        JSONB,
        default_factory=list,
        server_default=sa.text("'[]'::jsonb"),
        comment='上下文阶梯价格，提示词 token 超过阈值后覆盖基础单价',
    )
    source: Mapped[str] = mapped_column(
        sa.String(32), default='manual', comment='价格来源（manual 人工/models.dev 目录）'
    )
    source_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='价格来源版本')
    synced_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=None, comment='最近一次同步时间'
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=None, index=True, comment='价格失效时间'
    )
