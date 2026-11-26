-- Configurable priority-based incident SLA targets (minutes, 24x7 baseline).
CREATE TABLE IF NOT EXISTS incident_sla_policies (
 sla_policy_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 priority ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL UNIQUE,
 first_response_minutes INT UNSIGNED NOT NULL,
 resolution_minutes INT UNSIGNED NOT NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
