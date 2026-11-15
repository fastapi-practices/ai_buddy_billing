insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values (2147098509659216100, 'ai-buddy-billing.menu', 'PluginAIBuddyBilling', '/plugins/ai-buddy-billing', 14, 'material-symbols:payments-outline', 0, null, null, 1, 1, 1, '', null, null, now(), null);

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(2147098509659216101, 'ai-buddy-billing.usage.title', 'AIBuddyBillingUsageManage', '/plugins/ai-buddy-billing/usage', 1, 'carbon:chart-line', 1, '/plugins/ai-buddy-billing/views/usage/index', null, 1, 1, 1, '', null, 2147098509659216100, now(), null),
(2147098509659216102, 'ai-buddy-billing.price.title', 'AIBuddyBillingPriceManage', '/plugins/ai-buddy-billing/price', 2, 'carbon:currency-dollar', 1, '/plugins/ai-buddy-billing/views/price/index', null, 1, 1, 1, '', null, 2147098509659216100, now(), null),
(2147098509659216103, 'ai-buddy-billing.account.title', 'AIBuddyBillingAccountManage', '/plugins/ai-buddy-billing/account', 3, 'carbon:wallet', 1, '/plugins/ai-buddy-billing/views/account/index', null, 1, 1, 1, '', null, 2147098509659216100, now(), null),
(2147098509659216104, 'ai-buddy-billing.budget.title', 'AIBuddyBillingBudgetManage', '/plugins/ai-buddy-billing/budget', 4, 'carbon:meter', 1, '/plugins/ai-buddy-billing/views/budget/index', null, 1, 1, 1, '', null, 2147098509659216100, now(), null);

insert into sys_menu (id, title, name, path, sort, icon, type, component, perms, status, display, cache, link, remark, parent_id, created_time, updated_time)
values
(2147098509659216105, '用量归集', 'ReconcileAIBuddyBilling', null, 0, null, 2, null, 'ai:billing:reconcile', 1, 0, 1, '', null, 2147098509659216101, now(), null),
(2147098509659216106, '新增价格', 'AddAIBuddyBillingPrice', null, 0, null, 2, null, 'ai:billing:price:add', 1, 0, 1, '', null, 2147098509659216102, now(), null),
(2147098509659216107, '修改价格', 'EditAIBuddyBillingPrice', null, 1, null, 2, null, 'ai:billing:price:edit', 1, 0, 1, '', null, 2147098509659216102, now(), null),
(2147098509659216108, '删除价格', 'DeleteAIBuddyBillingPrice', null, 2, null, 2, null, 'ai:billing:price:del', 1, 0, 1, '', null, 2147098509659216102, now(), null),
(2147098509659216115, '同步 models.dev 价格', 'SyncAIBuddyBillingPrice', null, 3, null, 2, null, 'ai:billing:price:sync', 1, 0, 1, '', null, 2147098509659216102, now(), null),
(2147098509659216109, '查询计费账户', 'QueryAIBuddyBillingAccount', null, 0, null, 2, null, 'ai:billing:account:list', 1, 0, 1, '', null, 2147098509659216103, now(), null),
(2147098509659216110, '账户充值', 'RechargeAIBuddyBilling', null, 1, null, 2, null, 'ai:billing:account:recharge', 1, 0, 1, '', null, 2147098509659216103, now(), null),
(2147098509659216111, '余额调整', 'AdjustAIBuddyBilling', null, 2, null, 2, null, 'ai:billing:account:adjust', 1, 0, 1, '', null, 2147098509659216103, now(), null),
(2147098509659216112, '新增预算', 'AddAIBuddyBillingBudget', null, 0, null, 2, null, 'ai:billing:budget:add', 1, 0, 1, '', null, 2147098509659216104, now(), null),
(2147098509659216113, '修改预算', 'EditAIBuddyBillingBudget', null, 1, null, 2, null, 'ai:billing:budget:edit', 1, 0, 1, '', null, 2147098509659216104, now(), null),
(2147098509659216114, '删除预算', 'DeleteAIBuddyBillingBudget', null, 2, null, 2, null, 'ai:billing:budget:del', 1, 0, 1, '', null, 2147098509659216104, now(), null);
