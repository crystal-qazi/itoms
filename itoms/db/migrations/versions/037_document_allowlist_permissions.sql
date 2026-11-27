-- Admin-configurable safe file type allowlist; actual signatures are validated by the service.
CREATE TABLE IF NOT EXISTS document_file_type_allowlist (
 extension VARCHAR(12) PRIMARY KEY,
 mime_type VARCHAR(150) NOT NULL,
 description VARCHAR(200) NULL,
 is_active BOOLEAN NOT NULL DEFAULT TRUE,
 updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
INSERT INTO document_file_type_allowlist (extension,mime_type,description,is_active) VALUES
 ('pdf','application/pdf','PDF document',TRUE),
 ('png','image/png','PNG image',TRUE),
 ('jpg','image/jpeg','JPEG image',TRUE),
 ('jpeg','image/jpeg','JPEG image',TRUE),
 ('gif','image/gif','GIF image',TRUE),
 ('txt','text/plain','UTF-8 plain text',TRUE),
 ('docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document','Word document',TRUE),
 ('xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','Excel workbook',TRUE),
 ('pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation','PowerPoint presentation',TRUE)
ON DUPLICATE KEY UPDATE mime_type=VALUES(mime_type),description=VALUES(description);
INSERT INTO permissions (permission_key,description) VALUES
 ('document.upload','Upload documents into managed storage'),
 ('document.read','Read document metadata within authorized owner scope'),
 ('document.download','Download clean active documents within authorized owner scope'),
 ('document.allowlist.manage','Configure the document extension and MIME allowlist')
ON DUPLICATE KEY UPDATE description=VALUES(description);
