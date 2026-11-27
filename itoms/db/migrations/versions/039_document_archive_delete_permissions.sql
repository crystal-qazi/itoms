-- Explicit permissions for archiving and approval-gated permanent document deletion.
INSERT INTO permissions (permission_key,description) VALUES
 ('document.archive','Archive owned documents and revoke active shares'),
 ('document.delete','Permanently delete documents only with a matching approved deletion request')
ON DUPLICATE KEY UPDATE description=VALUES(description);
