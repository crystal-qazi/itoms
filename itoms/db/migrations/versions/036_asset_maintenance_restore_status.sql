-- Preserve the pre-repair asset lifecycle so completion restores the correct state.
ALTER TABLE asset_maintenance
 ADD COLUMN previous_asset_status ENUM('IN_USE','IN_STOCK') NULL
 AFTER issue_description;
