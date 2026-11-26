-- Change management and controlled software release records.
CREATE TABLE IF NOT EXISTS change_records (
 change_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 change_number VARCHAR(40) NOT NULL UNIQUE,
 title VARCHAR(240) NOT NULL,
 description MEDIUMTEXT NOT NULL,
 change_type ENUM('NORMAL','STANDARD','EMERGENCY') NOT NULL DEFAULT 'NORMAL',
 risk_level ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL DEFAULT 'MEDIUM',
 status ENUM('DRAFT','SUBMITTED','SCHEDULED','IMPLEMENTING','IMPLEMENTED','FAILED','CANCELLED','CLOSED') NOT NULL DEFAULT 'DRAFT',
 requested_by BIGINT UNSIGNED NOT NULL,
 owner_employee_id BIGINT UNSIGNED NULL,
 planned_start DATETIME NULL,
 planned_end DATETIME NULL,
 implementation_plan MEDIUMTEXT NULL,
 rollback_plan MEDIUMTEXT NULL,
 verification_plan MEDIUMTEXT NULL,
 implementation_result MEDIUMTEXT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_change_calendar (planned_start,planned_end,status),
 CONSTRAINT fk_change_requester FOREIGN KEY (requested_by) REFERENCES employees(employee_id),
 CONSTRAINT fk_change_owner FOREIGN KEY (owner_employee_id) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS change_activity (
 change_activity_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 change_id BIGINT UNSIGNED NOT NULL,
 actor_employee_id BIGINT UNSIGNED NOT NULL,
 action_key VARCHAR(80) NOT NULL,
 details MEDIUMTEXT NULL,
 occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_change_activity (change_id,occurred_at),
 CONSTRAINT fk_change_activity_change FOREIGN KEY (change_id) REFERENCES change_records(change_id),
 CONSTRAINT fk_change_activity_actor FOREIGN KEY (actor_employee_id) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS software_releases (
 release_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 release_key VARCHAR(100) NOT NULL UNIQUE,
 service_id BIGINT UNSIGNED NULL,
 version_label VARCHAR(80) NOT NULL,
 release_notes MEDIUMTEXT NULL,
 status ENUM('PLANNED','IN_TEST','READY','APPROVED','DEPLOYING','RELEASED','ROLLED_BACK','CANCELLED') NOT NULL DEFAULT 'PLANNED',
 target_at DATETIME NULL,
 released_at DATETIME NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_release_service FOREIGN KEY (service_id) REFERENCES service_records(service_id),
 CONSTRAINT fk_release_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS release_change_links (
 release_id BIGINT UNSIGNED NOT NULL,
 change_id BIGINT UNSIGNED NOT NULL,
 PRIMARY KEY (release_id,change_id),
 CONSTRAINT fk_release_link_release FOREIGN KEY (release_id) REFERENCES software_releases(release_id),
 CONSTRAINT fk_release_link_change FOREIGN KEY (change_id) REFERENCES change_records(change_id)
);
