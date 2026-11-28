-- Admin-configurable Service Request priorities; existing request values are preserved.
CREATE TABLE IF NOT EXISTS service_request_priorities (
    priority_key VARCHAR(30) NOT NULL,
    priority_label VARCHAR(60) NOT NULL,
    sort_order SMALLINT UNSIGNED NOT NULL DEFAULT 100,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (priority_key),
    UNIQUE KEY uq_service_request_priority_label (priority_label),
    KEY idx_service_request_priorities_active_order (is_active, sort_order, priority_key),
    CONSTRAINT fk_service_request_priority_creator
        FOREIGN KEY (created_by) REFERENCES employees(employee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO service_request_priorities
    (priority_key, priority_label, sort_order, is_active)
VALUES
    ('LOW', 'Low', 10, TRUE),
    ('MEDIUM', 'Medium', 20, TRUE),
    ('HIGH', 'High', 30, TRUE),
    ('CRITICAL', 'Critical', 40, TRUE)
ON DUPLICATE KEY UPDATE
    priority_label=VALUES(priority_label),
    sort_order=VALUES(sort_order);

ALTER TABLE service_requests
    MODIFY priority VARCHAR(30) NOT NULL,
    ADD CONSTRAINT fk_service_request_priority
        FOREIGN KEY (priority) REFERENCES service_request_priorities(priority_key);

INSERT INTO permissions (permission_key, description)
VALUES (
    'service_request.priorities.manage',
    'Create and configure Service Request priority levels'
)
ON DUPLICATE KEY UPDATE description=VALUES(description);

-- Preserve administration access for roles that already manage request categories.
INSERT IGNORE INTO role_permissions (role_id, permission_id)
SELECT existing.role_id, priority_permission.permission_id
FROM role_permissions existing
JOIN permissions category_permission
  ON category_permission.permission_id=existing.permission_id
 AND category_permission.permission_key='service_request.categories.manage'
JOIN permissions priority_permission
  ON priority_permission.permission_key='service_request.priorities.manage';
