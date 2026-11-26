-- Explicit manager-to-team relationships; job titles do not imply authority.
CREATE TABLE IF NOT EXISTS team_management_assignments (
 manager_employee_id BIGINT UNSIGNED NOT NULL,
 team_id BIGINT UNSIGNED NOT NULL,
 assigned_by BIGINT UNSIGNED NULL,
 assigned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (manager_employee_id, team_id),
 CONSTRAINT fk_team_manager_employee FOREIGN KEY (manager_employee_id) REFERENCES employees(employee_id),
 CONSTRAINT fk_team_manager_team FOREIGN KEY (team_id) REFERENCES teams(team_id),
 CONSTRAINT fk_team_manager_assigner FOREIGN KEY (assigned_by) REFERENCES employees(employee_id)
);
