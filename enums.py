from backend.common.enums import StrEnum


class AIBuddyBillingTransactionType(StrEnum):
    """AI Buddy 计费账户流水类型"""

    recharge = 'recharge'
    consume = 'consume'
    adjust = 'adjust'
    refund = 'refund'


class AIBuddyBillingLedgerStatus(StrEnum):
    """AI Buddy 计费账本状态"""

    billed = 'billed'
    """已按价格结算"""
    provider_cost = 'provider_cost'
    """仅记录供应商成本，未结算扣费"""
    unpriced = 'unpriced'
    """没有价格也没有供应商成本"""


class AIBuddyBillingPriceSource(StrEnum):
    """AI Buddy 价格来源"""

    manual = 'manual'
    models_dev = 'models.dev'


class AIBuddyBillingPriceSyncStatus(StrEnum):
    """AI Buddy 价格同步状态"""

    create = 'create'
    update = 'update'
    unchanged = 'unchanged'
    manual_locked = 'manual_locked'
    future_price = 'future_price'
    not_found = 'not_found'
    no_cost = 'no_cost'


class AIBuddyBillingBudgetWindow(StrEnum):
    """AI Buddy 计费预算窗口"""

    run = 'run'
    conversation = 'conversation'
    day = 'day'
    month = 'month'
    total = 'total'
