-- Complete the Blueprint-required pending-reason and comment capabilities.
-- Notification rows are written by the owning service in the same transaction.
ALTER TABLE service_requests
    ADD COLUMN pending_reason MEDIUMTEXT NULL AFTER resolution_notes;

ALTER TABLE service_request_activity
    ADD COLUMN reason MEDIUMTEXT NULL AFTER new_value;

CREATE TABLE service_request_comments (
    comment_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    request_id BIGINT UNSIGNED NOT NULL,
    author_employee_id BIGINT UNSIGNED NOT NULL,
    body MEDIUMTEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (comment_id),
    KEY idx_service_request_comments (request_id, created_at, comment_id),
    CONSTRAINT fk_service_request_comment_request
        FOREIGN KEY (request_id) REFERENCES service_requests(request_id),
    CONSTRAINT fk_service_request_comment_author
        FOREIGN KEY (author_employee_id) REFERENCES employees(employee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
