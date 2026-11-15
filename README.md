# AI Buddy Billing

为 AI Buddy 提供模型价格（models.dev 同步、保底价、峰谷价、上下文阶梯价）、用量账本、用户余额、充值调整、消费预算、账单归集和余额拦截

## 插件类型

- 应用级插件

## 配置说明

插件目录下 `plugin.toml` 的 `[settings]` 中包含以下内容：

```toml
[settings]
AI_BUDDY_BILLING_BALANCE_GUARD_ENABLED = true
AI_BUDDY_BILLING_BALANCE_MIN_USD = 0
AI_BUDDY_BILLING_BALANCE_GUARD_SKIP_SUPERUSER = false
AI_BUDDY_BILLING_DISPLAY_CURRENCY = "USD"
AI_BUDDY_BILLING_DISPLAY_CURRENCY_SYMBOL = "$"
AI_BUDDY_BILLING_DISPLAY_CURRENCY_RATE = 1
AI_BUDDY_BILLING_DISPLAY_CURRENCY_DECIMALS = 2
```

当前项目的 `backend/core/conf.py` 已包含以下字段：

```python
##################################################
# [ Plugin ] ai_buddy_billing
##################################################
# 基础配置（in plugin.toml）
AI_BUDDY_BILLING_BALANCE_GUARD_ENABLED: bool = True
AI_BUDDY_BILLING_BALANCE_MIN_USD: Decimal = Decimal(0)
AI_BUDDY_BILLING_BALANCE_GUARD_SKIP_SUPERUSER: bool = False
AI_BUDDY_BILLING_DISPLAY_CURRENCY: str = 'USD'
AI_BUDDY_BILLING_DISPLAY_CURRENCY_SYMBOL: str = '$'
AI_BUDDY_BILLING_DISPLAY_CURRENCY_RATE: Decimal = Decimal(1)
AI_BUDDY_BILLING_DISPLAY_CURRENCY_DECIMALS: int = 2
```

## 配置项说明

- `AI_BUDDY_BILLING_BALANCE_GUARD_ENABLED`：是否在模型请求前校验计费余额，关闭后余额不足仍会继续运行
- `AI_BUDDY_BILLING_BALANCE_MIN_USD`：允许的最低余额，单位为美元，余额不高于该值时阻断
- `AI_BUDDY_BILLING_BALANCE_GUARD_SKIP_SUPERUSER`：是否跳过超级管理员的余额校验
- `AI_BUDDY_BILLING_DISPLAY_CURRENCY`：金额展示币种，所有金额始终按美元结算与存储，该配置只影响展示
- `AI_BUDDY_BILLING_DISPLAY_CURRENCY_SYMBOL`：展示币种符号
- `AI_BUDDY_BILLING_DISPLAY_CURRENCY_RATE`：1 美元可兑换的展示币种数量
- `AI_BUDDY_BILLING_DISPLAY_CURRENCY_DECIMALS`：展示小数位

## 使用方式

1. 安装并启用 AI Buddy 插件和本插件后重启后端服务，系统会创建独立的 AI Buddy 计费菜单及用量、价格、账户和预算子菜单
2. 在模型价格页先预览 models.dev 报价差异，确认后再应用同步，随后按需调整价格、峰谷时段与上下文阶梯价
3. 同一供应商与模型只能存在一条未失效价格，已存在时请直接修改，重复添加会被拒绝
4. 配置保底价（供应商 ID `0`、模型 ID `*`）后，未匹配到模型价格的用量统一按保底价结算，已配置模型价格的模型优先使用自身价格；既无模型价格也无保底价时不扣费
5. 通过账户列表查询用户余额，并按用户充值或调整余额
6. 按用户和运行、对话、日、月或总使用窗口配置美元与 token 上限
7. 由后台任务定时归集 AI Buddy 消息中的模型用量，也可以手动触发归集
8. 查询用户余额、计费流水、用量账本、消费预算和按时间范围汇总的费用

## 卸载说明

- 卸载插件后清理 AI Buddy Billing 目录菜单及其子菜单、权限、消费预算和计费数据表
- 如业务已依赖余额、流水或账单数据，请先导出并完成结算
- 清理前端页面、定时归集任务和相关业务集成

## 联系方式

- 作者：`wu-clan`
- 反馈方式：提交 Issue 或 PR
