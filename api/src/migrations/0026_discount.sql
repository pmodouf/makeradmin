ALTER TABLE `membership_members` ADD COLUMN `discount_id` INT UNSIGNED DEFAULT NULL;
ALTER TABLE `membership_members` ADD INDEX `index_discount_id` (`discount_id`);


CREATE TABLE IF NOT EXISTS `webshop_discount`(
    `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
    `description` varchar(255) COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
    `stripe_discount_id`varchar(64) COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
    `discount_percentage` DECIMAL(5,2) NOT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `deleted_at` DATETIME DEFAULT NULL,
    PRIMARY KEY (`id`),
    KEY `stripe_discount_id` (`stripe_discount_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
ALTER TABLE `membership_members` ADD CONSTRAINT `discount_id_constraint` FOREIGN KEY (`discount_id`) REFERENCES `webshop_discount` (`id`);
