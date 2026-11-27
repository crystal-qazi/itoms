-- Personal saved report definitions; data access remains delegated to authorized services.
CREATE TABLE IF NOT EXISTS saved_reports (
 report_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 report_name VARCHAR(150) NOT NULL,
 dataset_key VARCHAR(60) NOT NULL,
 definition JSON NOT NULL,
 created_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE KEY uq_saved_report_owner_name (created_by,report_name),
 INDEX idx_saved_reports_owner (created_by,updated_at),
 CONSTRAINT fk_saved_report_creator FOREIGN KEY (created_by) REFERENCES employees(employee_id)
);
INSERT INTO permissions (permission_key,description) VALUES
 ('reports.read','Read personal saved report definitions'),
 ('reports.create','Create personal saved report definitions'),
 ('reports.run','Run and export personal saved reports using underlying scoped permissions')
ON DUPLICATE KEY UPDATE description=VALUES(description);
