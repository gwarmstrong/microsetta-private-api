ALTER TABLE barcodes.project ADD COLUMN is_microsetta BOOLEAN;
UPDATE barcodes.project SET is_microsetta='no' WHERE is_microsetta IS NULL;
UPDATE barcodes.project SET is_microsetta='yes' WHERE project in ('American Gut Project',
                                                                  'British Gut Project',
                                                                  'Daklapak W1',
                                                                  'canadian gut',
                                                                  'TMI - Daklapack W1',
                                                                  'TMI - Daklapack W2');
ALTER TABLE barcodes.project ALTER COLUMN is_microsetta SET NOT NULL;
ALTER TABLE barcodes.project ADD CONSTRAINT project_unique UNIQUE (project);
