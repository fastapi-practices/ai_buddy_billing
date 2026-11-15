do $$
declare
    billing_menu_id bigint;
    billing_usage_menu_id bigint;
    billing_price_menu_id bigint;
    billing_account_menu_id bigint;
    billing_budget_menu_id bigint;
begin
    insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
    values ('ai-buddy-billing.menu', 'PluginAIBuddyBilling', '/plugins/ai-buddy-billing', 14, 'material-symbols:payments-outline', 0, null, null, 1, 1, 1, '', null, null, now(), null)
    returning id into billing_menu_id;

    insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
    values ('ai-buddy-billing.usage.title', 'AIBuddyBillingUsageManage', '/plugins/ai-buddy-billing/usage', 1, 'carbon:chart-line', 1, '/plugins/ai-buddy-billing/views/usage/index', null, 1, 1, 1, '', null, billing_menu_id, now(), null)
    returning id into billing_usage_menu_id;

    insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
    values ('ai-buddy-billing.price.title', 'AIBuddyBillingPriceManage', '/plugins/ai-buddy-billing/price', 2, 'carbon:currency-dollar', 1, '/plugins/ai-buddy-billing/views/price/index', null, 1, 1, 1, '', null, billing_menu_id, now(), null)
    returning id into billing_price_menu_id;

    insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
    values ('ai-buddy-billing.account.title', 'AIBuddyBillingAccountManage', '/plugins/ai-buddy-billing/account', 3, 'carbon:wallet', 1, '/plugins/ai-buddy-billing/views/account/index', null, 1, 1, 1, '', null, billing_menu_id, now(), null)
    returning id into billing_account_menu_id;

    insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
    values ('ai-buddy-billing.budget.title', 'AIBuddyBillingBudgetManage', '/plugins/ai-buddy-billing/budget', 4, 'carbon:meter', 1, '/plugins/ai-buddy-billing/views/budget/index', null, 1, 1, 1, '', null, billing_menu_id, now(), null)
    returning id into billing_budget_menu_id;

    insert into sys_menu (title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
    values
    ('用量归集', 'ReconcileAIBuddyBilling', null, 0, null, 2, null, 'ai:billing:reconcile', 1, 0, 1, '', null, billing_usage_menu_id, now(), null),
    ('新增价格', 'AddAIBuddyBillingPrice', null, 0, null, 2, null, 'ai:billing:price:add', 1, 0, 1, '', null, billing_price_menu_id, now(), null),
    ('修改价格', 'EditAIBuddyBillingPrice', null, 1, null, 2, null, 'ai:billing:price:edit', 1, 0, 1, '', null, billing_price_menu_id, now(), null),
    ('删除价格', 'DeleteAIBuddyBillingPrice', null, 2, null, 2, null, 'ai:billing:price:del', 1, 0, 1, '', null, billing_price_menu_id, now(), null),
    ('同步 models.dev 价格', 'SyncAIBuddyBillingPrice', null, 3, null, 2, null, 'ai:billing:price:sync', 1, 0, 1, '', null, billing_price_menu_id, now(), null),
    ('查询计费账户', 'QueryAIBuddyBillingAccount', null, 0, null, 2, null, 'ai:billing:account:list', 1, 0, 1, '', null, billing_account_menu_id, now(), null),
    ('账户充值', 'RechargeAIBuddyBilling', null, 1, null, 2, null, 'ai:billing:account:recharge', 1, 0, 1, '', null, billing_account_menu_id, now(), null),
    ('余额调整', 'AdjustAIBuddyBilling', null, 2, null, 2, null, 'ai:billing:account:adjust', 1, 0, 1, '', null, billing_account_menu_id, now(), null),
    ('新增预算', 'AddAIBuddyBillingBudget', null, 0, null, 2, null, 'ai:billing:budget:add', 1, 0, 1, '', null, billing_budget_menu_id, now(), null),
    ('修改预算', 'EditAIBuddyBillingBudget', null, 1, null, 2, null, 'ai:billing:budget:edit', 1, 0, 1, '', null, billing_budget_menu_id, now(), null),
    ('删除预算', 'DeleteAIBuddyBillingBudget', null, 2, null, 2, null, 'ai:billing:budget:del', 1, 0, 1, '', null, billing_budget_menu_id, now(), null);
end $$;

select setval(pg_get_serial_sequence('sys_menu', 'id'), coalesce(max(id), 0) + 1, true) from sys_menu;
