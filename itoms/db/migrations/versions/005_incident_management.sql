-- Helpdesk / incident management core with external-event idempotency.
CREATE TABLE IF NOT EXISTS service_categories (
 category_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 category_name VARCHAR(150) NOT NULL UNIQUE,
 is_active BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE IF NOT EXISTS incident_tickets (
 ticket_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 ticket_number VARCHAR(40) NOT NULL UNIQUE,
 title VARCHAR(240) NOT NULL,
 description MEDIUMTEXT NOT NULL,
 category_id BIGINT UNSIGNED NULL,
 requester_employee_id BIGINT UNSIGNED NULL,
 assigned_employee_id BIGINT UNSIGNED NULL,
 assigned_team_id BIGINT UNSIGNED NULL,
 status ENUM('NEW','OPEN','IN_PROGRESS','PENDING','RESOLVED','CLOSED','CANCELLED') NOT NULL DEFAULT 'NEW',
 priority ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
 source ENUM('PORTAL','EMAIL','PHONE','GRAFANA','ADMIN') NOT NULL DEFAULT 'PORTAL',
 external_source VARCHAR(80) NULL,
 external_event_id VARCHAR(190) NULL,
 first_response_due_at DATETIME NULL,
 resolution_due_at DATETIME NULL,
 first_responded_at DATETIME NULL,
 resolved_at DATETIME NULL,
 closed_at DATETIME NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_incident_queue (status,priority,created_at),
 INDEX idx_incident_assignee (assigned_employee_id,status),
 INDEX idx_incident_team (assigned_team_id,status),
 UNIQUE KEY uq_incident_external_event (external_source,external_event_id),
 CONSTRAINT fk_incident_category FOREIGN KEY (category_id) REFERENCES service_categories(category_id),
 CONSTRAINT fk_incident_requester FOREIGN KEY (requester_employee_id) REFERENCES employees(employee_id),
 CONSTRAINT fk_incident_assignee FOREIGN KEY (assigned_employee_id) REFERENCES employees(employee_id),
 CONSTRAINT fk_incident_team FOREIGN KEY (assigned_team_id) REFERENCES teams(team_id)
);
CREATE TABLE IF NOT EXISTS incident_comments (
 comment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 ticket_id BIGINT UNSIGNED NOT NULL,
 author_employee_id BIGINT UNSIGNED NOT NULL,
 comment_body MEDIUMTEXT NOT NULL,
 is_internal BOOLEAN NOT NULL DEFAULT FALSE,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_incident_comments_ticket (ticket_id,created_at),
 CONSTRAINT fk_incident_comment_ticket FOREIGN KEY (ticket_id) REFERENCES incident_tickets(ticket_id),
 CONSTRAINT fk_incident_comment_author FOREIGN KEY (author_employee_id) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS incident_activity (
 activity_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 ticket_id BIGINT UNSIGNED NOT NULL,
 actor_employee_id BIGINT UNSIGNED NULL,
 activity_key VARCHAR(120) NOT NULL,
 old_value VARCHAR(500) NULL,
 new_value VARCHAR(500) NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_incident_activity_ticket (ticket_id,created_at),
 CONSTRAINT fk_incident_activity_ticket FOREIGN KEY (ticket_id) REFERENCES incident_tickets(ticket_id),
 CONSTRAINT fk_incident_activity_actor FOREIGN KEY (actor_employee_id) REFERENCES employees(employee_id)
);
