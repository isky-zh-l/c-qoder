ALTER TABLE app.folders ADD COLUMN chapter_id bigint;
CREATE INDEX folders_owner_chapter_parent_sort_idx
  ON app.folders (owner_id, chapter_id, parent_id, sort_order);
