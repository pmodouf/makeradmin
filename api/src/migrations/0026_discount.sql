ALTER TABLE `membership_members` ADD COLUMN `price_level_id` INT UNSIGNED DEFAULT NULL;
ALTER TABLE `membership_members` ADD INDEX `index_price_level_id` (`price_level_id`);



CREATE TABLE IF NOT EXISTS `discounts`(
    `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `description` varchar(255) COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
    `price_level_id` int(10) unsigned NOT NULL,
    `discount_percentage` DECIMAL(5,2) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted_at` DATETIME DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `discount_price_level_id` (`price_level_id`),
    CONSTRAINT `discount_price_level_id_foreign` FOREIGN KEY (`price_level_id`) REFERENCES `membership_members` (`price_level_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
