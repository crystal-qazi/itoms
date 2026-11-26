-- ITOMS platform identity and authorization foundation.
CREATE TABLE IF NOT EXISTS departments (
 department_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, department_name VARCHAR(150) NOT NULL UNIQUE, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS teams (
 team_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, department_id BIGINT UNSIGNED NOT NULL, team_name VARCHAR(150) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY uq_team_department_name (department_id, team_name), CONSTRAINT fk_teams_department FOREIGN KEY (department_id) REFERENCES departments(department_id)
);
CREATE TABLE IF NOT EXISTS employees (
 employee_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, employee_code VARCHAR(80) NOT NULL UNIQUE, full_name VARCHAR(200) NOT NULL, email VARCHAR(254) NULL UNIQUE, job_title VARCHAR(150) NULL, department_id BIGINT UNSIGNED NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP, CONSTRAINT fk_employees_department FOREIGN KEY (department_id) REFERENCES departments(department_id)
);
CREATE TABLE IF NOT EXISTS employee_team_memberships (
 employee_id BIGINT UNSIGNED NOT NULL, team_id BIGINT UNSIGNED NOT NULL, is_primary BOOLEAN NOT NULL DEFAULT FALSE, assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (employee_id, team_id), CONSTRAINT fk_membership_employee FOREIGN KEY (employee_id) REFERENCES employees(employee_id), CONSTRAINT fk_membership_team FOREIGN KEY (team_id) REFERENCES teams(team_id)
);
CREATE TABLE IF NOT EXISTS application_roles (
 role_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, role_name VARCHAR(100) NOT NULL UNIQUE, description VARCHAR(500) NULL, is_system_role BOOLEAN NOT NULL DEFAULT FALSE, is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS permissions (
 permission_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, permission_key VARCHAR(160) NOT NULL UNIQUE, description VARCHAR(500) NULL
);
CREATE TABLE IF NOT EXISTS role_permissions (
 role_id BIGINT UNSIGNED NOT NULL, permission_id BIGINT UNSIGNED NOT NULL, PRIMARY KEY (role_id, permission_id), CONSTRAINT fk_role_permissions_role FOREIGN KEY (role_id) REFERENCES application_roles(role_id), CONSTRAINT fk_role_permissions_permission FOREIGN KEY (permission_id) REFERENCES permissions(permission_id)
);
CREATE TABLE IF NOT EXISTS employee_role_assignments (
 assignment_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, employee_id BIGINT UNSIGNED NOT NULL, role_id BIGINT UNSIGNED NOT NULL, scope_type ENUM('OWN','TEAM','MANAGED_TEAMS','DEPARTMENT','RESOURCE') NOT NULL DEFAULT 'OWN', scope_reference VARCHAR(255) NULL, assigned_by BIGINT UNSIGNED NULL, assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, expires_at TIMESTAMP NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE, CONSTRAINT fk_assignment_employee FOREIGN KEY (employee_id) REFERENCES employees(employee_id), CONSTRAINT fk_assignment_role FOREIGN KEY (role_id) REFERENCES application_roles(role_id), CONSTRAINT fk_assignment_assigner FOREIGN KEY (assigned_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS audit_events (
 audit_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY, actor_employee_id BIGINT UNSIGNED NULL, event_key VARCHAR(160) NOT NULL, target_type VARCHAR(120) NULL, target_id VARCHAR(255) NULL, outcome ENUM('SUCCESS','FAILURE','DENIED') NOT NULL DEFAULT 'SUCCESS', request_id VARCHAR(80) NULL, details JSON NULL, occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, INDEX idx_audit_actor_time (actor_employee_id, occurred_at), INDEX idx_audit_target (target_type, target_id), CONSTRAINT fk_audit_actor FOREIGN KEY (actor_employee_id) REFERENCES employees(employee_id)
);
