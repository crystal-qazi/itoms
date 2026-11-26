-- Authentication primitives. Secrets/tokens are stored encrypted or hashed by service code.
CREATE TABLE IF NOT EXISTS user_accounts (
 account_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 employee_id BIGINT UNSIGNED NOT NULL UNIQUE,
 username VARCHAR(120) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL,
 account_status ENUM('PENDING','ACTIVE','SUSPENDED','DISABLED') NOT NULL DEFAULT 'PENDING',
 must_change_password BOOLEAN NOT NULL DEFAULT TRUE,
 failed_login_count SMALLINT UNSIGNED NOT NULL DEFAULT 0,
 locked_until DATETIME NULL,
 session_version INT UNSIGNED NOT NULL DEFAULT 1,
 mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE,
 totp_secret_encrypted VARBINARY(512) NULL,
 last_login_at DATETIME NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 CONSTRAINT fk_account_employee FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);
CREATE TABLE IF NOT EXISTS account_recovery_codes (
 recovery_code_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 account_id BIGINT UNSIGNED NOT NULL,
 code_hash VARCHAR(255) NOT NULL,
 used_at DATETIME NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_recovery_account (account_id),
 CONSTRAINT fk_recovery_account FOREIGN KEY (account_id) REFERENCES user_accounts(account_id)
);
CREATE TABLE IF NOT EXISTS user_sessions (
 session_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 account_id BIGINT UNSIGNED NOT NULL,
 token_hash CHAR(64) NOT NULL UNIQUE,
 session_version INT UNSIGNED NOT NULL,
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 last_activity_at DATETIME NOT NULL,
 expires_at DATETIME NOT NULL,
 revoked_at DATETIME NULL,
 revoke_reason VARCHAR(160) NULL,
 ip_address VARCHAR(45) NULL,
 user_agent VARCHAR(500) NULL,
 INDEX idx_session_account_active (account_id, revoked_at, expires_at),
 CONSTRAINT fk_session_account FOREIGN KEY (account_id) REFERENCES user_accounts(account_id)
);
CREATE TABLE IF NOT EXISTS authentication_events (
 auth_event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 account_id BIGINT UNSIGNED NULL,
 username_attempted VARCHAR(120) NULL,
 event_type ENUM('LOGIN_SUCCESS','LOGIN_FAILURE','LOCKOUT','MFA_SUCCESS','MFA_FAILURE','SESSION_REVOKED','PASSWORD_CHANGED') NOT NULL,
 ip_address VARCHAR(45) NULL,
 user_agent VARCHAR(500) NULL,
 occurred_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 INDEX idx_auth_events_account_time (account_id, occurred_at),
 INDEX idx_auth_events_username_time (username_attempted, occurred_at),
 CONSTRAINT fk_auth_event_account FOREIGN KEY (account_id) REFERENCES user_accounts(account_id)
);
