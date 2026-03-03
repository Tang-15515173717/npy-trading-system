-- 支付订单表
CREATE TABLE IF NOT EXISTS `payment_orders` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `order_no` VARCHAR(64) NOT NULL UNIQUE COMMENT '商户订单号',
    `tenant_id` INT NOT NULL COMMENT '租户ID',
    `user_id` INT NOT NULL COMMENT '用户ID',
    `plan_type` VARCHAR(20) NOT NULL COMMENT '套餐类型',
    `amount` INT NOT NULL COMMENT '金额（分）',
    `body` VARCHAR(200) NOT NULL COMMENT '商品描述',
    `pay_type` VARCHAR(20) NOT NULL COMMENT '支付类型: alipay/wechat',
    `pay_url` TEXT COMMENT '支付链接',
    `transaction_id` VARCHAR(64) COMMENT '第三方订单号',
    `status` VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '订单状态: pending/paid/failed/closed/refunded',
    `paid_at` DATETIME COMMENT '支付时间',
    `created_at` DATETIME NOT NULL COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL COMMENT '更新时间',
    INDEX `idx_order_no` (`order_no`),
    INDEX `idx_tenant_id` (`tenant_id`),
    INDEX `idx_status` (`status`),
    INDEX `idx_created_at` (`created_at`),
    FOREIGN KEY (`tenant_id`) REFERENCES `tenants`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付订单表';

-- 支付记录表
CREATE TABLE IF NOT EXISTS `payment_records` (
    `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '主键ID',
    `order_no` VARCHAR(64) NOT NULL COMMENT '商户订单号',
    `tenant_id` INT NOT NULL COMMENT '租户ID',
    `user_id` INT NOT NULL COMMENT '用户ID',
    `pay_type` VARCHAR(20) NOT NULL COMMENT '支付类型',
    `transaction_id` VARCHAR(64) NOT NULL COMMENT '第三方订单号',
    `amount` INT NOT NULL COMMENT '金额（分）',
    `plan_type` VARCHAR(20) NOT NULL COMMENT '购买的套餐类型',
    `status` VARCHAR(20) NOT NULL DEFAULT 'success' COMMENT '状态: success/failed/refunded',
    `notify_data` TEXT COMMENT '回调原始数据',
    `created_at` DATETIME NOT NULL COMMENT '创建时间',
    INDEX `idx_order_no` (`order_no`),
    INDEX `idx_tenant_id` (`tenant_id`),
    INDEX `idx_created_at` (`created_at`),
    FOREIGN KEY (`tenant_id`) REFERENCES `tenants`(`id`) ON DELETE CASCADE,
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付记录表';
