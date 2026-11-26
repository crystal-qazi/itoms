-- Lightweight asset register and basic maintenance; excludes procurement.
CREATE TABLE IF NOT EXISTS asset_records (
 asset_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 asset_tag VARCHAR(100) NOT NULL UNIQUE,
 asset_name VARCHAR(200) NOT NULL,
 asset_type VARCHAR(80) NOT NULL,
 serial_number VARCHAR(150) NULL,
 manufacturer VARCHAR(150) NULL,
 model VARCHAR(150) NULL,
 assigned_employee_id BIGINT UNSIGNED NULL,
 owner_team_id BIGINT UNSIGNED NULL,
 location_label VARCHAR(200) NULL,
 asset_status ENUM('IN_USE','IN_STOCK','UNDER_REPAIR','RETIRED','LOST') NOT NULL DEFAULT 'IN_STOCK',
 acquired_on DATE NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 CONSTRAINT fk_asset_assignee FOREIGN KEY (assigned_employee_id) REFERENCES employees(employee_id),
 CONSTRAINT fk_asset_team FOREIGN KEY (owner_team_id) REFERENCES teams(team_id)
);
CREATE TABLE IF NOT EXISTS asset_maintenance (
 maintenance_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 asset_id BIGINT UNSIGNED NOT NULL,
 reported_by BIGINT UNSIGNED NOT NULL,
 assigned_to BIGINT UNSIGNED NULL,
 issue_description MEDIUMTEXT NOT NULL,
 status ENUM('OPEN','IN_PROGRESS','ON_HOLD','COMPLETED','CANCELLED') NOT NULL DEFAULT 'OPEN',
 opened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 completed_at DATETIME NULL,
 INDEX idx_asset_maintenance (asset_id,status,opened_at),
 CONSTRAINT fk_maintenance_asset FOREIGN KEY (asset_id) REFERENCES asset_records(asset_id),
 CONSTRAINT fk_maintenance_reporter FOREIGN KEY (reported_by) REFERENCES employees(employee_id),
 CONSTRAINT fk_maintenance_assignee FOREIGN KEY (assigned_to) REFERENCES employees(employee_id)
);
-- Project tracking: scope, milestones and team assignments only; no procurement.
CREATE TABLE IF NOT EXISTS projects (
 project_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 project_key VARCHAR(80) NOT NULL UNIQUE,
 project_name VARCHAR(200) NOT NULL,
 description MEDIUMTEXT NULL,
 project_manager_employee_id BIGINT UNSIGNED NULL,
 status ENUM('PROPOSED','ACTIVE','ON_HOLD','COMPLETED','CANCELLED') NOT NULL DEFAULT 'PROPOSED',
 start_date DATE NULL,
 target_end_date DATE NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_project_manager FOREIGN KEY (project_manager_employee_id) REFERENCES employees(employee_id),
 CONSTRAINT fk_project_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS project_team_assignments (
 project_id BIGINT UNSIGNED NOT NULL,
 team_id BIGINT UNSIGNED NOT NULL,
 assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (project_id,team_id),
 CONSTRAINT fk_project_team_project FOREIGN KEY (project_id) REFERENCES projects(project_id),
 CONSTRAINT fk_project_team_team FOREIGN KEY (team_id) REFERENCES teams(team_id)
);
CREATE TABLE IF NOT EXISTS project_milestones (
 milestone_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 project_id BIGINT UNSIGNED NOT NULL,
 title VARCHAR(200) NOT NULL,
 due_date DATE NULL,
 status ENUM('NOT_STARTED','IN_PROGRESS','COMPLETED','DELAYED','CANCELLED') NOT NULL DEFAULT 'NOT_STARTED',
 completed_at DATETIME NULL,
 CONSTRAINT fk_milestone_project FOREIGN KEY (project_id) REFERENCES projects(project_id)
);
