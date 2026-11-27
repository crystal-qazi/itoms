-- Preserve rejected change attempts and allow a controlled resubmission.
ALTER TABLE change_records
 MODIFY COLUMN status ENUM('DRAFT','SUBMITTED','REJECTED','SCHEDULED','IMPLEMENTING','IMPLEMENTED','FAILED','CANCELLED','CLOSED')
 NOT NULL DEFAULT 'DRAFT';
