-- 做什么：创建 MallPilot 业务数据库。
-- 为什么：方便在应用启动前独立初始化 MySQL 库。
CREATE DATABASE IF NOT EXISTS `mallpilot`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE `mallpilot`;

-- 做什么：创建商品表。
-- 为什么：承载导购搜索、推荐、比价和库存查询所需的真实商品数据。
CREATE TABLE IF NOT EXISTS `products` (
  `product_id` VARCHAR(32) NOT NULL COMMENT '商品主键',
  `name` VARCHAR(128) NOT NULL COMMENT '商品名称',
  `category` VARCHAR(64) NOT NULL COMMENT '商品类目',
  `brand` VARCHAR(64) NOT NULL COMMENT '商品品牌',
  `price` DOUBLE NOT NULL COMMENT '商品售价',
  `original_price` DOUBLE NOT NULL COMMENT '商品原价',
  `stock` INT NOT NULL DEFAULT 0 COMMENT '库存数量',
  `rating` DOUBLE NOT NULL DEFAULT 0 COMMENT '商品评分',
  `sales_count` INT NOT NULL DEFAULT 0 COMMENT '销量',
  `tags` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '商品标签',
  `summary` TEXT NOT NULL COMMENT '商品简介',
  `specs_json` TEXT NOT NULL COMMENT '商品规格 JSON',
  `is_featured` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否主推商品',
  PRIMARY KEY (`product_id`),
  KEY `idx_products_name` (`name`),
  KEY `idx_products_category` (`category`),
  KEY `idx_products_price` (`price`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品表';

-- 做什么：创建促销活动表。
-- 为什么：承载优惠券、活动和预算相关的促销事实。
CREATE TABLE IF NOT EXISTS `promotions` (
  `promotion_id` VARCHAR(32) NOT NULL COMMENT '活动主键',
  `title` VARCHAR(128) NOT NULL COMMENT '活动标题',
  `description` TEXT NOT NULL COMMENT '活动描述',
  `applies_to_category` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '适用类目',
  `applies_to_product_id` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '适用商品 ID',
  `coupon_code` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '优惠券码',
  `discount_label` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '折扣标签',
  `min_spend` DOUBLE NOT NULL DEFAULT 0 COMMENT '最低消费门槛',
  `starts_at` DATETIME NOT NULL COMMENT '开始时间',
  `ends_at` DATETIME NOT NULL COMMENT '结束时间',
  `status` VARCHAR(32) NOT NULL DEFAULT 'active' COMMENT '活动状态',
  `priority` INT NOT NULL DEFAULT 99 COMMENT '优先级',
  PRIMARY KEY (`promotion_id`),
  KEY `idx_promotions_category` (`applies_to_category`),
  KEY `idx_promotions_product` (`applies_to_product_id`),
  KEY `idx_promotions_coupon` (`coupon_code`),
  KEY `idx_promotions_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='促销活动表';

-- 做什么：创建订单表。
-- 为什么：承载订单主数据，供订单、支付、物流和售后场景复用。
CREATE TABLE IF NOT EXISTS `orders` (
  `order_id` VARCHAR(32) NOT NULL COMMENT '订单主键',
  `user_id` VARCHAR(64) NOT NULL COMMENT '用户标识',
  `status` VARCHAR(32) NOT NULL COMMENT '订单状态',
  `total_amount` DOUBLE NOT NULL DEFAULT 0 COMMENT '订单总金额',
  `payment_amount` DOUBLE NOT NULL DEFAULT 0 COMMENT '实付金额',
  `payment_method` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '支付方式',
  `shipping_status` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '物流状态',
  `shipping_company` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '物流公司',
  `tracking_no` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '运单号',
  `created_at` DATETIME NOT NULL COMMENT '下单时间',
  `paid_at` DATETIME NULL COMMENT '支付时间',
  `shipped_at` DATETIME NULL COMMENT '发货时间',
  `delivered_at` DATETIME NULL COMMENT '签收时间',
  `coupon_code` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '优惠券码',
  `address_summary` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '地址摘要',
  `invoice_title` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '发票抬头',
  `after_sales_status` VARCHAR(32) NOT NULL DEFAULT '无' COMMENT '售后状态',
  PRIMARY KEY (`order_id`),
  KEY `idx_orders_user` (`user_id`),
  KEY `idx_orders_status` (`status`),
  KEY `idx_orders_shipping_status` (`shipping_status`),
  KEY `idx_orders_created_at` (`created_at`),
  KEY `idx_orders_coupon` (`coupon_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单表';

-- 做什么：创建订单明细表。
-- 为什么：承载一个订单下的多商品快照。
CREATE TABLE IF NOT EXISTS `order_items` (
  `id` INT NOT NULL AUTO_INCREMENT COMMENT '明细主键',
  `order_id` VARCHAR(32) NOT NULL COMMENT '订单编号',
  `product_id` VARCHAR(32) NOT NULL COMMENT '商品编号',
  `product_name_snapshot` VARCHAR(128) NOT NULL COMMENT '商品名称快照',
  `sku_snapshot` VARCHAR(128) NOT NULL DEFAULT '' COMMENT '规格快照',
  `quantity` INT NOT NULL DEFAULT 1 COMMENT '购买数量',
  `unit_price` DOUBLE NOT NULL DEFAULT 0 COMMENT '成交单价',
  `item_index` INT NOT NULL DEFAULT 1 COMMENT '明细顺序',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_order_items_order_index` (`order_id`, `item_index`),
  KEY `idx_order_items_product` (`product_id`),
  CONSTRAINT `fk_order_items_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`order_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_order_items_product` FOREIGN KEY (`product_id`) REFERENCES `products` (`product_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='订单明细表';

-- 做什么：创建支付交易表。
-- 为什么：承载支付、退款等交易流水，满足真实交易记录查询。
CREATE TABLE IF NOT EXISTS `payment_transactions` (
  `transaction_id` VARCHAR(40) NOT NULL COMMENT '交易流水主键',
  `order_id` VARCHAR(32) NOT NULL COMMENT '订单编号',
  `user_id` VARCHAR(64) NOT NULL COMMENT '用户标识',
  `transaction_type` VARCHAR(32) NOT NULL COMMENT '交易阶段',
  `channel` VARCHAR(32) NOT NULL DEFAULT '' COMMENT '交易渠道',
  `amount` DOUBLE NOT NULL DEFAULT 0 COMMENT '交易金额',
  `status` VARCHAR(32) NOT NULL COMMENT '交易状态',
  `transacted_at` DATETIME NOT NULL COMMENT '交易时间',
  `channel_reference` VARCHAR(128) NOT NULL DEFAULT '' COMMENT '渠道流水号',
  `note` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '交易备注',
  PRIMARY KEY (`transaction_id`),
  KEY `idx_payment_transactions_order` (`order_id`),
  KEY `idx_payment_transactions_user` (`user_id`),
  KEY `idx_payment_transactions_type` (`transaction_type`),
  KEY `idx_payment_transactions_status` (`status`),
  KEY `idx_payment_transactions_time` (`transacted_at`),
  CONSTRAINT `fk_payment_transactions_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`order_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='支付交易表';

-- 做什么：创建物流事件表。
-- 为什么：承载物流轨迹节点，支持物流和订单时间线查询。
CREATE TABLE IF NOT EXISTS `logistics_events` (
  `event_id` VARCHAR(40) NOT NULL COMMENT '物流事件主键',
  `order_id` VARCHAR(32) NOT NULL COMMENT '订单编号',
  `event_time` DATETIME NOT NULL COMMENT '事件时间',
  `status` VARCHAR(64) NOT NULL COMMENT '事件状态',
  `detail` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '事件详情',
  PRIMARY KEY (`event_id`),
  KEY `idx_logistics_events_order` (`order_id`),
  KEY `idx_logistics_events_time` (`event_time`),
  KEY `idx_logistics_events_status` (`status`),
  CONSTRAINT `fk_logistics_events_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`order_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='物流事件表';

-- 做什么：创建售后工单表。
-- 为什么：承载退款、换货、投诉和咨询等售后记录。
CREATE TABLE IF NOT EXISTS `after_sales_tickets` (
  `ticket_id` VARCHAR(40) NOT NULL COMMENT '售后工单主键',
  `order_id` VARCHAR(32) NOT NULL COMMENT '订单编号',
  `user_id` VARCHAR(64) NOT NULL COMMENT '用户标识',
  `ticket_type` VARCHAR(32) NOT NULL COMMENT '工单类型',
  `status` VARCHAR(32) NOT NULL COMMENT '工单状态',
  `reason` VARCHAR(255) NOT NULL DEFAULT '' COMMENT '售后原因',
  `refund_amount` DOUBLE NOT NULL DEFAULT 0 COMMENT '退款金额',
  `requested_at` DATETIME NOT NULL COMMENT '申请时间',
  `updated_at` DATETIME NOT NULL COMMENT '更新时间',
  `resolution_note` TEXT NOT NULL COMMENT '处理说明',
  PRIMARY KEY (`ticket_id`),
  KEY `idx_after_sales_order` (`order_id`),
  KEY `idx_after_sales_user` (`user_id`),
  KEY `idx_after_sales_type` (`ticket_type`),
  KEY `idx_after_sales_status` (`status`),
  KEY `idx_after_sales_updated` (`updated_at`),
  CONSTRAINT `fk_after_sales_order` FOREIGN KEY (`order_id`) REFERENCES `orders` (`order_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='售后工单表';

-- 做什么：创建服务政策表。
-- 为什么：承载退款、换货、发票和投诉等规则文本。
CREATE TABLE IF NOT EXISTS `service_policies` (
  `policy_id` VARCHAR(32) NOT NULL COMMENT '政策主键',
  `policy_type` VARCHAR(32) NOT NULL COMMENT '政策类型',
  `title` VARCHAR(128) NOT NULL COMMENT '政策标题',
  `content` TEXT NOT NULL COMMENT '政策内容',
  `applies_to_category` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '适用类目',
  `applies_to_status` VARCHAR(64) NOT NULL DEFAULT '' COMMENT '适用状态',
  `priority` INT NOT NULL DEFAULT 99 COMMENT '优先级',
  PRIMARY KEY (`policy_id`),
  KEY `idx_service_policies_type` (`policy_type`),
  KEY `idx_service_policies_category` (`applies_to_category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='服务政策表';
