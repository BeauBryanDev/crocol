ALTER TABLE rag.documents DROP CONSTRAINT documents_collection_check;

ALTER TABLE rag.documents ADD CONSTRAINT documents_collection_check CHECK (collection IN
    ('VMM_Basin', 'ANH_Contracts', 'ANH_Regulatory', 'ANH_Reserves', 'Magdalena_River'));
