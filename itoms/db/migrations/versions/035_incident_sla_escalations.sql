-- Configurable 24x7 incident SLA escalation thresholds and idempotency records.
CREATE TABLE IF NOT EXISTS incident_sla_escalation_policies (
 policy_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 priority ENUM('LOW','MEDIUM','HIGH','CRITICAL') NOT NULL,
 sla_type ENUM('FIRST_RESPONSE','RESOLUTION') NOT NULL,
 escalation_level TINYINT UNSIGNED NOT NULL,
 after_due_minutes INT UNSIGNED NOT NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 UNIQUE KEY uq_incident_sla_escalation (priority,sla_type,escalation_level),
 CHECK (escalation_level BETWEEN 1 AND 9),
 CHECK (after_due_minutes BETWEEN 1 AND 10080)
);
CREATE TABLE IF NOT EXISTS incident_sla_escalation_events (
 escalation_event_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
 ticket_id BIGINT UNSIGNED NOT NULL,
 sla_type ENUM('FIRST_RESPONSE','RESOLUTION') NOT NULL,
 escalation_level TINYINT UNSIGNED NOT NULL,
 due_at DATETIME NOT NULL,
 triggered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE KEY uq_incident_sla_escalation_event (ticket_id,sla_type,escalation_level),
 CONSTRAINT fk_incident_sla_event_ticket FOREIGN KEY (ticket_id) REFERENCES incident_tickets(ticket_id)
);
INSERT INTO incident_sla_escalation_policies
 (priority,sla_type,escalation_level,after_due_minutes,is_active) VALUES
 ('LOW','FIRST_RESPONSE',1,60,TRUE),('LOW','FIRST_RESPONSE',2,240,TRUE),
 ('LOW','RESOLUTION',1,120,TRUE),('LOW','RESOLUTION',2,480,TRUE),
 ('MEDIUM','FIRST_RESPONSE',1,30,TRUE),('MEDIUM','FIRST_RESPONSE',2,120,TRUE),
 ('MEDIUM','RESOLUTION',1,60,TRUE),('MEDIUM','RESOLUTION',2,240,TRUE),
 ('HIGH','FIRST_RESPONSE',1,15,TRUE),('HIGH','FIRST_RESPONSE',2,60,TRUE),
 ('HIGH','RESOLUTION',1,30,TRUE),('HIGH','RESOLUTION',2,120,TRUE),
 ('CRITICAL','FIRST_RESPONSE',1,5,TRUE),('CRITICAL','FIRST_RESPONSE',2,15,TRUE),
 ('CRITICAL','RESOLUTION',1,15,TRUE),('CRITICAL','RESOLUTION',2,60,TRUE)
ON DUPLICATE KEY UPDATE
 after_due_minutes=VALUES(after_due_minutes),is_active=VALUES(is_active);
INSERT INTO permissions (permission_key,description) VALUES
 ('incident.sla.manage','Configure priority-based incident SLA escalation policies')
ON DUPLICATE KEY UPDATE description=VALUES(description);
