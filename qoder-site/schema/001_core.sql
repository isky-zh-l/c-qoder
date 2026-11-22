CREATE TABLE app.profiles (
  id bigint PRIMARY KEY,
  owner_id text NOT NULL UNIQUE,
  display_name text NOT NULL,
  picture text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.chapters (
  id bigint PRIMARY KEY,
  owner_id text NOT NULL,
  name text NOT NULL,
  sort_order integer NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (owner_id, name)
);

CREATE TABLE app.documents (
  id bigint PRIMARY KEY,
  owner_id text NOT NULL,
  kind text NOT NULL,
  title text NOT NULL,
  summary text NOT NULL,
  chapter_id bigint,
  language text,
  visibility text NOT NULL,
  share_token text UNIQUE,
  published_at timestamptz,
  published_version integer,
  published_title text,
  published_author text,
  published_blocks jsonb,
  blocks jsonb NOT NULL,
  is_favorite boolean NOT NULL,
  favorite_order integer NOT NULL,
  chapter_order integer NOT NULL,
  library_order integer NOT NULL,
  version integer NOT NULL,
  created_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL,
  deleted_at timestamptz,
  original_chapter_id bigint,
  deleted_sort_order integer,
  UNIQUE (owner_id, title)
);

CREATE TABLE app.assets (
  id bigint PRIMARY KEY,
  owner_id text NOT NULL,
  object_path text NOT NULL UNIQUE,
  original_name text NOT NULL,
  mime_type text NOT NULL,
  size_bytes bigint NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX chapters_owner_sort_idx ON app.chapters (owner_id, sort_order);
CREATE INDEX documents_owner_deleted_idx ON app.documents (owner_id, deleted_at);
CREATE INDEX documents_owner_chapter_idx ON app.documents (owner_id, chapter_id);
CREATE INDEX documents_owner_favorite_idx ON app.documents (owner_id, is_favorite);
CREATE INDEX assets_owner_idx ON app.assets (owner_id);
