-- Additional document versioning and governed sharing permissions.
INSERT INTO permissions (permission_key,description) VALUES
 ('document.share','Share owned documents with explicit expiry and approval for sensitive classifications'),
 ('document.version.manage','Upload a new scanned version of an owned document'),
 ('document.share.manage','Manage document sharing policies')
ON DUPLICATE KEY UPDATE description=VALUES(description);
