-- In-app notification inbox and transactional delivery outbox.
CREATE TABLE IF NOT EXISTS notifications (
 notification_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 recipient_employee_id BIGINT UNSIGNED NOT NULL,
 notification_type VARCHAR(80) NOT NULL,
 title VARCHAR(200) NOT NULL,
 body TEXT NOT NULL,
 target_type VARCHAR(80) NULL,
 target_id VARCHAR(100) NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 read_at DATETIME NULL,
 INDEX idx_notification_inbox (recipient_employee_id,read_at,created_at),
 CONSTRAINT fk_notification_recipient FOREIGN KEY (recipient_employee_id) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS notification_outbox (
 outbox_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 notification_id BIGINT UNSIGNED NOT NULL,
 channel ENUM('EMAIL','IN_APP') NOT NULL DEFAULT 'IN_APP',
 delivery_status ENUM('PENDING','PROCESSING','SENT','FAILED','DEAD') NOT NULL DEFAULT 'PENDING',
 attempt_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
 available_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 locked_at DATETIME NULL,
 last_error VARCHAR(500) NULL,
 sent_at DATETIME NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_outbox_ready (delivery_status,available_at),
 CONSTRAINT fk_outbox_notification FOREIGN KEY (notification_id) REFERENCES notifications(notification_id)
);
