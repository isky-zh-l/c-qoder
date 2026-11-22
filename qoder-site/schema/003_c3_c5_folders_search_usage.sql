CREATE TABLE app.folders (
  id bigint PRIMARY KEY,
  owner_id text NOT NULL,
  parent_id bigint NOT NULL,
  name text NOT NULL,
  sort_order integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (owner_id, parent_id, name)
);

CREATE INDEX folders_owner_parent_sort_idx ON app.folders (owner_id, parent_id, sort_order);

ALTER TABLE app.documents ADD COLUMN folder_id bigint;
ALTER TABLE app.documents ADD COLUMN folder_order integer;
ALTER TABLE app.documents ADD COLUMN original_folder_id bigint;
ALTER TABLE app.profiles ADD COLUMN storage_quota_bytes bigint;

CREATE INDEX documents_owner_folder_idx ON app.documents (owner_id, folder_id);

CREATE TABLE app.usage_locks (
  owner_id text PRIMARY KEY,
  token text NOT NULL,
  expires_at timestamptz NOT NULL
);
