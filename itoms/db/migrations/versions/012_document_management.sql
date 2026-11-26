-- Controlled document metadata, immutable versions and governed sharing.
CREATE TABLE IF NOT EXISTS managed_files (
 file_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 opaque_id CHAR(36) NOT NULL UNIQUE,
 original_filename VARCHAR(255) NOT NULL,
 storage_key VARCHAR(500) NOT NULL UNIQUE,
 detected_mime_type VARCHAR(150) NOT NULL,
 file_size_bytes BIGINT UNSIGNED NOT NULL,
 sha256_checksum CHAR(64) NOT NULL,
 classification ENUM('PUBLIC','INTERNAL','RESTRICTED','CONFIDENTIAL') NOT NULL DEFAULT 'INTERNAL',
 scan_status ENUM('PENDING','CLEAN','INFECTED','ERROR') NOT NULL DEFAULT 'PENDING',
 lifecycle_status ENUM('ACTIVE','QUARANTINED','ARCHIVED','REVOKED','PENDING_DELETE') NOT NULL DEFAULT 'ACTIVE',
 uploaded_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 INDEX idx_managed_file_owner (uploaded_by,created_at),
 INDEX idx_managed_file_scan (scan_status,lifecycle_status),
 CONSTRAINT fk_managed_file_uploader FOREIGN KEY (uploaded_by) REFERENCES employees(employee_id),
 CHECK (file_size_bytes <= 10485760)
);
CREATE TABLE IF NOT EXISTS managed_file_versions (
 file_version_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 file_id BIGINT UNSIGNED NOT NULL,
 version_number INT UNSIGNED NOT NULL,
 storage_key VARCHAR(500) NOT NULL UNIQUE,
 file_size_bytes BIGINT UNSIGNED NOT NULL,
 sha256_checksum CHAR(64) NOT NULL,
 detected_mime_type VARCHAR(150) NOT NULL,
 scan_status ENUM('PENDING','CLEAN','INFECTED','ERROR') NOT NULL DEFAULT 'PENDING',
 uploaded_by BIGINT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_managed_file_version (file_id,version_number),
 CONSTRAINT fk_file_version_file FOREIGN KEY (file_id) REFERENCES managed_files(file_id),
 CONSTRAINT fk_file_version_uploader FOREIGN KEY (uploaded_by) REFERENCES employees(employee_id),
 CHECK (file_size_bytes <= 10485760)
);
CREATE TABLE IF NOT EXISTS managed_file_shares (
 share_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 file_id BIGINT UNSIGNED NOT NULL,
 shared_with_employee_id BIGINT UNSIGNED NOT NULL,
 shared_by_employee_id BIGINT UNSIGNED NOT NULL,
 permission ENUM('PREVIEW','DOWNLOAD') NOT NULL,
 expires_at DATETIME NOT NULL,
 revoked_at DATETIME NULL,
 approval_request_id BIGINT UNSIGNED NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_file_share_recipient (shared_with_employee_id,expires_at,revoked_at),
 CONSTRAINT fk_file_share_file FOREIGN KEY (file_id) REFERENCES managed_files(file_id),
 CONSTRAINT fk_file_share_recipient FOREIGN KEY (shared_with_employee_id) REFERENCES employees(employee_id),
 CONSTRAINT fk_file_share_creator FOREIGN KEY (shared_by_employee_id) REFERENCES employees(employee_id),
 CONSTRAINT fk_file_share_approval FOREIGN KEY (approval_request_id) REFERENCES approval_requests(approval_request_id)
);
CREATE TABLE IF NOT EXISTS file_scan_events (
 scan_event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 file_id BIGINT UNSIGNED NOT NULL,
 file_version_id BIGINT UNSIGNED NULL,
 scanner_name VARCHAR(100) NOT NULL,
 scanner_engine_version VARCHAR(100) NULL,
 scan_result ENUM('CLEAN','INFECTED','ERROR') NOT NULL,
 details VARCHAR(500) NULL,
 scanned_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 CONSTRAINT fk_file_scan_file FOREIGN KEY (file_id) REFERENCES managed_files(file_id),
 CONSTRAINT fk_file_scan_version FOREIGN KEY (file_version_id) REFERENCES managed_file_versions(file_version_id)
);
