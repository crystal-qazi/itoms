-- Explicit permissions for Network, Infrastructure and Oracle operations.
INSERT INTO permissions (permission_key,description) VALUES
 ('operations.read','Read operational work within authorized team scope'),
 ('operations.create','Create Network, Infrastructure and Oracle work for authorized teams'),
 ('operations.update','Update operational work within authorized team scope'),
 ('oracle.inventory.read','Read Oracle database inventory through authorized service scope'),
 ('oracle.inventory.manage','Register and update Oracle database references through authorized service scope')
ON DUPLICATE KEY UPDATE description=VALUES(description);
