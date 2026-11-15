delete from sys_menu
where name in (
    'AIBuddyBillingUsageManage',
    'AIBuddyBillingPriceManage',
    'AIBuddyBillingAccountManage',
    'AIBuddyBillingBudgetManage',
    'ReconcileAIBuddyBilling',
    'AddAIBuddyBillingPrice',
    'EditAIBuddyBillingPrice',
    'DeleteAIBuddyBillingPrice',
    'SyncAIBuddyBillingPrice',
    'QueryAIBuddyBillingAccount',
    'RechargeAIBuddyBilling',
    'AdjustAIBuddyBilling',
    'AddAIBuddyBillingBudget',
    'EditAIBuddyBillingBudget',
    'DeleteAIBuddyBillingBudget'
);

delete from sys_menu where name = 'PluginAIBuddyBilling';

drop table if exists ai_buddy_billing_budget;
drop table if exists ai_buddy_billing_transaction;
drop table if exists ai_buddy_billing_ledger;
drop table if exists ai_buddy_billing_account;
drop table if exists ai_buddy_billing_price;

select setval(pg_get_serial_sequence('sys_menu', 'id'), coalesce(max(id), 0) + 1, true) from sys_menu;
