-- Basic service request workflow; deliberately excludes catalog, approvals, SLA and fulfillment automation.
CREATE TABLE IF NOT EXISTS service_request_categories (
 category_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 category_name VARCHAR(120) NOT NULL UNIQUE,
 description VARCHAR(500) NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 CONSTRAINT fk_service_request_category_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS service_requests (
 request_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 request_number VARCHAR(40) NOT NULL UNIQUE,
 title VARCHAR(240) NOT NULL,
 description MEDIUMTEXT NOT NULL,
 category_id BIGINT UNSIGNED NULL,
 requester_employee_id BIGINT UNSIGNED NOT NULL,
 assigned_employee_id BIGINT UNSIGNED NULL,
 assigned_team_id BIGINT UNSIGNED NULL,
 priority ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
 status ENUM('OPEN','IN_PROGRESS','ON_HOLD','COMPLETED','CANCELLED') NOT NULL DEFAULT 'OPEN',
 resolution_notes MEDIUMTEXT NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 completed_at DATETIME NULL,
 cancelled_at DATETIME NULL,
 INDEX idx_service_request_queue (status,priority,created_at),
 INDEX idx_service_request_requester (requester_employee_id,status),
 INDEX idx_service_request_team (assigned_team_id,status),
 CONSTRAINT fk_service_request_category FOREIGN KEY (category_id) REFERENCES service_request_categories(category_id),
 CONSTRAINT fk_service_request_requester FOREIGN KEY (requester_employee_id) REFERENCES employees(employee_id),
 CONSTRAINT fk_service_request_assignee FOREIGN KEY (assigned_employee_id) REFERENCES employees(employee_id),
 CONSTRAINT fk_service_request_team FOREIGN KEY (assigned_team_id) REFERENCES teams(team_id),
 CONSTRAINT fk_service_request_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS service_request_activity (
 activity_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 request_id BIGINT UNSIGNED NOT NULL,
 actor_employee_id BIGINT UNSIGNED NULL,
 activity_key VARCHAR(120) NOT NULL,
 old_value VARCHAR(1000) NULL,
 new_value VARCHAR(1000) NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_service_request_activity (request_id,created_at),
 CONSTRAINT fk_service_request_activity_request FOREIGN KEY (request_id) REFERENCES service_requests(request_id),
 CONSTRAINT fk_service_request_activity_actor FOREIGN KEY (actor_employee_id) REFERENCES employees(employee_id)
);
INSERT INTO permissions (permission_key,description) VALUES
('service_request.create','Submit service requests within the actor''s authorized scope'),
('service_request.read','Read service requests within the actor''s authorized scope'),
('service_request.update','Update service request handling and closure within the actor''s authorized scope'),
('service_request.assign','Assign service requests within the actor''s authorized scope'),
('service_request.categories.manage','Create and manage service request categories')
ON DUPLICATE KEY UPDATE description=VALUES(description);
