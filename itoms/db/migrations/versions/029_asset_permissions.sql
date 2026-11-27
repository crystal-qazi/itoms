-- Asset register and basic maintenance permissions; no procurement grants are implied.
INSERT INTO permissions (permission_key,description) VALUES
 ('asset.read','Read assets and maintenance tickets within authorized team scope'),
 ('asset.create','Register assets for authorized owner teams'),
 ('asset.update','Update asset lifecycle within authorized team scope'),
 ('asset.maintenance.create','Open repair tickets for assets within authorized scope'),
 ('asset.maintenance.update','Update repair tickets within authorized team scope')
ON DUPLICATE KEY UPDATE description=VALUES(description);
