-- Reusable approval requests and immutable decision history.
CREATE TABLE IF NOT EXISTS approval_requests (
 approval_request_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 request_type VARCHAR(80) NOT NULL,
 resource_type VARCHAR(80) NOT NULL,
 resource_id VARCHAR(100) NOT NULL,
 requested_by BIGINT UNSIGNED NOT NULL,
 status ENUM('PENDING','APPROVED','REJECTED','CANCELLED') NOT NULL DEFAULT 'PENDING',
 current_step SMALLINT UNSIGNED NOT NULL DEFAULT 1,
 request_reason TEXT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 completed_at DATETIME NULL,
 INDEX idx_approval_resource (resource_type,resource_id,status),
 INDEX idx_approval_requester (requested_by,status,created_at),
 CONSTRAINT fk_approval_requester FOREIGN KEY (requested_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS approval_steps (
 approval_step_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 approval_request_id BIGINT UNSIGNED NOT NULL,
 step_number SMALLINT UNSIGNED NOT NULL,
 approver_employee_id BIGINT UNSIGNED NOT NULL,
 decision ENUM('PENDING','APPROVED','REJECTED','SKIPPED') NOT NULL DEFAULT 'PENDING',
 decision_comment TEXT NULL,
 decided_at DATETIME NULL,
 UNIQUE KEY uq_approval_step_approver (approval_request_id,step_number,approver_employee_id),
 INDEX idx_approval_inbox (approver_employee_id,decision),
 CONSTRAINT fk_approval_step_request FOREIGN KEY (approval_request_id) REFERENCES approval_requests(approval_request_id),
 CONSTRAINT fk_approval_step_approver FOREIGN KEY (approver_employee_id) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS approval_history (
 approval_history_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 approval_request_id BIGINT UNSIGNED NOT NULL,
 actor_employee_id BIGINT UNSIGNED NOT NULL,
 action_key VARCHAR(40) NOT NULL,
 comment TEXT NULL,
 occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_approval_history (approval_request_id,occurred_at),
 CONSTRAINT fk_approval_history_request FOREIGN KEY (approval_request_id) REFERENCES approval_requests(approval_request_id),
 CONSTRAINT fk_approval_history_actor FOREIGN KEY (actor_employee_id) REFERENCES employees(employee_id)
);
