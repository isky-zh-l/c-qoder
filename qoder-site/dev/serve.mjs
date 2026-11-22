// Local-only preview harness. It is outside both dist/ and functions/.
import http from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { Readable } from 'node:stream';
import { fileURLToPath } from 'node:url';
import { application } from '../functions/routes.mjs';

const root = fileURLToPath(new URL('..', import.meta.url));
const dist = join(root, 'dist');
const port = Number(process.env.PORT || 4176);
const saveDelayMs = Number(process.env.SAVE_DELAY_MS || 0);

const tables = {
  profiles: [],
  chapters: [],
  documents: [],
  assets: [],
  folders: [],
  usage_locks: [],
};

function now() {
  return new Date().toISOString();
}

function uniqueViolation() {
  return { code: '23505', message: 'duplicate key' };
}

function matches(row, filters) {
  return filters.every(({ column, value, op }) => {
    if (op === 'is') return row[column] === value;
    return row[column] === value;
  });
}

class Query {
  constructor(table) {
    this.table = table;
    this.filters = [];
    this.operation = 'select';
    this.payload = null;
    this.mode = 'many';
    this.limitValue = null;
    this.offsetValue = 0;
    this.orderSpec = null;
    this.conflict = null;
    this.insertIfAbsentMode = false;
  }

  select() {
    return this;
  }

  eq(column, value) {
    this.filters.push({ column, value, op: 'eq' });
    return this;
  }

  is(column, value) {
    this.filters.push({ column, value, op: 'is' });
    return this;
  }

  order(column, { ascending = true } = {}) {
    this.orderSpec = { column, ascending };
    return this;
  }

  limit(value) {
    this.limitValue = value;
    return this;
  }

  range(from, to) {
    this.offsetValue = Math.max(0, Number(from) || 0);
    this.limitValue = Math.max(0, Number(to) - Number(from) + 1) || 0;
    return this;
  }

  maybeSingle() {
    this.mode = 'maybeSingle';
    return this;
  }

  single() {
    this.mode = 'single';
    return this;
  }

  insert(row) {
    this.operation = 'insert';
    this.payload = row;
    return this;
  }

  insertIfAbsent(row, { onConflict } = {}) {
    this.operation = 'insert';
    this.insertIfAbsentMode = true;
    this.conflict = onConflict;
    this.payload = row;
    return this;
  }

  update(patch) {
    this.operation = 'update';
    this.payload = patch;
    return this;
  }

  delete() {
    this.operation = 'delete';
    return this;
  }

  run() {
    const list = tables[this.table];
    let data = list.filter((row) => matches(row, this.filters));

    if (this.operation === 'insert') {
      if (this.insertIfAbsentMode && this.conflict) {
        const keys = this.conflict.split(',').map((key) => key.trim());
        const exists = list.some((row) =>
          keys.every((key) => row[key] === this.payload[key]),
        );
        if (exists) return { data: [], error: null };
      }
      const duplicate = list.some((row) => {
        if (row.id === this.payload.id) return true;
        if (
          this.table === 'documents' &&
          row.owner_id === this.payload.owner_id &&
          row.title === this.payload.title
        ) {
          return true;
        }
        if (
          this.table === 'chapters' &&
          row.owner_id === this.payload.owner_id &&
          row.name === this.payload.name
        ) {
          return true;
        }
        if (
          this.table === 'folders' &&
          row.owner_id === this.payload.owner_id &&
          Number(row.parent_id) === Number(this.payload.parent_id) &&
          row.name === this.payload.name
        ) {
          return true;
        }
        if (
          this.table === 'profiles' &&
          row.owner_id === this.payload.owner_id
        ) {
          return true;
        }
        if (
          this.table === 'documents' &&
          this.payload.share_token &&
          row.share_token === this.payload.share_token
        ) {
          return true;
        }
        if (
          this.table === 'assets' &&
          row.object_path === this.payload.object_path
        ) {
          return true;
        }
        return false;
      });
      if (duplicate) return { data: null, error: uniqueViolation() };
      const row = structuredClone(this.payload);
      list.push(row);
      return { data: [structuredClone(row)], error: null };
    }

    if (this.operation === 'update') {
      if (!data.length) return { data: [], error: null };
      const patched = data.map((row) => ({
        ...structuredClone(row),
        ...structuredClone(this.payload),
      }));
      for (const proposal of patched) {
        const conflict = list.some((row) => {
          if (row.id === proposal.id) return false;
          if (
            this.table === 'documents' &&
            row.owner_id === proposal.owner_id &&
            row.title === proposal.title
          ) {
            return true;
          }
          if (
            this.table === 'chapters' &&
            row.owner_id === proposal.owner_id &&
            row.name === proposal.name
          ) {
            return true;
          }
          if (
            this.table === 'folders' &&
            row.owner_id === proposal.owner_id &&
            Number(row.parent_id) === Number(proposal.parent_id) &&
            row.name === proposal.name
          ) {
            return true;
          }
          return false;
        });
        if (conflict) return { data: null, error: uniqueViolation() };
      }
      for (let index = 0; index < data.length; index += 1) {
        Object.assign(data[index], patched[index]);
      }
      return { data: data.map((row) => structuredClone(row)), error: null };
    }

    if (this.operation === 'delete') {
      const ids = new Set(data.map((row) => row.id));
      for (let index = list.length - 1; index >= 0; index -= 1) {
        if (ids.has(list[index].id)) list.splice(index, 1);
      }
      return { data: data.map((row) => structuredClone(row)), error: null };
    }

    if (this.orderSpec) {
      const { column, ascending } = this.orderSpec;
      data = data.slice().sort((a, b) => {
        if (a[column] === b[column]) return 0;
        const result = a[column] < b[column] ? -1 : 1;
        return ascending ? result : -result;
      });
    }
    if (this.offsetValue) data = data.slice(this.offsetValue);
    if (this.limitValue !== null) data = data.slice(0, this.limitValue);
    return { data: data.map((row) => structuredClone(row)), error: null };
  }

  then(resolvePromise, rejectPromise) {
    try {
      const result = this.run();
      let data = result.data;
      if (!result.error) {
        if (this.mode === 'maybeSingle') data = data?.[0] ?? null;
        if (this.mode === 'single') data = data?.[0] ?? null;
      }
      return Promise.resolve({ data, error: result.error }).then(
        resolvePromise,
        rejectPromise,
      );
    } catch (error) {
      return Promise.reject(error).then(resolvePromise, rejectPromise);
    }
  }
}

const db = {
  from(table) {
    return new Query(table);
  },
};

const objects = new Map();
const storage = {
  async upload(path, bytes, { contentType }) {
    objects.set(path, { bytes, contentType });
    return { ok: true };
  },
  async download(path) {
    const record = objects.get(path);
    if (!record) {
      const error = new Error('not found');
      error.code = 'storage_object_not_found';
      throw error;
    }
    return new Response(record.bytes, {
      status: 200,
      headers: { 'content-type': record.contentType },
    });
  },
  async remove(paths) {
    for (const path of paths) objects.delete(path);
    return { ok: true };
  },
};

const fixtureUser = {
  user_id: 'local-alice',
  name: '本地预览用户',
  picture: '',
  site_id: 'local',
  host_id: 'local',
  session_expires_at: Math.floor(Date.now() / 1000) + 3600,
};

const demoMode = process.env.DEMO === '1';
const demoUser = {
  user_id: 'demo',
  name: '示例学习者',
  picture: '',
  site_id: 'local',
  host_id: 'local',
  session_expires_at: Math.floor(Date.now() / 1000) + 3600,
};

function getUser() {
  return demoMode ? demoUser : fixtureUser;
}

function requireUser() {
  return demoMode ? demoUser : fixtureUser;
}

const handle = application({
  db,
  storage,
  getUser,
  requireUser,
  onError: (error) => console.error('local route error:', error),
});

const mime = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
};

async function serveStatic(pathname, response) {
  const relative = normalize(pathname).replace(/^(\.\.(\/|\\|$))+/, '');
  let filePath = join(dist, relative);
  if (!filePath.startsWith(dist)) {
    response.writeHead(403).end('Forbidden');
    return;
  }
  try {
    const info = await stat(filePath);
    if (info.isDirectory()) filePath = join(filePath, 'index.html');
    const body = await readFile(filePath);
    response.writeHead(200, {
      'content-type': mime[extname(filePath)] || 'application/octet-stream',
      'cache-control': 'no-store',
    });
    response.end(body);
  } catch {
    const body = await readFile(join(dist, 'index.html'));
    response.writeHead(200, {
      'content-type': 'text/html; charset=utf-8',
      'cache-control': 'no-store',
    });
    response.end(body);
  }
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || '127.0.0.1'}`);
  if (url.pathname === '/__dev/quota') {
    const bytes = Number(url.searchParams.get('bytes') || '0');
    for (const profile of tables.profiles) {
      profile.storage_quota_bytes = bytes || null;
    }
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ ok: true, bytes }));
    return;
  }
  if (url.pathname === '/__dev/seed') {
    const count = Math.min(1500, Number(url.searchParams.get('count') || '0'));
    const profile = tables.profiles[0];
    if (!profile) {
      res.writeHead(409, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ error: 'session required first' }));
      return;
    }
    for (let index = 0; index < count; index += 1) {
      const id = 910000000000000 + index;
      const now = new Date().toISOString();
      tables.documents.push({
        id,
        owner_id: profile.owner_id,
        kind: 'note',
        title: `批量搜索文档 ${String(index).padStart(4, '0')}`,
        summary: index === 0 ? '超出加载上限的命中词' : '',
        chapter_id: null,
        folder_id: null,
        language: null,
        visibility: 'private',
        share_token: null,
        published_at: null,
        published_version: null,
        published_title: null,
        published_author: null,
        published_blocks: null,
        blocks: [
          {
            id: id + 1,
            block_type: 'rich_text',
            content: {
              module: 'paragraph',
              markdown:
                index === 0
                  ? '超出加载上限的命中词：千条之外仍可搜索'
                  : `批量内容 ${index}`,
            },
            asset_id: null,
            sort_order: 0,
          },
        ],
        is_favorite: false,
        favorite_order: 0,
        chapter_order: 0,
        folder_order: 0,
        library_order: index,
        version: 1,
        created_at: now,
        updated_at: now,
        deleted_at: null,
        original_chapter_id: null,
        original_folder_id: null,
        deleted_sort_order: null,
        deleted_title: null,
      });
    }
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify({ ok: true, count }));
    return;
  }
  if (url.pathname.startsWith('/functions/v1/app')) {
    if (
      saveDelayMs > 0 &&
      req.method === 'PUT' &&
      url.pathname.endsWith('/blocks')
    ) {
      await new Promise((resolve) => setTimeout(resolve, saveDelayMs));
    }
    const headers = new Headers();
    for (const [key, value] of Object.entries(req.headers)) {
      if (typeof value === 'string') headers.set(key, value);
    }
    const method = req.method || 'GET';
    const request = new Request(url, {
      method,
      headers,
      body:
        method === 'GET' || method === 'HEAD'
          ? undefined
          : Readable.toWeb(req),
      duplex: method === 'GET' || method === 'HEAD' ? undefined : 'half',
    });
    const result = await handle({ request });
    for (const [key, value] of result.headers) res.setHeader(key, value);
    res.statusCode = result.status;
    if (!result.body) {
      res.end();
      return;
    }
    const buffer = Buffer.from(await result.arrayBuffer());
    res.end(buffer);
    return;
  }
  await serveStatic(url.pathname, res);
});

server.listen(port, '127.0.0.1', () => {
  console.log(`Local preview: http://127.0.0.1:${port}/c/`);
  console.log(`Local API:     http://127.0.0.1:${port}/functions/v1/app/api/health`);
  console.log('Data is an in-memory fixture and disappears on restart.');
});
