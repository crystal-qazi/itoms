-- ITOMS Service Request module schema proposal (MySQL 8.0+ / InnoDB)
-- DESIGN ONLY: not applied. Identity references intentionally have no FK until
-- canonical employee/team table names, key types and lifecycle rules are inspected.
-- Apply through the approved migration runner after integration review.

CREATE TABLE service_request_categories (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(120) NOT NULL,
    description VARCHAR(500) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT NOT NULL DEFAULT 0,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_sr_category_code (code),
    KEY ix_sr_category_active_order (is_active, sort_order, name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE service_request_priorities (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(80) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_sr_priority_code (code),
    KEY ix_sr_priority_active_order (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE service_request_statuses (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(64) NOT NULL,
    name VARCHAR(80) NOT NULL,
    sort_order INT NOT NULL DEFAULT 0,
    is_initial BOOLEAN NOT NULL DEFAULT FALSE,
    is_pending BOOLEAN NOT NULL DEFAULT FALSE,
    is_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_sr_status_code (code),
    KEY ix_sr_status_active_order (is_active, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE service_requests (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    request_key VARCHAR(32) GENERATED ALWAYS AS (CONCAT('SR-', LPAD(id, 8, '0'))) STORED,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    category_id BIGINT UNSIGNED NOT NULL,
    priority_id BIGINT UNSIGNED NOT NULL,
    status_id BIGINT UNSIGNED NOT NULL,
    requester_employee_id BIGINT UNSIGNED NOT NULL,
    assigned_team_id BIGINT UNSIGNED NULL,
    assigned_employee_id BIGINT UNSIGNED NULL,
    current_pending_reason VARCHAR(1000) NULL,
    version INT UNSIGNED NOT NULL DEFAULT 1,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uq_sr_request_key (request_key),
    KEY ix_sr_requester_created (requester_employee_id, created_at, id),
    KEY ix_sr_team_status_created (assigned_team_id, status_id, created_at, id),
    KEY ix_sr_assignee_status_created (assigned_employee_id, status_id, created_at, id),
    KEY ix_sr_status_created (status_id, created_at, id),
    KEY ix_sr_category_priority (category_id, priority_id),
    CONSTRAINT fk_sr_category FOREIGN KEY (category_id)
        REFERENCES service_request_categories(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_sr_priority FOREIGN KEY (priority_id)
        REFERENCES service_request_priorities(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_sr_status FOREIGN KEY (status_id)
        REFERENCES service_request_statuses(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_sr_title_nonempty CHECK (CHAR_LENGTH(TRIM(title)) > 0),
    CONSTRAINT chk_sr_description_nonempty CHECK (CHAR_LENGTH(TRIM(description)) > 0),
    CONSTRAINT chk_sr_version_positive CHECK (version >= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE service_request_comments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    service_request_id BIGINT UNSIGNED NOT NULL,
    author_employee_id BIGINT UNSIGNED NOT NULL,
    body TEXT NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_sr_comment_request_created (service_request_id, created_at, id),
    CONSTRAINT fk_sr_comment_request FOREIGN KEY (service_request_id)
        REFERENCES service_requests(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT chk_sr_comment_nonempty CHECK (CHAR_LENGTH(TRIM(body)) > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE service_request_status_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    service_request_id BIGINT UNSIGNED NOT NULL,
    from_status_id BIGINT UNSIGNED NULL,
    to_status_id BIGINT UNSIGNED NOT NULL,
    changed_by_employee_id BIGINT UNSIGNED NOT NULL,
    reason VARCHAR(1000) NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY ix_sr_history_request_created (service_request_id, created_at, id),
    CONSTRAINT fk_sr_history_request FOREIGN KEY (service_request_id)
        REFERENCES service_requests(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_sr_history_from_status FOREIGN KEY (from_status_id)
        REFERENCES service_request_statuses(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_sr_history_to_status FOREIGN KEY (to_status_id)
        REFERENCES service_request_statuses(id) ON UPDATE RESTRICT ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- The application must additionally enforce exactly one active initial status,
-- active category/priority/status selection, pending reason requirements,
-- employee/team assignment eligibility, object scope, and append-only history.
-- These cross-row/business invariants belong in transactional service logic.
