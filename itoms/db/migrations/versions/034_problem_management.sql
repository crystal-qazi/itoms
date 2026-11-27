-- Problem Management, incident links and known-error records.
CREATE TABLE IF NOT EXISTS problem_records (
 problem_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 problem_key VARCHAR(40) NOT NULL UNIQUE,
 title VARCHAR(240) NOT NULL,
 description MEDIUMTEXT NOT NULL,
 root_cause MEDIUMTEXT NULL,
 owner_team_id BIGINT UNSIGNED NOT NULL,
 assigned_to BIGINT UNSIGNED NULL,
 priority ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
 status ENUM('OPEN','INVESTIGATING','KNOWN_ERROR','RESOLVED','CLOSED') NOT NULL DEFAULT 'OPEN',
 created_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 resolved_at DATETIME NULL,
 INDEX idx_problem_queue (owner_team_id,status,priority,updated_at),
 CONSTRAINT fk_problem_team FOREIGN KEY (owner_team_id) REFERENCES teams(team_id),
 CONSTRAINT fk_problem_assignee FOREIGN KEY (assigned_to) REFERENCES employees(employee_id),
 CONSTRAINT fk_problem_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS problem_incident_links (
 problem_id BIGINT UNSIGNED NOT NULL,
 ticket_id BIGINT UNSIGNED NOT NULL,
 linked_by BIGINT UNSIGNED NOT NULL,
 linked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (problem_id,ticket_id),
 CONSTRAINT fk_problem_link_problem FOREIGN KEY (problem_id) REFERENCES problem_records(problem_id),
 CONSTRAINT fk_problem_link_incident FOREIGN KEY (ticket_id) REFERENCES incident_tickets(ticket_id),
 CONSTRAINT fk_problem_link_actor FOREIGN KEY (linked_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS known_error_records (
 known_error_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 problem_id BIGINT UNSIGNED NOT NULL UNIQUE,
 title VARCHAR(200) NOT NULL,
 symptoms MEDIUMTEXT NOT NULL,
 workaround MEDIUMTEXT NOT NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_known_error_problem FOREIGN KEY (problem_id) REFERENCES problem_records(problem_id),
 CONSTRAINT fk_known_error_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
INSERT INTO permissions (permission_key,description) VALUES
 ('problem.read','Read problems and known errors within authorized team scope'),
 ('problem.create','Create problems for authorized teams'),
 ('problem.update','Manage problem lifecycle, incident links and known errors within authorized team scope')
ON DUPLICATE KEY UPDATE description=VALUES(description);
