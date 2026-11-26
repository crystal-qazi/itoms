-- Service/software inventory and cross-team engineering task tracking.
CREATE TABLE IF NOT EXISTS service_records (
 service_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 service_key VARCHAR(80) NOT NULL UNIQUE,
 service_name VARCHAR(200) NOT NULL,
 service_type VARCHAR(40) NOT NULL,
 description TEXT NULL,
 owner_team_id BIGINT UNSIGNED NULL,
 criticality ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
 lifecycle_status ENUM('PLANNED','ACTIVE','DEGRADED','RETIRED') NOT NULL DEFAULT 'PLANNED',
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_service_owner (owner_team_id,lifecycle_status),
 CONSTRAINT fk_service_owner_team FOREIGN KEY (owner_team_id) REFERENCES teams(team_id)
);
CREATE TABLE IF NOT EXISTS engineering_tasks (
 task_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 task_number VARCHAR(40) NOT NULL UNIQUE,
 title VARCHAR(240) NOT NULL,
 description MEDIUMTEXT NULL,
 team_id BIGINT UNSIGNED NOT NULL,
 project_key VARCHAR(80) NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 assigned_to BIGINT UNSIGNED NULL,
 priority ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
 status ENUM('BACKLOG','READY','IN_PROGRESS','BLOCKED','IN_REVIEW','DONE','CANCELLED') NOT NULL DEFAULT 'BACKLOG',
 due_at DATETIME NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_engineering_team_queue (team_id,status,priority),
 INDEX idx_engineering_assignee (assigned_to,status),
 CONSTRAINT fk_engineering_team FOREIGN KEY (team_id) REFERENCES teams(team_id),
 CONSTRAINT fk_engineering_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id),
 CONSTRAINT fk_engineering_assignee FOREIGN KEY (assigned_to) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS engineering_task_activity (
 activity_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 task_id BIGINT UNSIGNED NOT NULL,
 actor_employee_id BIGINT UNSIGNED NOT NULL,
 action_key VARCHAR(80) NOT NULL,
 old_value VARCHAR(500) NULL,
 new_value VARCHAR(500) NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_task_activity (task_id,created_at),
 CONSTRAINT fk_task_activity_task FOREIGN KEY (task_id) REFERENCES engineering_tasks(task_id),
 CONSTRAINT fk_task_activity_actor FOREIGN KEY (actor_employee_id) REFERENCES employees(employee_id)
);
