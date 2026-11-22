// Business routes for the Qoder Sites runtime. Dependency injection keeps the
// same handler runnable with credential-free local fakes.
import { UserContextError } from './auth.mjs';
import { AiPolishError, aiTitleFor, runAiPolish } from './ai/polish.mjs';

const SITE_TITLE = 'C 语言学习笔记';
const DEMO_OWNER_ID = 'demo';
// AI polish is limited to signed-in Qoder accounts in the final release.
const AI_ALLOW_DEMO = false;
const DEFAULT_CHAPTERS = [
  '起步与工具链',
  '变量与基本类型',
  '运算符与表达式',
  '分支与循环',
  '函数与作用域',
  '数组与字符串',
  '指针与内存',
  '结构体与联合体',
  '动态内存',
  '文件与 I/O',
  '预处理器与多文件',
  '调试与常见错误',
];
const DEMO_SEEDS = [
  {
    kind: 'note',
    title: '示例：模块化笔记',
    blocks: [
      { block_type: 'rich_text', content: { module: 'heading1', markdown: '示例：模块化笔记' } },
      { block_type: 'rich_text', content: { module: 'quote', markdown: '这是公开示例空间，可以直接编辑、插入模块、撤销和保存。' } },
      { block_type: 'rich_text', content: { module: 'heading2', markdown: '一、文字与列表' } },
      { block_type: 'rich_text', content: { module: 'bullet_list', markdown: '- **加粗**、*斜体*、<u>下划线</u>、~~删除线~~ 和 `行内代码`\n- ==默认高亮== 与 <mark data-tone="mint">薄荷绿高亮</mark>\n- [x] 已完成一项\n- [ ] 继续体验模块编辑' } },
      { block_type: 'rich_text', content: { module: 'heading2', markdown: '二、表格' } },
      { block_type: 'rich_text', content: { module: 'table', headers: ['模块', '用途', '状态'], rows: [['富文本', '段落、标题、列表', '可用'], ['代码', 'C/H 源码与结果', '可用'], ['公式', '行内与块级 LaTeX', '可用']] } },
      { block_type: 'rich_text', content: { module: 'heading2', markdown: '三、代码块' } },
      { block_type: 'code', content: { text: '#include <stdio.h>\n\nint main(void) {\n    int a[] = {1, 2, 3};\n    printf("%zu\\n", sizeof(a) / sizeof(a[0]));\n    return 0;\n}', language: 'c' } },
      { block_type: 'rich_text', content: { module: 'heading2', markdown: '四、块级公式' } },
      { block_type: 'formula', content: { latex: '\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}' } },
      { block_type: 'rich_text', content: { module: 'divider' } },
      { block_type: 'rich_text', content: { module: 'paragraph', markdown: '选中文字即可使用右侧文字样式；拖动模块左上角可以排序。' } },
    ],
  },
  {
    kind: 'source',
    language: 'c',
    title: '示例：C 源码模块',
    blocks: [
      { block_type: 'code', content: { text: '#include <stdio.h>\n\nint main(void) {\n    printf("Hello, C!\\n");\n    return 0;\n}\n', language: 'c' } },
    ],
  },
];
const BLOCK_TYPES = new Set([
  'rich_text',
  'code',
  'remark',
  'result',
  'image',
  'formula',
]);
const TEXT_MODULES = new Set([
  'paragraph',
  'heading1',
  'heading2',
  'heading3',
  'quote',
  'divider',
  'bullet_list',
  'ordered_list',
  'todo_list',
  'table',
]);
const RECYCLE_DAYS = 7;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_IMAGE_DIMENSION = 6000;
const MAX_IMPORT_BYTES = 5 * 1024 * 1024;
const DEFAULT_QUOTA_BYTES = 1024 * 1024 * 1024;
const USAGE_LOCK_MS = 120000;
const FOLDER_COLUMNS = 'id,owner_id,chapter_id,parent_id,name,sort_order,created_at';
const DOC_COLUMNS = [
  'id',
  'owner_id',
  'kind',
  'title',
  'summary',
  'chapter_id',
  'language',
  'visibility',
  'share_token',
  'published_at',
  'published_version',
  'published_title',
  'published_author',
  'published_blocks',
  'blocks',
  'is_favorite',
  'favorite_order',
  'chapter_order',
  'library_order',
  'version',
  'created_at',
  'updated_at',
  'deleted_at',
  'original_chapter_id',
  'deleted_title',
  'folder_id',
  'folder_order',
  'original_folder_id',
].join(',');

export class AppError extends Error {
  constructor(code, status, message, details = {}) {
    super(message);
    this.name = 'AppError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

const nowIso = () => new Date().toISOString();

function randomId() {
  const bytes = crypto.getRandomValues(new Uint8Array(6));
  let value = 0;
  for (const byte of bytes) value = value * 256 + byte;
  return value || 1;
}

function randomToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(24));
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'private, no-store',
      pragma: 'no-cache',
      'x-content-type-options': 'nosniff',
      ...extraHeaders,
    },
  });
}

function empty(status = 204, extraHeaders = {}) {
  return new Response(null, {
    status,
    headers: {
      'cache-control': 'private, no-store',
      pragma: 'no-cache',
      ...extraHeaders,
    },
  });
}

function contractError(error) {
  return json(
    {
      error: {
        code: error.code || 'request_failed',
        message: error.message || '请求失败',
        details: error.details || {},
      },
    },
    error.status || 400,
  );
}

function dbFailure(result, conflict) {
  if (!result?.error) return result?.data;
  const code = String(result.error.code || '');
  if (code === '23505' && conflict) throw conflict;
  console.error('cqoder_db_error', code || 'unknown');
  throw new AppError('database_unavailable', 503, '数据服务暂时不可用，请稍后重试');
}

function first(result, conflict) {
  const data = dbFailure(result, conflict);
  return Array.isArray(data) ? data[0] ?? null : data ?? null;
}

export async function persistOrder({
  db,
  table,
  ownerId,
  updates,
  previousById,
  field,
  scope,
}) {
  const applied = [];
  try {
    for (const update of updates) {
      const result = await db
        .from(table)
        .update({ [field]: update.order })
        .eq('id', update.id)
        .eq('owner_id', ownerId)
        .select('id');
      if (result.error) {
        throw new AppError(
          'order_write_failed',
          503,
          '排序没有完全保存，请刷新后重试',
          { scope },
        );
      }
      if (!result.data?.length) {
        throw new AppError(
          'order_conflict',
          409,
          '排序目标已变化，请刷新后重试',
          { scope },
        );
      }
      applied.push(update);
    }
  } catch (error) {
    let rollbackIncomplete = false;
    for (const update of applied.reverse()) {
      const rollback = await db
        .from(table)
        .update({ [field]: previousById.get(update.id) })
        .eq('id', update.id)
        .eq('owner_id', ownerId)
        .select('id');
      if (rollback.error || !rollback.data?.length) {
        rollbackIncomplete = true;
        break;
      }
    }
    if (rollbackIncomplete) {
      throw new AppError(
        'order_write_failed',
        503,
        '排序保存失败且回退未完成，请刷新后核对顺序',
        { scope },
      );
    }
    if (error instanceof AppError) throw error;
    throw new AppError(
      'order_write_failed',
      503,
      '排序没有保存，请刷新后重试',
      { scope },
    );
  }
}

async function readJson(request, limit = 64 * 1024) {
  if (!request.headers.get('content-type')?.startsWith('application/json')) {
    throw new AppError('invalid_input', 400, '请求格式无效');
  }
  const length = Number(request.headers.get('content-length') || '0');
  if (Number.isFinite(length) && length > limit) {
    throw new AppError('payload_too_large', 413, '请求内容过大');
  }
  const reader = request.body?.getReader();
  if (!reader) throw new AppError('invalid_input', 400, '请求内容为空');
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) {
        await reader.cancel().catch(() => {});
        throw new AppError('payload_too_large', 413, '请求内容过大');
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  try {
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  } catch {
    throw new AppError('invalid_input', 400, '请求内容不是有效 JSON');
  }
}

function cleanText(value, max, field = '内容') {
  if (typeof value !== 'string') {
    throw new AppError('invalid_input', 400, `${field}格式无效`);
  }
  const text = value.trim();
  if (!text) throw new AppError('invalid_input', 400, `${field}不能为空`);
  if (Array.from(text).length > max) {
    throw new AppError('invalid_input', 400, `${field}不能超过 ${max} 个字符`);
  }
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(text)) {
    throw new AppError('invalid_input', 400, `${field}包含无效字符`);
  }
  return text;
}

function safeInteger(value, field = 'ID') {
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new AppError('invalid_input', 400, `${field}无效`);
  }
  return value;
}

function serializeProfile(profile) {
  return {
    id: Number(profile.id),
    email: 'Qoder 账号',
    display_name: profile.display_name,
    bio: '',
    avatar_asset_id: null,
    email_verified_at: profile.created_at,
    is_enabled: true,
    is_admin: false,
    is_demo: profile.owner_id === DEMO_OWNER_ID,
    created_at: profile.created_at,
  };
}

function publicShareUrl(token) {
  return token ? `/c/#/p/${token}` : null;
}

function publicationOut(doc) {
  return {
    visibility: doc.visibility === 'public' ? 'public' : 'private',
    share_token: doc.visibility === 'public' ? doc.share_token || null : null,
    share_url:
      doc.visibility === 'public' ? publicShareUrl(doc.share_token) : null,
    published_at: doc.visibility === 'public' ? doc.published_at || null : null,
    published_version:
      doc.visibility === 'public' ? doc.published_version ?? null : null,
  };
}

function sortedBlocks(blocks) {
  return (Array.isArray(blocks) ? blocks : [])
    .slice()
    .sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0));
}

function folderPath(folders, folderId) {
  if (!folderId) return { ids: [], names: [], label: null };
  const byId = new Map(
    (folders || []).map((folder) => [Number(folder.id), folder]),
  );
  const ids = [];
  const names = [];
  let current = Number(folderId);
  const seen = new Set();
  while (current && !seen.has(current)) {
    seen.add(current);
    const folder = byId.get(current);
    if (!folder) break;
    ids.unshift(current);
    names.unshift(folder.name);
    current = Number(folder.parent_id || 0);
  }
  return {
    ids,
    names,
    label: names.length ? names.join(' / ') : null,
  };
}

function folderParentId(folder) {
  const parent = Number(folder.parent_id || 0);
  return parent > 0 ? parent : 0;
}

function rootFolderParent(chapterId) {
  return -Number(chapterId);
}

function rootParentIds(chapterId) {
  return new Set([0, rootFolderParent(chapterId)]);
}

function documentOut(doc, chapterNames, folders = []) {
  const blocks = sortedBlocks(doc.blocks);
  const folder = folderPath(folders, doc.folder_id);
  return {
    id: Number(doc.id),
    kind: doc.kind,
    title: doc.title,
    summary: doc.summary || '',
    chapter_id: doc.chapter_id === null ? null : Number(doc.chapter_id),
    chapter_name:
      doc.chapter_id === null
        ? null
        : chapterNames.get(Number(doc.chapter_id)) || null,
    folder_id: doc.folder_id === null || doc.folder_id === undefined
      ? null
      : Number(doc.folder_id),
    folder_name: folder.names.at(-1) || null,
    folder_path: folder.label,
    language: doc.language || null,
    visibility: doc.visibility === 'public' ? 'public' : 'private',
    is_favorite: Boolean(doc.is_favorite),
    version: Number(doc.version),
    created_at: doc.created_at,
    updated_at: doc.updated_at,
    share_token: doc.visibility === 'public' ? doc.share_token || null : null,
    share_url:
      doc.visibility === 'public' ? publicShareUrl(doc.share_token) : null,
    published_at: doc.visibility === 'public' ? doc.published_at || null : null,
    published_version:
      doc.visibility === 'public' ? doc.published_version ?? null : null,
    blocks,
  };
}

function stripMarkdown(value) {
  return String(value || '')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
    .replace(/<[^>]+>/g, '')
    .replace(/[`*_~>#|]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function summarize(blocks) {
  for (const block of sortedBlocks(blocks)) {
    if (block.block_type !== 'rich_text' && block.block_type !== 'remark') {
      continue;
    }
    const moduleName =
      typeof block.content?.module === 'string' ? block.content.module : '';
    if (moduleName.startsWith('heading')) continue;
    const markdown =
      typeof block.content?.markdown === 'string' ? block.content.markdown : '';
    const text = stripMarkdown(markdown);
    if (text) return Array.from(text).slice(0, 120).join('');
  }
  return '';
}

function emptyBlocks(kind, language) {
  if (kind === 'source') {
    return [
      {
        id: randomId(),
        block_type: 'code',
        content: { text: '', language: language || 'c' },
        asset_id: null,
        sort_order: 0,
      },
    ];
  }
  return [
    {
      id: randomId(),
      block_type: 'rich_text',
      content: { module: 'paragraph', markdown: '' },
      asset_id: null,
      sort_order: 0,
    },
  ];
}

function collectAssetIds(value, output) {
  if (value === null || value === undefined) return;
  if (Array.isArray(value)) {
    for (const item of value) collectAssetIds(item, output);
    return;
  }
  if (typeof value === 'object') {
    if (Number.isSafeInteger(value.asset_id) && value.asset_id > 0) {
      output.add(value.asset_id);
    }
    for (const item of Object.values(value)) collectAssetIds(item, output);
    return;
  }
  if (typeof value === 'string') {
    const pattern = /\/assets\/(\d+)\/(?:file|download)/g;
    let match;
    while ((match = pattern.exec(value))) output.add(Number(match[1]));
  }
}

function detectImage(bytes) {
  if (
    bytes.length >= 24 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  ) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    return {
      mime: 'image/png',
      ext: 'png',
      width: view.getUint32(16),
      height: view.getUint32(20),
    };
  }
  if (bytes.length >= 10 && bytes[0] === 0x47 && bytes[1] === 0x49 && bytes[2] === 0x46) {
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    return {
      mime: 'image/gif',
      ext: 'gif',
      width: view.getUint16(6, true),
      height: view.getUint16(8, true),
    };
  }
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    let width = 0;
    let height = 0;
    for (let index = 2; index + 9 < bytes.length; ) {
      if (bytes[index] !== 0xff) {
        index += 1;
        continue;
      }
      const marker = bytes[index + 1];
      if (marker === 0xd8 || marker === 0xd9) {
        index += 2;
        continue;
      }
      const length = (bytes[index + 2] << 8) | bytes[index + 3];
      if (length < 2) break;
      if (
        (marker >= 0xc0 && marker <= 0xc3) ||
        (marker >= 0xc5 && marker <= 0xc7) ||
        (marker >= 0xc9 && marker <= 0xcb) ||
        (marker >= 0xcd && marker <= 0xcf)
      ) {
        height = (bytes[index + 5] << 8) | bytes[index + 6];
        width = (bytes[index + 7] << 8) | bytes[index + 8];
        break;
      }
      index += 2 + length;
    }
    return { mime: 'image/jpeg', ext: 'jpg', width, height };
  }
  if (
    bytes.length >= 30 &&
    String.fromCharCode(...bytes.slice(0, 4)) === 'RIFF' &&
    String.fromCharCode(...bytes.slice(8, 12)) === 'WEBP'
  ) {
    return { mime: 'image/webp', ext: 'webp', width: 0, height: 0 };
  }
  return null;
}

function safeOriginalName(name, fallback) {
  const cleaned = String(name || '')
    .replace(/[\\/]/g, '_')
    .replace(/[\u0000-\u001f]/g, '')
    .trim()
    .slice(0, 120);
  return cleaned || fallback;
}

function sourceExtension(language) {
  return language === 'h' ? 'h' : 'c';
}

function splitTableRow(line) {
  const cells = [];
  let current = '';
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '\\' && line[index + 1] === '|') {
      current += '|';
      index += 1;
      continue;
    }
    if (char === '|') {
      cells.push(current.trim());
      current = '';
      continue;
    }
    current += char;
  }
  cells.push(current.trim());
  if (line.trim().startsWith('|') && cells[0] === '') cells.shift();
  if (line.trim().endsWith('|') && cells[cells.length - 1] === '') cells.pop();
  return cells;
}

function isTableSeparator(line) {
  if (!line.includes('|')) return false;
  const cells = splitTableRow(line);
  return (
    cells.length > 0 &&
    cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()))
  );
}

function parseMarkdownBlocks(text) {
  const lines = text.replace(/\r\n?/g, '\n').split('\n');
  const blocks = [];
  let paragraph = [];
  let index = 0;
  let id = 1;
  const push = (blockType, content) => {
    blocks.push({
      id: id++,
      block_type: blockType,
      content,
      asset_id: null,
      sort_order: blocks.length,
    });
  };
  const flush = () => {
    if (!paragraph.length) return;
    const markdown = paragraph.join('\n').trim();
    if (markdown) push('rich_text', { module: 'paragraph', markdown });
    paragraph = [];
  };
  while (index < lines.length) {
    const line = lines[index];
    const fence = line.match(/^(`{3,})([A-Za-z0-9_+-]*)\s*$/);
    if (fence) {
      flush();
      const code = [];
      const closing = new RegExp(`^\`{${fence[1].length},}\\s*$`);
      index += 1;
      while (index < lines.length && !closing.test(lines[index])) {
        code.push(lines[index]);
        index += 1;
      }
      if (index < lines.length) index += 1;
      const language = fence[2].toLowerCase();
      push('code', {
        text: code.join('\n'),
        language: language === 'c' || language === 'h' ? language : 'text',
      });
      continue;
    }
    if (!line.trim()) {
      flush();
      index += 1;
      continue;
    }
    const trimmed = line.trim();
    if (trimmed === '$$') {
      flush();
      const latex = [];
      index += 1;
      let closed = false;
      while (index < lines.length) {
        if (lines[index].trim() === '$$') {
          closed = true;
          index += 1;
          break;
        }
        latex.push(lines[index]);
        index += 1;
      }
      if (closed) {
        push('formula', { latex: latex.join('\n').trim() });
        continue;
      }
      paragraph.push('$$', ...latex);
      continue;
    }
    if (
      trimmed.startsWith('$$') &&
      trimmed.endsWith('$$') &&
      trimmed.length > 4
    ) {
      flush();
      push('formula', { latex: trimmed.slice(2, -2).trim() });
      index += 1;
      continue;
    }
    if (trimmed.startsWith('$$')) {
      const latex = [trimmed.slice(2)];
      let cursor = index + 1;
      let closed = false;
      while (cursor < lines.length) {
        const current = lines[cursor].trim();
        if (current.endsWith('$$')) {
          latex.push(current.slice(0, -2));
          closed = true;
          cursor += 1;
          break;
        }
        latex.push(lines[cursor]);
        cursor += 1;
      }
      if (closed) {
        flush();
        push('formula', { latex: latex.join('\n').trim() });
        index = cursor;
        continue;
      }
    }
    if (
      line.includes('|') &&
      index + 1 < lines.length &&
      isTableSeparator(lines[index + 1])
    ) {
      const headers = splitTableRow(line);
      const separator = splitTableRow(lines[index + 1]);
      if (headers.length > 0 && separator.length === headers.length) {
        flush();
        const rows = [];
        index += 2;
        while (
          index < lines.length &&
          lines[index].trim() &&
          lines[index].includes('|')
        ) {
          const cells = splitTableRow(lines[index]);
          rows.push(
            Array.from({ length: headers.length }, (_, cellIndex) =>
              String(cells[cellIndex] ?? ''),
            ),
          );
          index += 1;
        }
        push('rich_text', { module: 'table', headers, rows });
        continue;
      }
    }
    if (/^\s*---+\s*$/.test(line) || /^\s*\*\*\*+\s*$/.test(line)) {
      flush();
      push('rich_text', { module: 'divider' });
      index += 1;
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      flush();
      push('rich_text', {
        module: `heading${heading[1].length}`,
        markdown: heading[2].trim(),
      });
      index += 1;
      continue;
    }
    if (/^\s*>\s?/.test(line)) {
      flush();
      const quoted = [];
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quoted.push(lines[index].replace(/^\s*>\s?/, ''));
        index += 1;
      }
      push('rich_text', {
        module: 'quote',
        markdown: quoted.join('\n').trim(),
      });
      continue;
    }
    const listMatch = line.match(/^\s*([-*+]|\d+\.)\s+/);
    if (listMatch) {
      flush();
      const ordered = /\d+\./.test(listMatch[1]);
      const todo = /^\s*[-*+]\s+\[[ xX]\]\s+/.test(line);
      const items = [];
      while (index < lines.length) {
        const current = lines[index];
        if (!current.trim()) break;
        if (ordered && !/^\s*\d+\.\s+/.test(current)) break;
        if (!ordered && !/^\s*[-*+]\s+/.test(current)) break;
        if (todo) {
          const item = current.match(
            /^\s*[-*+]\s+\[([ xX])\]\s+(.*)$/,
          );
          if (!item) break;
          items.push(`- [${item[1].toLowerCase() === 'x' ? 'x' : ' '}] ${item[2]}`);
        } else {
          items.push(current.trim());
        }
        index += 1;
      }
      push('rich_text', {
        module: todo ? 'todo_list' : ordered ? 'ordered_list' : 'bullet_list',
        markdown: items.join('\n'),
      });
      continue;
    }
    paragraph.push(line);
    index += 1;
  }
  flush();
  if (!blocks.length) {
    push('rich_text', { module: 'paragraph', markdown: '' });
  }
  return blocks;
}

export function application({ db, storage, getUser, requireUser, onError }) {
  const fail = (code, status, message, details = {}) => {
    throw new AppError(code, status, message, details);
  };

  async function currentProfile(user) {
    const existing = first(
      await db
        .from('profiles')
        .select('id,owner_id,display_name,picture,created_at,storage_quota_bytes')
        .eq('owner_id', user.user_id)
        .limit(1),
    );
    if (existing) return existing;
    const row = {
      id: randomId(),
      owner_id: user.user_id,
      display_name: (user.name || '').trim().slice(0, 80) || 'C 学习者',
      picture: (user.picture || '').slice(0, 1024),
      created_at: nowIso(),
    };
    const inserted = dbFailure(
      await db
        .from('profiles')
        .insertIfAbsent(row, { onConflict: 'owner_id' })
        .select('id,owner_id,display_name,picture,created_at,storage_quota_bytes'),
    );
    if (inserted?.length) return inserted[0];
    const raced = first(
      await db
        .from('profiles')
        .select('id,owner_id,display_name,picture,created_at,storage_quota_bytes')
        .eq('owner_id', user.user_id)
        .limit(1),
    );
    if (!raced) fail('profile_unavailable', 503, '个人空间暂时不可用');
    return raced;
  }

  async function ensureChapters(ownerId) {
    const existing = dbFailure(
      await db
        .from('chapters')
        .select('id')
        .eq('owner_id', ownerId)
        .limit(1),
    );
    if (existing?.length) return;
    for (let index = 0; index < DEFAULT_CHAPTERS.length; index += 1) {
      await db.from('chapters').insertIfAbsent(
        {
          id: randomId(),
          owner_id: ownerId,
          name: DEFAULT_CHAPTERS[index],
          sort_order: index,
          created_at: nowIso(),
        },
        { onConflict: 'owner_id,name' },
      );
    }
  }

  async function authenticated(user) {
    const profile = await currentProfile(user);
    await ensureChapters(profile.owner_id);
    return profile;
  }

  async function ensureDemoSeed() {
    try {
      const demoProfile = await currentProfile({
        user_id: DEMO_OWNER_ID,
        name: '示例学习者',
        picture: '',
      });
      const existing = await readOwnerRows(
        'documents',
        'id,title,deleted_at',
        DEMO_OWNER_ID,
      );
      const titles = new Set(
        existing.filter((row) => row.deleted_at === null).map((row) => row.title),
      );
      let chapters = await chapterRows(DEMO_OWNER_ID);
      if (!chapters.length) {
        await ensureChapters(DEMO_OWNER_ID);
        chapters = await chapterRows(DEMO_OWNER_ID);
      }
      const chapterId = chapters.length ? Number(chapters[0].id) : null;
      for (const seed of DEMO_SEEDS) {
        if (titles.has(seed.title)) continue;
        const blocks = seed.blocks.map((block, index) => ({
          id: randomId(),
          block_type: block.block_type,
          content: block.content,
          asset_id: null,
          sort_order: index,
        }));
        try {
          await createDocumentRow(
            DEMO_OWNER_ID,
            seed.kind,
            seed.title,
            chapterId,
            seed.language || null,
            blocks,
          );
        } catch (error) {
          if (error?.status !== 409) {
            console.error('demo_seed_insert_failed', error?.message || error);
          }
        }
      }
      return demoProfile;
    } catch (error) {
      console.error('demo_seed_failed', error?.message || error);
      return null;
    }
  }

  async function readOwnerRows(table, columns, ownerId) {
    const pageSize = 500;
    let offset = 0;
    const rows = [];
    while (true) {
      const result = await db
        .from(table)
        .select(columns)
        .eq('owner_id', ownerId)
        .order('id', { ascending: true })
        .range(offset, offset + pageSize - 1);
      const page = dbFailure(result);
      if (!page?.length) break;
      rows.push(...page);
      if (page.length < pageSize) break;
      offset += page.length;
    }
    return rows;
  }

  async function chapterRows(ownerId) {
    const rows = await readOwnerRows(
      'chapters',
      'id,owner_id,name,sort_order,created_at',
      ownerId,
    );
    return rows.sort(
      (a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0),
    );
  }

  async function allDocuments(ownerId) {
    return readOwnerRows('documents', DOC_COLUMNS, ownerId);
  }

  async function allFolders(ownerId) {
    const rows = await readOwnerRows('folders', FOLDER_COLUMNS, ownerId);
    return rows.sort(
      (a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0),
    );
  }

  async function allAssets(ownerId) {
    return readOwnerRows(
      'assets',
      'id,owner_id,object_path,original_name,mime_type,size_bytes,created_at',
      ownerId,
    );
  }

  async function chapterMap(ownerId) {
    const rows = await chapterRows(ownerId);
    return new Map(rows.map((row) => [Number(row.id), row.name]));
  }

  async function ownedDocument(ownerId, id, { deleted = false } = {}) {
    const doc = first(
      await db
        .from('documents')
        .select(DOC_COLUMNS)
        .eq('id', id)
        .eq('owner_id', ownerId)
        .limit(1),
    );
    if (!doc) fail('not_found', 404, '文档不存在');
    if (deleted ? doc.deleted_at === null : doc.deleted_at !== null) {
      fail('not_found', 404, '文档不存在');
    }
    return doc;
  }

  async function requireChapter(ownerId, chapterId) {
    if (chapterId === null) return null;
    const id = safeInteger(chapterId, '章节');
    const chapter = first(
      await db
        .from('chapters')
        .select('id,name')
        .eq('id', id)
        .eq('owner_id', ownerId)
        .limit(1),
    );
    if (!chapter) fail('not_found', 404, '章节不存在');
    return chapter;
  }

  async function nextOrder(ownerId, field, chapterId = undefined) {
    const docs = await allDocuments(ownerId);
    const values = docs
      .filter((doc) => doc.deleted_at === null)
      .filter((doc) =>
        chapterId === undefined ? true : Number(doc.chapter_id) === chapterId,
      )
      .map((doc) => Number(doc[field] || 0));
    return values.length ? Math.max(...values) + 1 : 0;
  }

  async function nextFolderOrder(ownerId, folderId) {
    const docs = await allDocuments(ownerId);
    const values = docs
      .filter((doc) => doc.deleted_at === null)
      .filter((doc) => {
        const current = doc.folder_id === null || doc.folder_id === undefined
          ? 0
          : Number(doc.folder_id);
        return current === Number(folderId || 0);
      })
      .map((doc) => Number(doc.folder_order || 0));
    return values.length ? Math.max(...values) + 1 : 0;
  }

  async function requireFolder(ownerId, folderId) {
    if (folderId === null || folderId === undefined || Number(folderId) === 0) {
      return null;
    }
    const id = safeInteger(Number(folderId), '文件夹');
    const folder = first(
      await db
        .from('folders')
        .select(FOLDER_COLUMNS)
        .eq('id', id)
        .eq('owner_id', ownerId)
        .limit(1),
    );
    if (!folder) fail('not_found', 404, '文件夹不存在');
    return folder;
  }

  function descendantFolderIds(folders, rootId) {
    const output = new Set([Number(rootId)]);
    let changed = true;
    while (changed) {
      changed = false;
      for (const folder of folders) {
        if (
          output.has(Number(folder.parent_id)) &&
          !output.has(Number(folder.id))
        ) {
          output.add(Number(folder.id));
          changed = true;
        }
      }
    }
    return output;
  }

  function folderOut(folder, docs, folders) {
    const id = Number(folder.id);
    return {
      id,
      chapter_id:
        folder.chapter_id === null || folder.chapter_id === undefined
          ? null
          : Number(folder.chapter_id),
      parent_id: folderParentId(folder),
      name: folder.name,
      sort_order: Number(folder.sort_order || 0),
      document_count: docs.filter(
        (doc) =>
          doc.deleted_at === null &&
          doc.folder_id !== null &&
          doc.folder_id !== undefined &&
          Number(doc.folder_id) === id,
      ).length,
      child_count: folders.filter(
        (item) =>
          Number(item.parent_id || 0) === id &&
          (item.chapter_id === null || item.chapter_id === undefined
            ? folder.chapter_id === null || folder.chapter_id === undefined
            : Number(item.chapter_id) === Number(folder.chapter_id)),
      ).length,
      path: folderPath(folders, id).label,
    };
  }

  function jsonByteLength(value) {
    if (value === null || value === undefined) return 0;
    try {
      return new TextEncoder().encode(JSON.stringify(value)).byteLength;
    } catch {
      return 0;
    }
  }

  async function usageFor(ownerId, profile, data = null) {
    const [docs, assets, folders] = data
      ? [data.docs, data.assets, data.folders]
      : await Promise.all([
          allDocuments(ownerId),
          allAssets(ownerId),
          allFolders(ownerId),
        ]);
    let noteBytes = 0;
    let sourceBytes = 0;
    let recycleBytes = 0;
    let publicationBytes = 0;
    let documentCount = 0;
    let recycleCount = 0;
    for (const doc of docs) {
      const blockBytes = jsonByteLength(doc.blocks);
      if (doc.deleted_at !== null) {
        recycleCount += 1;
        recycleBytes += blockBytes;
        continue;
      }
      documentCount += 1;
      if (doc.kind === 'source') sourceBytes += blockBytes;
      else noteBytes += blockBytes;
      if (doc.visibility === 'public') {
        publicationBytes += jsonByteLength(doc.published_blocks);
      }
    }
    const imageBytes = assets.reduce(
      (sum, asset) => sum + Number(asset.size_bytes || 0),
      0,
    );
    const usedBytes =
      noteBytes +
      sourceBytes +
      recycleBytes +
      publicationBytes +
      imageBytes;
    const quotaBytes =
      Number(profile.storage_quota_bytes || 0) > 0
        ? Number(profile.storage_quota_bytes)
        : DEFAULT_QUOTA_BYTES;
    return {
      quota_bytes: quotaBytes,
      used_bytes: usedBytes,
      reserved_bytes: 0,
      remaining_bytes: Math.max(0, quotaBytes - usedBytes),
      source_bytes: sourceBytes,
      note_bytes: noteBytes,
      image_bytes: imageBytes,
      recycle_bytes: recycleBytes,
      publication_bytes: publicationBytes,
      asset_count: assets.length,
      document_count: documentCount,
      recycle_count: recycleCount,
      folder_count: folders.length,
      over_quota: usedBytes > quotaBytes,
      limits: {
        max_file_bytes: MAX_IMPORT_BYTES,
        max_image_bytes: MAX_IMAGE_BYTES,
        image_max_dimension: MAX_IMAGE_DIMENSION,
      },
      recycle_retention_days: RECYCLE_DAYS,
      account_deletion_retention_days: 0,
    };
  }

  function assertQuota(profile, nextUsed) {
    const quota =
      Number(profile.storage_quota_bytes || 0) > 0
        ? Number(profile.storage_quota_bytes)
        : DEFAULT_QUOTA_BYTES;
    if (nextUsed > quota) {
      fail('quota_exceeded', 413, '空间用量已超出额度，请清理内容后再试', {
        quota_bytes: quota,
        used_bytes: nextUsed,
      });
    }
  }

  async function assertNewBlocksFit(ownerId, profile, blocks) {
    const usage = await usageFor(ownerId, profile);
    assertQuota(profile, usage.used_bytes + jsonByteLength(blocks));
  }

  async function assertSavedBlocksFit(ownerId, profile, doc, blocks) {
    const usage = await usageFor(ownerId, profile);
    const previous = jsonByteLength(doc.blocks);
    assertQuota(
      profile,
      usage.used_bytes - previous + jsonByteLength(blocks),
    );
  }

  async function acquireUsageLock(ownerId) {
    const token = randomToken();
    const expiresAt = new Date(Date.now() + USAGE_LOCK_MS).toISOString();
    for (let attempt = 0; attempt < 12; attempt += 1) {
      const inserted = await db
        .from('usage_locks')
        .insertIfAbsent(
          { owner_id: ownerId, token, expires_at: expiresAt },
          { onConflict: 'owner_id' },
        )
        .select('owner_id');
      if (inserted.error) {
        fail('usage_lock_failed', 503, '空间写入锁暂时不可用');
      }
      if (inserted.data?.length) return token;
      const existing = first(
        await db
          .from('usage_locks')
          .select('owner_id,token,expires_at')
          .eq('owner_id', ownerId)
          .limit(1),
      );
      if (existing && Date.parse(existing.expires_at) < Date.now()) {
        const renewed = await db
          .from('usage_locks')
          .update({ token, expires_at: expiresAt })
          .eq('owner_id', ownerId)
          .eq('token', existing.token)
          .select('owner_id');
        if (renewed.data?.length) return token;
      }
      await new Promise((resolve) => setTimeout(resolve, 60));
    }
    fail('usage_busy', 503, '空间正在写入，请稍后重试');
  }

  async function releaseUsageLock(ownerId, token) {
    try {
      await db
        .from('usage_locks')
        .delete()
        .eq('owner_id', ownerId)
        .eq('token', token);
    } catch {
      // The lease expires if cleanup fails.
    }
  }

  async function withUsageLock(ownerId, callback) {
    const token = await acquireUsageLock(ownerId);
    try {
      return await callback();
    } finally {
      await releaseUsageLock(ownerId, token);
    }
  }

  function blockSearchText(block) {
    const content = block?.content || {};
    const parts = [];
    if (typeof content.markdown === 'string') parts.push(content.markdown);
    if (typeof content.text === 'string') parts.push(content.text);
    if (typeof content.latex === 'string') parts.push(content.latex);
    if (typeof content.alt === 'string') parts.push(content.alt);
    if (typeof content.caption === 'string') parts.push(content.caption);
    if (Array.isArray(content.headers)) parts.push(content.headers.join(' '));
    if (Array.isArray(content.rows)) {
      for (const row of content.rows) {
        if (Array.isArray(row)) parts.push(row.join(' '));
      }
    }
    return parts.join('\n');
  }

  function documentSearchText(doc) {
    return [
      doc.title,
      doc.summary || '',
      ...sortedBlocks(doc.blocks).map(blockSearchText),
    ]
      .filter(Boolean)
      .join('\n');
  }

  function searchSnippet(text, query) {
    const compact = text.replace(/\s+/g, ' ').trim();
    if (!compact) return '';
    const lower = compact.toLowerCase();
    const index = lower.indexOf(query.toLowerCase());
    if (index < 0) return Array.from(compact).slice(0, 120).join('');
    const start = Math.max(0, index - 45);
    const end = Math.min(compact.length, index + query.length + 75);
    return `${start > 0 ? '…' : ''}${compact.slice(start, end)}${
      end < compact.length ? '…' : ''
    }`;
  }

  function buildZip(files) {
    const crcTable = (() => {
      const table = new Uint32Array(256);
      for (let index = 0; index < 256; index += 1) {
        let value = index;
        for (let bit = 0; bit < 8; bit += 1) {
          value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
        }
        table[index] = value >>> 0;
      }
      return table;
    })();
    const crc32 = (bytes) => {
      let crc = 0xffffffff;
      for (const byte of bytes) {
        crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
      }
      return (crc ^ 0xffffffff) >>> 0;
    };
    const localParts = [];
    const centralParts = [];
    let offset = 0;
    for (const file of files) {
      const name = new TextEncoder().encode(file.name);
      const bytes = file.bytes;
      const crc = crc32(bytes);
      const local = new Uint8Array(30 + name.length);
      const localView = new DataView(local.buffer);
      localView.setUint32(0, 0x04034b50, true);
      localView.setUint16(4, 20, true);
      localView.setUint16(6, 0x0800, true);
      localView.setUint16(8, 0, true);
      localView.setUint32(14, crc, true);
      localView.setUint32(18, bytes.length, true);
      localView.setUint32(22, bytes.length, true);
      localView.setUint16(26, name.length, true);
      local.set(name, 30);
      localParts.push(local, bytes);
      const central = new Uint8Array(46 + name.length);
      const centralView = new DataView(central.buffer);
      centralView.setUint32(0, 0x02014b50, true);
      centralView.setUint16(4, 20, true);
      centralView.setUint16(6, 20, true);
      centralView.setUint16(8, 0x0800, true);
      centralView.setUint16(10, 0, true);
      centralView.setUint32(16, crc, true);
      centralView.setUint32(20, bytes.length, true);
      centralView.setUint32(24, bytes.length, true);
      centralView.setUint16(28, name.length, true);
      centralView.setUint32(42, offset, true);
      central.set(name, 46);
      centralParts.push(central);
      offset += local.length + bytes.length;
    }
    const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
    const end = new Uint8Array(22);
    const endView = new DataView(end.buffer);
    endView.setUint32(0, 0x06054b50, true);
    endView.setUint16(8, files.length, true);
    endView.setUint16(10, files.length, true);
    endView.setUint32(12, centralSize, true);
    endView.setUint32(16, offset, true);
    const all = [...localParts, ...centralParts, end];
    const total = all.reduce((sum, part) => sum + part.length, 0);
    const output = new Uint8Array(total);
    let cursor = 0;
    for (const part of all) {
      output.set(part, cursor);
      cursor += part.length;
    }
    return output;
  }

  async function createDocumentRow(
    ownerId,
    kind,
    title,
    chapterId,
    language,
    blocks,
    folderId = null,
  ) {
    const chapters = await chapterRows(ownerId);
    if (chapterId !== null) {
      if (!chapters.some((chapter) => Number(chapter.id) === chapterId)) {
        fail('not_found', 404, '章节不存在');
      }
    }
    const folder = await requireFolder(ownerId, folderId);
    const timestamp = nowIso();
    const row = {
      id: randomId(),
      owner_id: ownerId,
      kind,
      title,
      summary: summarize(blocks),
      chapter_id: chapterId,
      folder_id: folder ? Number(folder.id) : null,
      language: kind === 'source' ? language || 'c' : null,
      visibility: 'private',
      share_token: null,
      published_at: null,
      published_version: null,
      published_title: null,
      published_author: null,
      published_blocks: null,
      blocks,
      is_favorite: false,
      favorite_order: 0,
      chapter_order:
        chapterId === null ? 0 : await nextOrder(ownerId, 'chapter_order', chapterId),
      folder_order:
        folder === null ? 0 : await nextFolderOrder(ownerId, Number(folder.id)),
      library_order: await nextOrder(ownerId, 'library_order'),
      version: 1,
      created_at: timestamp,
      updated_at: timestamp,
      deleted_at: null,
      original_chapter_id: null,
      original_folder_id: null,
      deleted_sort_order: null,
    };
    const result = await db
      .from('documents')
      .insert(row)
      .select(DOC_COLUMNS);
    const created = first(
      result,
      new AppError('document_name_conflict', 409, '已有同名文档，请换一个标题'),
    );
    if (!created) fail('database_unavailable', 503, '文档保存失败，请稍后重试');
    return created;
  }

  async function recycleDocumentRow(ownerId, doc) {
    const docs = await allDocuments(ownerId);
    const deletedOrders = docs
      .filter((item) => item.deleted_at !== null)
      .map((item) => Number(item.deleted_sort_order || 0));
    dbFailure(
      await db
        .from('documents')
        .update({
          title: `__deleted__${doc.id}-${randomToken().slice(0, 8)}`,
          deleted_title: doc.title,
          chapter_id: null,
          original_chapter_id: doc.chapter_id,
          folder_id: null,
          folder_order: 0,
          original_folder_id: doc.folder_id,
          deleted_at: nowIso(),
          deleted_sort_order: deletedOrders.length
            ? Math.max(...deletedOrders) + 1
            : 0,
          is_favorite: false,
          favorite_order: 0,
          visibility: 'private',
          share_token: null,
          published_at: null,
          published_version: null,
          published_title: null,
          published_author: null,
          published_blocks: null,
          updated_at: nowIso(),
          version: Number(doc.version) + 1,
        })
        .eq('id', doc.id)
        .eq('owner_id', ownerId)
        .select('id'),
    );
  }

  function importTitle(fileName, provided) {
    if (typeof provided === 'string' && provided.trim()) {
      return cleanText(provided, 120, '标题');
    }
    return cleanText(
      String(fileName || '导入文档').replace(/\.[^.]+$/, '') || '导入文档',
      120,
      '标题',
    );
  }

  async function importDocument(
    ownerId,
    file,
    providedTitle,
    chapterId,
    folderId = null,
    profile = null,
  ) {
    const fileName = safeOriginalName(file?.name, 'import.md');
    const extension = (fileName.split('.').pop() || '').toLowerCase();
    if (!['md', 'c', 'h'].includes(extension)) {
      fail('unsupported_media_type', 422, '只允许导入 .md、.c 或 .h 文件');
    }
    if (!Number.isSafeInteger(file.size) || file.size < 1) {
      fail('invalid_input', 422, '导入文件不能为空');
    }
    if (file.size > MAX_IMPORT_BYTES) {
      fail('payload_too_large', 413, '导入文件不能超过 5 MB');
    }
    let text;
    try {
      text = new TextDecoder('utf-8', { fatal: true }).decode(
        new Uint8Array(await file.arrayBuffer()),
      );
    } catch {
      fail('invalid_input', 422, '导入文件必须是 UTF-8 文本');
    }
    const title = importTitle(fileName, providedTitle);
    const kind = extension === 'md' ? 'note' : 'source';
    const language = extension === 'h' ? 'h' : 'c';
    const blocks =
      kind === 'source'
        ? [
            {
              id: 1,
              block_type: 'code',
              content: { text, language },
              asset_id: null,
              sort_order: 0,
            },
          ]
        : parseMarkdownBlocks(text);
    if (profile) {
      await assertNewBlocksFit(ownerId, profile, blocks);
    }
    return createDocumentRow(
      ownerId,
      kind,
      title,
      chapterId,
      language,
      blocks,
      folderId,
    );
  }

  async function validateBlocks(ownerId, kind, previousBlocks, incoming) {
    if (!Array.isArray(incoming) || incoming.length > 300) {
      fail('invalid_input', 400, '模块列表无效或过多');
    }
    const previousIds = new Set(
      (Array.isArray(previousBlocks) ? previousBlocks : []).map((block) =>
        Number(block.id),
      ),
    );
    const used = new Set();
    let nextId =
      Math.max(
        0,
        ...Array.from(previousIds).filter((value) => Number.isSafeInteger(value)),
      ) + 1;
    const normalized = [];
    for (let index = 0; index < incoming.length; index += 1) {
      const block = incoming[index];
      if (!block || typeof block !== 'object') {
        fail('invalid_input', 400, '模块格式无效');
      }
      if (!BLOCK_TYPES.has(block.block_type)) {
        fail('invalid_input', 400, '模块类型无效');
      }
      const allowed =
        kind === 'source'
          ? new Set(['code', 'remark', 'result', 'image'])
          : new Set(['rich_text', 'code', 'image', 'formula']);
      if (!allowed.has(block.block_type)) {
        fail('invalid_input', 400, '模块类型与文档类型不匹配');
      }
      let id;
      if (block.id !== undefined && block.id !== null) {
        id = Number(block.id);
        if (
          !Number.isSafeInteger(id) ||
          id < 1 ||
          !previousIds.has(id) ||
          used.has(id)
        ) {
          fail('invalid_block_id', 409, '模块 ID 不属于当前文档，请刷新后重试');
        }
      } else {
        id = nextId++;
        while (used.has(id)) id = nextId++;
      }
      used.add(id);
      const content =
        block.content && typeof block.content === 'object' && !Array.isArray(block.content)
          ? block.content
          : null;
      if (!content) fail('invalid_input', 400, '模块内容无效');
      let assetId = block.asset_id;
      if (assetId !== null && assetId !== undefined) {
        assetId = safeInteger(Number(assetId), '图片');
        const asset = first(
          await db
            .from('assets')
            .select('id')
            .eq('id', assetId)
            .eq('owner_id', ownerId)
            .limit(1),
        );
        if (!asset) fail('not_found', 404, '图片不存在');
      } else {
        assetId = null;
      }
      if (block.block_type === 'image' && assetId === null) {
        fail('invalid_input', 400, '图片模块缺少图片');
      }
      if (block.block_type === 'code') {
        if (typeof content.text !== 'string' || content.text.length > 800000) {
          fail('invalid_input', 400, '代码内容无效');
        }
        if (!['c', 'h', 'text'].includes(content.language)) {
          fail('invalid_input', 400, '代码语言无效');
        }
      }
      if (block.block_type === 'result' && typeof content.text !== 'string') {
        fail('invalid_input', 400, '运行结果内容无效');
      }
      if (block.block_type === 'formula' || block.block_type === 'remark') {
        if (
          typeof content.markdown !== 'string' &&
          typeof content.latex !== 'string'
        ) {
          fail('invalid_input', 400, '模块内容无效');
        }
      }
      if (block.block_type === 'rich_text') {
        if (content.module === 'table') {
          if (!Array.isArray(content.headers) || !Array.isArray(content.rows)) {
            fail('invalid_input', 400, '表格内容无效');
          }
        } else if (!TEXT_MODULES.has(content.module)) {
          fail('invalid_input', 400, '文本模块类型无效');
        }
      }
      normalized.push({
        id,
        block_type: block.block_type,
        content,
        asset_id: assetId,
        sort_order: index,
      });
    }
    return normalized;
  }

  async function saveDocument(
    ownerId,
    documentId,
    body,
    expectedVersion,
    profile = null,
  ) {
    const doc = await ownedDocument(ownerId, documentId);
    let title = doc.title;
    if (Object.prototype.hasOwnProperty.call(body, 'title')) {
      title = cleanText(body.title, 120, '标题');
    }
    let chapterId = doc.chapter_id === null ? null : Number(doc.chapter_id);
    let chapterChanged = false;
    if (Object.prototype.hasOwnProperty.call(body, 'chapter_id')) {
      chapterId = body.chapter_id === null ? null : safeInteger(Number(body.chapter_id), '章节');
      if (chapterId !== null) await requireChapter(ownerId, chapterId);
      chapterChanged = chapterId !== (doc.chapter_id === null ? null : Number(doc.chapter_id));
    }
    const blocks = await validateBlocks(
      ownerId,
      doc.kind,
      doc.blocks,
      body.blocks,
    );
    if (profile) {
      await assertSavedBlocksFit(ownerId, profile, doc, blocks);
    }
    const update = {
      title,
      chapter_id: chapterId,
      blocks,
      summary: summarize(blocks),
      updated_at: nowIso(),
      version: expectedVersion + 1,
    };
    if (chapterChanged) {
      update.chapter_order =
        chapterId === null ? 0 : await nextOrder(ownerId, 'chapter_order', chapterId);
    }
    const result = await db
      .from('documents')
      .update(update)
      .eq('id', documentId)
      .eq('owner_id', ownerId)
      .eq('version', expectedVersion)
      .select(DOC_COLUMNS);
    const saved = first(
      result,
      new AppError('document_name_conflict', 409, '已有同名文档，请换一个标题'),
    );
    if (!saved) {
      const current = await ownedDocument(ownerId, documentId);
      fail('version_conflict', 409, '文档已在其他页面更新', {
        current_version: Number(current.version),
      });
    }
    return saved;
  }

  function downloadHeaders(filename, contentType) {
    const fallback = filename.replace(/[^A-Za-z0-9._-]/g, '_') || 'download';
    return {
      'content-type': contentType,
      'content-disposition': `attachment; filename="${fallback}"; filename*=UTF-8''${encodeURIComponent(filename)}`,
      'cache-control': 'private, no-store',
      pragma: 'no-cache',
      'x-content-type-options': 'nosniff',
    };
  }

  async function assetForOwner(ownerId, assetId) {
    const asset = first(
      await db
        .from('assets')
        .select('id,owner_id,object_path,original_name,mime_type,size_bytes')
        .eq('id', assetId)
        .eq('owner_id', ownerId)
        .limit(1),
    );
    if (!asset) fail('not_found', 404, '图片不存在');
    return asset;
  }

  async function streamAsset(asset, asDownload = false) {
    let file;
    try {
      file = await storage.download(asset.object_path);
    } catch (error) {
      if (error?.code === 'storage_object_not_found') {
        fail('not_found', 404, '图片文件不存在');
      }
      fail('storage_unavailable', 503, '图片暂时无法读取');
    }
    if (!file.ok || !file.body) fail('storage_unavailable', 503, '图片暂时无法读取');
    const headers = asDownload
      ? downloadHeaders(asset.original_name, asset.mime_type)
      : {
          'content-type': asset.mime_type,
          'cache-control': 'private, no-store',
          pragma: 'no-cache',
          'x-content-type-options': 'nosniff',
        };
    return new Response(file.body, { status: 200, headers });
  }

  async function uploadAsset(ownerId, request, profile = null) {
    const length = Number(request.headers.get('content-length') || '0');
    if (Number.isFinite(length) && length > 6 * 1024 * 1024) {
      fail('payload_too_large', 413, '图片不能超过 5 MB');
    }
    let form;
    try {
      form = await request.formData();
    } catch {
      fail('invalid_input', 400, '图片上传格式无效');
    }
    const file = form.get('file');
    if (!file || typeof file.arrayBuffer !== 'function') {
      fail('invalid_input', 400, '请选择图片文件');
    }
    if (!Number.isSafeInteger(file.size) || file.size < 1) {
      fail('invalid_input', 422, '图片文件为空');
    }
    if (file.size > MAX_IMAGE_BYTES) {
      fail('payload_too_large', 413, '图片不能超过 5 MB');
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    const image = detectImage(bytes);
    if (!image) {
      fail('unsupported_media_type', 422, '文件不是有效的 PNG/JPEG/WebP/GIF 图片');
    }
    if (
      (image.width && image.width > MAX_IMAGE_DIMENSION) ||
      (image.height && image.height > MAX_IMAGE_DIMENSION)
    ) {
      fail('invalid_input', 422, `图片宽高不能超过 ${MAX_IMAGE_DIMENSION}px`);
    }
    if (profile) {
      const usage = await usageFor(ownerId, profile);
      assertQuota(profile, usage.used_bytes + bytes.byteLength);
    }
    const id = randomId();
    const digest = await crypto.subtle.digest(
      'SHA-256',
      new TextEncoder().encode(ownerId),
    );
    const ownerHash = Array.from(new Uint8Array(digest))
      .slice(0, 12)
      .map((byte) => byte.toString(16).padStart(2, '0'))
      .join('');
    const objectPath = `assets/${ownerHash}/${id}.${image.ext}`;
    try {
      await storage.upload(objectPath, bytes, {
        contentType: image.mime,
        upsert: false,
      });
    } catch {
      fail('storage_unavailable', 503, '图片保存失败，请稍后重试');
    }
    const originalName = safeOriginalName(
      file.name,
      `image.${image.ext}`,
    );
    const row = {
      id,
      owner_id: ownerId,
      object_path: objectPath,
      original_name: originalName,
      mime_type: image.mime,
      size_bytes: bytes.byteLength,
      created_at: nowIso(),
    };
    const result = await db.from('assets').insert(row).select('id');
    if (result.error || !result.data?.length) {
      await storage.remove([objectPath]).catch(() => {});
      throw new AppError('storage_unavailable', 503, '图片记录保存失败，请稍后重试');
    }
    return {
      id,
      original_name: originalName,
      mime_type: image.mime,
      size_bytes: bytes.byteLength,
    };
  }

  async function purgeExpired(ownerId) {
    const docs = await allDocuments(ownerId);
    const cutoff = Date.now() - RECYCLE_DAYS * 24 * 60 * 60 * 1000;
    const expired = docs.filter(
      (doc) => doc.deleted_at && Date.parse(doc.deleted_at) < cutoff,
    );
    if (!expired.length) return;
    const candidates = new Set();
    for (const doc of expired) {
      collectAssetIds(doc.blocks, candidates);
      collectAssetIds(doc.published_blocks, candidates);
    }
    for (const doc of expired) {
      await db
        .from('documents')
        .delete()
        .eq('id', doc.id)
        .eq('owner_id', ownerId);
    }
    const remaining = await allDocuments(ownerId);
    const referenced = new Set();
    for (const doc of remaining) {
      collectAssetIds(doc.blocks, referenced);
      collectAssetIds(doc.published_blocks, referenced);
    }
    for (const assetId of candidates) {
      if (referenced.has(assetId)) continue;
      const asset = first(
        await db
          .from('assets')
          .select('id,owner_id,object_path')
          .eq('id', assetId)
          .eq('owner_id', ownerId)
          .limit(1),
      );
      if (!asset) continue;
      try {
        await storage.remove([asset.object_path]);
        await db
          .from('assets')
          .delete()
          .eq('id', assetId)
          .eq('owner_id', ownerId);
      } catch {
        // Keep the record so a later cleanup can retry.
      }
    }
  }

  async function publicDocument(token) {
    const doc = first(
      await db
        .from('documents')
        .select(DOC_COLUMNS)
        .eq('share_token', token)
        .eq('visibility', 'public')
        .limit(1),
    );
    if (!doc || doc.deleted_at !== null || !Array.isArray(doc.published_blocks)) {
      fail('not_found', 404, '内容不存在或已取消公开');
    }
    return doc;
  }

  return async function handle(ctx) {
    const request = ctx.request;
    const url = new URL(request.url);
    const pathname = url.pathname;
    const match = pathname.match(
      /^\/(?:functions\/v1\/)?(?:app|app-d[0-9a-f]{32})(\/.*)?$/,
    );
    if (!match) {
      return json(
        { error: { code: 'not_found', message: '接口不存在', details: {} } },
        404,
      );
    }
    const path = match[1] || '/';
    const method = request.method.toUpperCase();

    try {
      if (path === '/api/health' && method === 'GET') {
        return json({ ok: true });
      }
      if (path === '/api/public/site' && method === 'GET') {
        return json(
          { site_title: SITE_TITLE, registration_enabled: false },
          200,
          { 'x-robots-tag': 'noindex, nofollow' },
        );
      }
      const publicAsset = path.match(
        /^\/api\/public\/documents\/([A-Za-z0-9_-]{16,80})\/assets\/(\d+)$/,
      );
      if (publicAsset && method === 'GET') {
        const doc = await publicDocument(publicAsset[1]);
        const assetId = safeInteger(Number(publicAsset[2]), '图片');
        const ids = new Set();
        collectAssetIds(doc.published_blocks, ids);
        if (!ids.has(assetId)) fail('not_found', 404, '图片不存在');
        const asset = first(
          await db
            .from('assets')
            .select('id,owner_id,object_path,original_name,mime_type,size_bytes')
            .eq('id', assetId)
            .eq('owner_id', doc.owner_id)
            .limit(1),
        );
        if (!asset) fail('not_found', 404, '图片不存在');
        const response = await streamAsset(asset, false);
        const headers = new Headers(response.headers);
        headers.set('cache-control', 'private, no-store');
        headers.set('x-robots-tag', 'noindex, nofollow');
        return new Response(response.body, { status: 200, headers });
      }
      const publicDoc = path.match(
        /^\/api\/public\/documents\/([A-Za-z0-9_-]{16,80})$/,
      );
      if (publicDoc && method === 'GET') {
        const doc = await publicDocument(publicDoc[1]);
        const blocks = sortedBlocks(doc.published_blocks).map((block) => ({
          block_type: block.block_type,
          content: block.content,
          asset_id: block.asset_id ?? null,
          sort_order: block.sort_order,
        }));
        return json(
          {
            title: doc.published_title || doc.title,
            kind: doc.kind,
            language: doc.language || null,
            author: { display_name: doc.published_author || 'C 学习者' },
            published_at: doc.published_at,
            blocks,
          },
          200,
          { 'x-robots-tag': 'noindex, nofollow' },
        );
      }

      if (path === '/api/public/demo/start' && method === 'POST') {
        let profile = await ensureDemoSeed();
        if (!profile) {
          try {
            profile = await currentProfile({
              user_id: DEMO_OWNER_ID,
              name: '示例学习者',
              picture: '',
            });
          } catch {
            profile = null;
          }
        }
        const secure = new URL(request.url).protocol === 'https:' ? '; Secure' : '';
        return json(
          {
            demo: true,
            authenticated: true,
            user: profile ? serializeProfile(profile) : null,
            csrf_token: null,
          },
          200,
          {
            'set-cookie': `cq_demo=1; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000${secure}`,
            'x-robots-tag': 'noindex, nofollow',
          },
        );
      }
      if (path === '/api/public/demo/exit' && method === 'POST') {
        const secure = new URL(request.url).protocol === 'https:' ? '; Secure' : '';
        return json(
          { demo: false },
          200,
          {
            'set-cookie': `cq_demo=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0${secure}`,
            'x-robots-tag': 'noindex, nofollow',
          },
        );
      }

      if (path === '/api/auth/session' && method === 'GET') {
        const qoderUser = getUser(request);
        if (!qoderUser) {
          return json({ authenticated: false, user: null, csrf_token: null });
        }
        const profile = await authenticated(qoderUser);
        return json({
          authenticated: true,
          user: serializeProfile(profile),
          csrf_token: null,
        });
      }
      const user = requireUser(request);
      const profile = await authenticated(user);
      const ownerId = profile.owner_id;

      if (path === '/api/me' && method === 'GET') {
        return json(serializeProfile(profile));
      }
      if (path === '/api/me/profile' && method === 'PATCH') {
        const body = await readJson(request);
        if (typeof body.display_name !== 'string') {
          fail('invalid_input', 400, '昵称格式无效');
        }
        const displayName = cleanText(body.display_name, 40, '昵称');
        const updated = first(
          await db
            .from('profiles')
            .update({ display_name: displayName })
            .eq('owner_id', ownerId)
            .select('id,owner_id,display_name,picture,created_at,storage_quota_bytes'),
        );
        if (!updated) fail('not_found', 404, '账号不存在');
        return json(serializeProfile(updated));
      }
      if (path === '/api/ai/status' && method === 'GET') {
        return json({
          enabled: true,
          requires_login: true,
          demo_allowed: AI_ALLOW_DEMO,
        });
      }
      const aiPolishPath = path.match(/^\/api\/documents\/(\d+)\/ai-polish$/);
      if (aiPolishPath && method === 'POST') {
        if (ownerId === DEMO_OWNER_ID && !AI_ALLOW_DEMO) {
          fail('ai_login_required', 403, 'AI 润色需要登录 Qoder 账号');
        }
        const doc = await ownedDocument(
          ownerId,
          safeInteger(Number(aiPolishPath[1])),
        );
        let polished;
        try {
          polished = await runAiPolish({
            document: doc,
            parseBlocks: parseMarkdownBlocks,
          });
        } catch (error) {
          if (error instanceof AiPolishError) {
            fail(error.code, error.status, error.message);
          }
          throw error;
        }
        return await withUsageLock(ownerId, async () => {
          await assertNewBlocksFit(ownerId, profile, polished.blocks);
          let created = null;
          for (let attempt = 0; attempt < 4 && !created; attempt += 1) {
            const base = aiTitleFor(doc.title);
            const title =
              attempt === 0 ? base : `${base.slice(0, 116)} ${attempt + 1}`;
            try {
              created = await createDocumentRow(
                ownerId,
                'note',
                title,
                doc.chapter_id,
                null,
                polished.blocks,
                doc.folder_id,
              );
            } catch (error) {
              if (error?.status !== 409) throw error;
            }
          }
          if (!created) {
            fail('document_name_conflict', 409, 'AI 副本命名冲突，请稍后重试');
          }
          const summarizeDoc = (item) => ({
            id: item.id,
            title: item.title,
            summary: item.summary || '',
            block_count: Array.isArray(item.blocks) ? item.blocks.length : 0,
            version: Number(item.version || 1),
          });
          return json({
            mode: 'qoder',
            original: summarizeDoc(doc),
            polished: summarizeDoc(created),
          });
        });
      }
      const aiChoosePath = path.match(
        /^\/api\/documents\/(\d+)\/ai-polish\/choose$/,
      );
      if (aiChoosePath && method === 'POST') {
        const body = await readJson(request);
        const keepId = safeInteger(Number(body.keep_id), '保留文档');
        const discardId = safeInteger(Number(body.discard_id), '丢弃文档');
        if (keepId === discardId) {
          fail('invalid_input', 400, '保留与丢弃的文档不能相同');
        }
        const keep = await ownedDocument(ownerId, keepId);
        const discard = await ownedDocument(ownerId, discardId);
        const isAiCopy = (item) =>
          / · AI 润色(?: \d+)?$/.test(String(item.title));
        if (!isAiCopy(keep) && !isAiCopy(discard)) {
          fail('invalid_input', 400, '只能对 AI 润色副本进行选择');
        }
        await recycleDocumentRow(ownerId, discard);
        return json({ kept: { id: keep.id, title: keep.title } });
      }
      if (path === '/api/me/export' && method === 'GET') {
        const [docs, folders, assets] = await Promise.all([
          allDocuments(ownerId),
          allFolders(ownerId),
          allAssets(ownerId),
        ]);
        const files = [];
        const missingAssets = [];
        const assetManifest = [];
        for (const asset of assets) {
          let bytes = null;
          try {
            const response = await storage.download(asset.object_path);
            if (response.ok) {
              bytes = new Uint8Array(await response.arrayBuffer());
            }
          } catch {
            bytes = null;
          }
          const fileName = `assets/${asset.id}-${safeOriginalName(
            asset.original_name,
            `asset-${asset.id}`,
          )}`;
          assetManifest.push({
            id: Number(asset.id),
            original_name: asset.original_name,
            mime_type: asset.mime_type,
            size_bytes: Number(asset.size_bytes),
            file: bytes ? fileName : null,
          });
          if (bytes) {
            files.push({ name: fileName, bytes });
          } else {
            missingAssets.push(Number(asset.id));
          }
        }
        const data = {
          format: 'c-qoder-sites-export',
          version: 1,
          exported_at: nowIso(),
          folders: folders.map((folder) => ({
            id: Number(folder.id),
            chapter_id:
              folder.chapter_id === null || folder.chapter_id === undefined
                ? null
                : Number(folder.chapter_id),
            parent_id: folderParentId(folder),
            name: folder.name,
            sort_order: Number(folder.sort_order || 0),
            created_at: folder.created_at,
          })),
          documents: docs.map((doc) => ({
            id: Number(doc.id),
            kind: doc.kind,
            title: doc.deleted_at ? doc.deleted_title || doc.title : doc.title,
            summary: doc.summary || '',
            chapter_id:
              doc.chapter_id === null ? null : Number(doc.chapter_id),
            folder_id:
              doc.folder_id === null || doc.folder_id === undefined
                ? null
                : Number(doc.folder_id),
            language: doc.language || null,
            blocks: doc.blocks,
            is_favorite: Boolean(doc.is_favorite),
            deleted_at: doc.deleted_at,
            created_at: doc.created_at,
            updated_at: doc.updated_at,
          })),
          assets: assetManifest,
          missing_assets: missingAssets,
        };
        files.unshift({
          name: 'data.json',
          bytes: new TextEncoder().encode(JSON.stringify(data, null, 2)),
        });
        const zip = buildZip(files);
        return new Response(zip, {
          status: 200,
          headers: {
            ...downloadHeaders(
              `c-qoder-export-${new Date().toISOString().slice(0, 10)}.zip`,
              'application/zip',
            ),
          },
        });
      }
      if (path === '/api/me/usage' && method === 'GET') {
        return json(await usageFor(ownerId, profile));
      }
      if (path === '/api/workspace' && method === 'GET') {
        await purgeExpired(ownerId);
        const [chapters, docs, assets, folders] = await Promise.all([
          chapterRows(ownerId),
          allDocuments(ownerId),
          allAssets(ownerId),
          allFolders(ownerId),
        ]);
        const active = docs.filter((doc) => doc.deleted_at === null);
        const counts = new Map();
        for (const doc of active) {
          if (doc.chapter_id !== null) {
            const id = Number(doc.chapter_id);
            counts.set(id, (counts.get(id) || 0) + 1);
          }
        }
        const usage = await usageFor(ownerId, profile, {
          docs,
          assets,
          folders,
        });
        return json({
          user: serializeProfile(profile),
          chapters: chapters.map((chapter) => ({
            id: Number(chapter.id),
            name: chapter.name,
            sort_order: Number(chapter.sort_order),
            document_count: counts.get(Number(chapter.id)) || 0,
          })),
          folders: folders.map((folder) =>
            folderOut(folder, docs, folders),
          ),
          favorite_count: active.filter((doc) => doc.is_favorite).length,
          library_count: active.length,
          recycle_count: docs.length - active.length,
          storage: {
            asset_count: usage.asset_count,
            total_bytes: usage.image_bytes,
          },
          usage,
          recycle_retention_days: RECYCLE_DAYS,
        });
      }

      if (path === '/api/chapters' && method === 'GET') {
        const [chapters, docs] = await Promise.all([
          chapterRows(ownerId),
          allDocuments(ownerId),
        ]);
        const active = docs.filter((doc) => doc.deleted_at === null);
        return json(
          chapters.map((chapter) => ({
            id: Number(chapter.id),
            name: chapter.name,
            sort_order: Number(chapter.sort_order),
            document_count: active.filter(
              (doc) =>
                doc.chapter_id !== null &&
                Number(doc.chapter_id) === Number(chapter.id),
            ).length,
          })),
        );
      }
      if (path === '/api/chapters' && method === 'POST') {
        const body = await readJson(request);
        const name = cleanText(body.name, 40, '章节名称');
        const chapters = await chapterRows(ownerId);
        const sortOrder = chapters.length
          ? Math.max(...chapters.map((chapter) => Number(chapter.sort_order))) + 1
          : 0;
        const result = await db
          .from('chapters')
          .insert({
            id: randomId(),
            owner_id: ownerId,
            name,
            sort_order: sortOrder,
            created_at: nowIso(),
          })
          .select('id,name,sort_order');
        const chapter = first(
          result,
          new AppError('chapter_name_conflict', 409, '已有同名章节'),
        );
        if (!chapter) fail('database_unavailable', 503, '章节保存失败，请稍后重试');
        return json(
          {
            id: Number(chapter.id),
            name: chapter.name,
            sort_order: Number(chapter.sort_order),
            document_count: 0,
          },
          201,
        );
      }
      const chapterPath = path.match(/^\/api\/chapters\/(\d+)$/);
      if (chapterPath && method === 'PATCH') {
        const chapterId = safeInteger(Number(chapterPath[1]), '章节');
        const body = await readJson(request);
        const name = cleanText(body.name, 40, '章节名称');
        const result = await db
          .from('chapters')
          .update({ name })
          .eq('id', chapterId)
          .eq('owner_id', ownerId)
          .select('id,name,sort_order');
        const chapter = first(
          result,
          new AppError('chapter_name_conflict', 409, '已有同名章节'),
        );
        if (!chapter) fail('not_found', 404, '章节不存在');
        const docs = await allDocuments(ownerId);
        return json({
          id: Number(chapter.id),
          name: chapter.name,
          sort_order: Number(chapter.sort_order),
          document_count: docs.filter(
            (doc) =>
              doc.deleted_at === null &&
              doc.chapter_id !== null &&
              Number(doc.chapter_id) === chapterId,
          ).length,
        });
      }
      if (chapterPath && method === 'DELETE') {
        const chapterId = safeInteger(Number(chapterPath[1]), '章节');
        const chapter = first(
          await db
            .from('chapters')
            .select('id')
            .eq('id', chapterId)
            .eq('owner_id', ownerId)
            .limit(1),
        );
        if (!chapter) fail('not_found', 404, '章节不存在');
        const docs = await allDocuments(ownerId);
        for (const doc of docs) {
          if (doc.deleted_at === null && Number(doc.chapter_id) === chapterId) {
            await db
              .from('documents')
              .update({
                chapter_id: null,
                chapter_order: 0,
                folder_id: null,
                folder_order: 0,
              })
              .eq('id', doc.id)
              .eq('owner_id', ownerId);
          }
        }
        await db
          .from('folders')
          .update({ chapter_id: null })
          .eq('owner_id', ownerId)
          .eq('chapter_id', chapterId);
        await db
          .from('chapters')
          .delete()
          .eq('id', chapterId)
          .eq('owner_id', ownerId);
        return empty(204);
      }
      if (path === '/api/chapters/order' && method === 'PUT') {
        const body = await readJson(request);
        const ids = Array.isArray(body.chapter_ids)
          ? body.chapter_ids.map((id) => safeInteger(Number(id), '章节'))
          : null;
        if (!ids || new Set(ids).size !== ids.length) {
          fail('invalid_input', 400, '章节顺序无效');
        }
        const chapters = await chapterRows(ownerId);
        if (
          ids.length !== chapters.length ||
          chapters.some((chapter) => !ids.includes(Number(chapter.id)))
        ) {
          fail('order_conflict', 409, '章节顺序与当前账号范围不一致', {
            current_chapter_ids: chapters.map((chapter) => Number(chapter.id)),
          });
        }
        await persistOrder({
          db,
          table: 'chapters',
          ownerId,
          updates: ids.map((id, index) => ({ id, order: index })),
          previousById: new Map(
            chapters.map((chapter) => [
              Number(chapter.id),
              Number(chapter.sort_order),
            ]),
          ),
          field: 'sort_order',
          scope: 'chapters',
        });
        return empty(204);
      }

      if (path === '/api/folders' && method === 'GET') {
        const [folders, docs] = await Promise.all([
          allFolders(ownerId),
          allDocuments(ownerId),
        ]);
        return json(folders.map((folder) => folderOut(folder, docs, folders)));
      }
      if (path === '/api/folders' && method === 'POST') {
        const body = await readJson(request);
        const name = cleanText(body.name, 60, '文件夹名称');
        const parentId =
          body.parent_id === null ||
          body.parent_id === undefined ||
          Number(body.parent_id) === 0
            ? 0
            : safeInteger(Number(body.parent_id), '父文件夹');
        const parent = parentId === 0 ? null : await requireFolder(ownerId, parentId);
        const chapterId =
          body.chapter_id === null || body.chapter_id === undefined
            ? parent?.chapter_id ?? null
            : safeInteger(Number(body.chapter_id), '章节');
        if (chapterId === null) {
          fail('invalid_input', 400, '文件夹必须属于一个章节');
        }
        await requireChapter(ownerId, chapterId);
        if (parent && Number(parent.chapter_id) !== Number(chapterId)) {
          fail('invalid_request', 400, '父文件夹不属于该章节');
        }
        const storageParentId =
          parentId === 0 ? rootFolderParent(chapterId) : parentId;
        const parentIds =
          parentId === 0
            ? rootParentIds(chapterId)
            : new Set([parentId]);
        const folders = await allFolders(ownerId);
        if (
          folders.some(
            (folder) =>
              parentIds.has(Number(folder.parent_id || 0)) &&
              Number(folder.chapter_id) === Number(chapterId) &&
              folder.name === name,
          )
        ) {
          fail('folder_name_conflict', 409, '同一章节的同一目录已有同名文件夹');
        }
        const siblings = folders.filter(
          (folder) =>
            parentIds.has(Number(folder.parent_id || 0)) &&
            Number(folder.chapter_id) === Number(chapterId),
        );
        const result = await db
          .from('folders')
          .insert({
            id: randomId(),
            owner_id: ownerId,
            chapter_id: chapterId,
            parent_id: storageParentId,
            name,
            sort_order: siblings.length
              ? Math.max(...siblings.map((item) => Number(item.sort_order || 0))) + 1
              : 0,
            created_at: nowIso(),
          })
          .select(FOLDER_COLUMNS);
        const created = first(
          result,
          new AppError('folder_name_conflict', 409, '同一目录已有同名文件夹'),
        );
        if (!created) fail('database_unavailable', 503, '文件夹保存失败');
        const docs = await allDocuments(ownerId);
        const nextFolders = [...folders, created];
        return json(folderOut(created, docs, nextFolders), 201);
      }
      if (path === '/api/folders/order' && method === 'PUT') {
        const body = await readJson(request);
        const parentId =
          body.parent_id === null ||
          body.parent_id === undefined ||
          Number(body.parent_id) === 0
            ? 0
            : safeInteger(Number(body.parent_id), '父文件夹');
        const parent = parentId === 0 ? null : await requireFolder(ownerId, parentId);
        const chapterId =
          body.chapter_id === null || body.chapter_id === undefined
            ? parent?.chapter_id ?? null
            : safeInteger(Number(body.chapter_id), '章节');
        if (chapterId === null) {
          fail('invalid_input', 400, '文件夹排序必须指定章节');
        }
        const ids = Array.isArray(body.folder_ids)
          ? body.folder_ids.map((id) => safeInteger(Number(id), '文件夹'))
          : null;
        if (!ids || new Set(ids).size !== ids.length) {
          fail('invalid_input', 400, '文件夹顺序无效');
        }
        const folders = await allFolders(ownerId);
        const parentIds =
          parentId === 0
            ? rootParentIds(chapterId)
            : new Set([parentId]);
        const siblings = folders.filter(
          (folder) =>
            parentIds.has(Number(folder.parent_id || 0)) &&
            Number(folder.chapter_id) === Number(chapterId),
        );
        if (
          ids.length !== siblings.length ||
          siblings.some((folder) => !ids.includes(Number(folder.id)))
        ) {
          fail('order_conflict', 409, '文件夹顺序与当前章节不一致');
        }
        await persistOrder({
          db,
          table: 'folders',
          ownerId,
          updates: ids.map((id, index) => ({ id, order: index })),
          previousById: new Map(
            siblings.map((folder) => [
              Number(folder.id),
              Number(folder.sort_order || 0),
            ]),
          ),
          field: 'sort_order',
          scope: 'folders',
        });
        return empty(204);
      }
      const folderPathMatch = path.match(/^\/api\/folders\/(\d+)$/);
      if (folderPathMatch && (method === 'PATCH' || method === 'DELETE')) {
        const folder = await requireFolder(
          ownerId,
          safeInteger(Number(folderPathMatch[1]), '文件夹'),
        );
        if (!folder) fail('not_found', 404, '文件夹不存在');
        const folders = await allFolders(ownerId);
        if (method === 'PATCH') {
          const body = await readJson(request);
          const name = Object.prototype.hasOwnProperty.call(body, 'name')
            ? cleanText(body.name, 60, '文件夹名称')
            : folder.name;
          const parentId = Object.prototype.hasOwnProperty.call(body, 'parent_id')
            ? body.parent_id === null || Number(body.parent_id) === 0
              ? 0
              : safeInteger(Number(body.parent_id), '父文件夹')
            : folderParentId(folder);
          const currentParentId = folderParentId(folder);
          if (parentId !== currentParentId) {
            if (parentId !== 0) {
              const parent = await requireFolder(ownerId, parentId);
              if (Number(parent.chapter_id) !== Number(folder.chapter_id)) {
                fail('invalid_move', 400, '不能把文件夹移动到其他章节');
              }
            }
            const descendants = descendantFolderIds(folders, folder.id);
            if (parentId === Number(folder.id) || descendants.has(parentId)) {
              fail('invalid_move', 400, '不能把文件夹移动到自身或子文件夹');
            }
          }
          const storageParentId =
            parentId === 0
              ? rootFolderParent(folder.chapter_id)
              : parentId;
          const parentIds =
            parentId === 0
              ? rootParentIds(folder.chapter_id)
              : new Set([parentId]);
          if (
            folders.some(
              (item) =>
                Number(item.id) !== Number(folder.id) &&
                parentIds.has(Number(item.parent_id || 0)) &&
                Number(item.chapter_id) === Number(folder.chapter_id) &&
                item.name === name,
            )
          ) {
            fail('folder_name_conflict', 409, '同一章节的同一目录已有同名文件夹');
          }
          const siblings = folders.filter(
            (item) =>
              parentIds.has(Number(item.parent_id || 0)) &&
              Number(item.chapter_id) === Number(folder.chapter_id) &&
              Number(item.id) !== Number(folder.id),
          );
          const moving = storageParentId !== Number(folder.parent_id || 0);
          const result = await db
            .from('folders')
            .update({
              name,
              parent_id: storageParentId,
              ...(moving
                ? {
                    sort_order: siblings.length
                      ? Math.max(
                          ...siblings.map((item) => Number(item.sort_order || 0)),
                        ) + 1
                      : 0,
                  }
                : {}),
            })
            .eq('id', folder.id)
            .eq('owner_id', ownerId)
            .select(FOLDER_COLUMNS);
          const updated = first(
            result,
            new AppError('folder_name_conflict', 409, '同一父目录已有同名文件夹'),
          );
          if (!updated) fail('not_found', 404, '文件夹不存在');
          const docs = await allDocuments(ownerId);
          const nextFolders = folders.map((item) =>
            Number(item.id) === Number(folder.id) ? updated : item,
          );
          return json(folderOut(updated, docs, nextFolders));
        }
        const parentId = folderParentId(folder);
        const storageParentId =
          parentId === 0
            ? rootFolderParent(folder.chapter_id)
            : parentId;
        const movedDocs = await db
          .from('documents')
          .update({
            folder_id: parentId === 0 ? null : parentId,
            folder_order: 0,
          })
          .eq('owner_id', ownerId)
          .eq('folder_id', Number(folder.id))
          .select('id');
        if (movedDocs.error) {
          fail('folder_delete_failed', 503, '文件夹内容移动失败，请重试');
        }
        const movedChildren = await db
          .from('folders')
          .update({ parent_id: storageParentId })
          .eq('owner_id', ownerId)
          .eq('parent_id', Number(folder.id))
          .select('id');
        if (movedChildren.error) {
          fail('folder_delete_failed', 503, '子文件夹移动失败，请重试');
        }
        const deleted = await db
          .from('folders')
          .delete()
          .eq('id', folder.id)
          .eq('owner_id', ownerId)
          .select('id');
        if (deleted.error) {
          fail('folder_delete_failed', 503, '文件夹删除失败，请重试');
        }
        return empty(204);
      }

      if (path === '/api/search' && method === 'GET') {
        const query = String(url.searchParams.get('q') || '').trim();
        if (!query || query.length > 100) {
          fail('invalid_query', 400, '请输入 1–100 个字符的搜索内容');
        }
        const scope = url.searchParams.get('scope') || 'all';
        const offset = Math.max(0, Number(url.searchParams.get('offset') || '0') || 0);
        const limit = Math.min(
          50,
          Math.max(1, Number(url.searchParams.get('limit') || '20') || 20),
        );
        const [docs, folders, chapters] = await Promise.all([
          allDocuments(ownerId),
          allFolders(ownerId),
          chapterMap(ownerId),
        ]);
        let candidates = docs.filter((doc) => doc.deleted_at === null);
        if (scope === 'chapter') {
          const chapterId = safeInteger(
            Number(url.searchParams.get('chapter_id')),
            '章节',
          );
          candidates = candidates.filter(
            (doc) =>
              doc.chapter_id !== null &&
              Number(doc.chapter_id) === chapterId,
          );
        } else if (scope === 'folder') {
          const requestedFolderId = Number(url.searchParams.get('folder_id'));
          if (!Number.isSafeInteger(requestedFolderId) || requestedFolderId < 0) {
            fail('invalid_input', 400, '文件夹无效');
          }
          if (requestedFolderId === 0) {
            // Root scope includes the whole tree below root.
          } else {
            const folder = await requireFolder(ownerId, requestedFolderId);
            const folderIds = descendantFolderIds(folders, folder.id);
            candidates = candidates.filter(
              (doc) =>
                doc.folder_id !== null &&
                doc.folder_id !== undefined &&
                folderIds.has(Number(doc.folder_id)),
            );
          }
        }
        const lowerQuery = query.toLowerCase();
        const results = [];
        for (const doc of candidates) {
          const titleHit = doc.title.toLowerCase().includes(lowerQuery);
          const body = [
            doc.summary || '',
            ...sortedBlocks(doc.blocks).map(blockSearchText),
          ]
            .filter(Boolean)
            .join('\n');
          if (!titleHit && !body.toLowerCase().includes(lowerQuery)) {
            continue;
          }
          const folder = folderPath(folders, doc.folder_id);
          results.push({
            id: Number(doc.id),
            title: doc.title,
            kind: doc.kind,
            language: doc.language || null,
            chapter_id:
              doc.chapter_id === null ? null : Number(doc.chapter_id),
            chapter_name:
              doc.chapter_id === null
                ? null
                : chapters.get(Number(doc.chapter_id)) || null,
            folder_id:
              doc.folder_id === null || doc.folder_id === undefined
                ? null
                : Number(doc.folder_id),
            folder_path: folder.label,
            updated_at: doc.updated_at,
            title_hit: titleHit,
            snippet: searchSnippet(
              body || doc.title,
              query,
            ),
          });
        }
        results.sort((a, b) => {
          if (a.title_hit !== b.title_hit) return a.title_hit ? -1 : 1;
          const time = String(b.updated_at).localeCompare(String(a.updated_at));
          if (time !== 0) return time;
          return b.id - a.id;
        });
        return json({
          items: results.slice(offset, offset + limit),
          total: results.length,
          offset,
          limit,
          next_offset:
            offset + limit < results.length ? offset + limit : null,
          query,
          scope,
        });
      }
      if (path === '/api/documents' && method === 'GET') {
        const scope = url.searchParams.get('scope') || 'library';
        const chapterParam = url.searchParams.get('chapter_id');
        const folderParam = url.searchParams.get('folder_id');
        const [chapters, folders, allDocs] = await Promise.all([
          chapterMap(ownerId),
          allFolders(ownerId),
          allDocuments(ownerId),
        ]);
        let docs = allDocs.filter((doc) => doc.deleted_at === null);
        if (scope === 'favorites') {
          docs = docs
            .filter((doc) => doc.is_favorite)
            .sort(
              (a, b) =>
                Number(a.favorite_order || 0) - Number(b.favorite_order || 0),
            );
        } else if (scope === 'chapter') {
          const chapterId = safeInteger(Number(chapterParam), '章节');
          docs = docs
            .filter(
              (doc) =>
                doc.chapter_id !== null &&
                Number(doc.chapter_id) === chapterId,
            )
            .sort(
              (a, b) =>
                Number(a.chapter_order || 0) - Number(b.chapter_order || 0),
            );
        } else if (scope === 'folder') {
          const requestedFolderId = Number(folderParam);
          if (!Number.isSafeInteger(requestedFolderId) || requestedFolderId < 0) {
            fail('invalid_input', 400, '文件夹无效');
          }
          let rootChapterId = null;
          if (requestedFolderId === 0) {
            rootChapterId =
              chapterParam === null || chapterParam === undefined || chapterParam === ''
                ? null
                : safeInteger(Number(chapterParam), '章节');
            if (rootChapterId !== null) await requireChapter(ownerId, rootChapterId);
          } else {
            await requireFolder(ownerId, requestedFolderId);
          }
          docs = docs
            .filter((doc) =>
              requestedFolderId === 0
                ? (doc.folder_id === null || doc.folder_id === undefined) &&
                  (rootChapterId === null ||
                    (doc.chapter_id !== null &&
                      Number(doc.chapter_id) === rootChapterId))
                : doc.folder_id !== null &&
                  doc.folder_id !== undefined &&
                  Number(doc.folder_id) === requestedFolderId,
            )
            .sort(
              (a, b) =>
                Number(a.folder_order || 0) - Number(b.folder_order || 0) ||
                String(a.updated_at).localeCompare(String(b.updated_at)),
            );
        } else {
          docs = docs.sort(
            (a, b) =>
              Number(a.library_order || 0) - Number(b.library_order || 0),
          );
        }
        return json(
          docs.map((doc) => {
            const out = documentOut(doc, chapters, folders);
            delete out.blocks;
            delete out.share_token;
            delete out.share_url;
            delete out.published_at;
            delete out.published_version;
            return out;
          }),
        );
      }
      if (path === '/api/documents' && method === 'POST') {
        const body = await readJson(request);
        if (body.kind !== 'note' && body.kind !== 'source') {
          fail('invalid_input', 400, '文档类型无效');
        }
        return await withUsageLock(ownerId, async () => {
          const title = cleanText(body.title, 120, '标题');
          let chapterId =
            body.chapter_id === null || body.chapter_id === undefined
              ? null
              : safeInteger(Number(body.chapter_id), '章节');
          const folderId =
            body.folder_id === null ||
            body.folder_id === undefined ||
            Number(body.folder_id) === 0
              ? null
              : safeInteger(Number(body.folder_id), '文件夹');
          const folder = folderId === null
            ? null
            : await requireFolder(ownerId, folderId);
          if (folder) {
            const folderChapterId =
              folder.chapter_id === null || folder.chapter_id === undefined
                ? null
                : Number(folder.chapter_id);
            if (chapterId === null) {
              chapterId = folderChapterId;
            } else if (folderChapterId !== null && Number(chapterId) !== folderChapterId) {
              fail('invalid_request', 400, '文件夹不属于所选章节');
            }
          }
          if (chapterId !== null) await requireChapter(ownerId, chapterId);
          const language =
            body.kind === 'source'
              ? body.language === 'h'
                ? 'h'
                : 'c'
              : null;
          const blocks = emptyBlocks(body.kind, language);
          await assertNewBlocksFit(ownerId, profile, blocks);
          const created = await createDocumentRow(
            ownerId,
            body.kind,
            title,
            chapterId,
            language,
            blocks,
            folderId,
          );
          const [chapters, folders] = await Promise.all([
            chapterMap(ownerId),
            allFolders(ownerId),
          ]);
          return json(
            documentOut(created, chapters, folders),
            201,
          );
        });
      }
      if (path === '/api/documents/import' && method === 'POST') {
        const length = Number(request.headers.get('content-length') || '0');
        if (Number.isFinite(length) && length > 6 * 1024 * 1024) {
          fail('payload_too_large', 413, '导入文件不能超过 5 MB');
        }
        let form;
        try {
          form = await request.formData();
        } catch {
          fail('invalid_input', 400, '导入格式无效');
        }
        const file = form.get('file');
        if (!file || typeof file.arrayBuffer !== 'function') {
          fail('invalid_input', 400, '请选择导入文件');
        }
        const chapterValue = form.get('chapter_id');
        const folderValue = form.get('folder_id');
        return await withUsageLock(ownerId, async () => {
          let chapterId =
            chapterValue === null || String(chapterValue) === ''
              ? null
              : safeInteger(Number(chapterValue), '章节');
          const folderId =
            folderValue === null ||
            String(folderValue) === '' ||
            Number(folderValue) === 0
              ? null
              : safeInteger(Number(folderValue), '文件夹');
          const folder = folderId === null
            ? null
            : await requireFolder(ownerId, folderId);
          if (folder) {
            const folderChapterId =
              folder.chapter_id === null || folder.chapter_id === undefined
                ? null
                : Number(folder.chapter_id);
            if (chapterId === null) {
              chapterId = folderChapterId;
            } else if (folderChapterId !== null && Number(chapterId) !== folderChapterId) {
              fail('invalid_request', 400, '文件夹不属于所选章节');
            }
          }
          if (chapterId !== null) await requireChapter(ownerId, chapterId);
          const created = await importDocument(
            ownerId,
            file,
            form.get('title'),
            chapterId,
            folderId,
            profile,
          );
          const [chapters, folders] = await Promise.all([
            chapterMap(ownerId),
            allFolders(ownerId),
          ]);
          return json(
            documentOut(created, chapters, folders),
            201,
          );
        });
      }
      const docPath = path.match(/^\/api\/documents\/(\d+)$/);
      if (docPath && method === 'GET') {
        const doc = await ownedDocument(ownerId, safeInteger(Number(docPath[1])));
        const [chapters, folders] = await Promise.all([
          chapterMap(ownerId),
          allFolders(ownerId),
        ]);
        return json(documentOut(doc, chapters, folders));
      }
      if (docPath && method === 'PATCH') {
        const doc = await ownedDocument(ownerId, safeInteger(Number(docPath[1])));
        const version = Number(request.headers.get('if-match') || '0');
        if (!Number.isSafeInteger(version) || version < 1) {
          fail('version_required', 428, '请刷新文档版本后重试');
        }
        const body = await readJson(request);
        const docId = Number(doc.id);
        let title = doc.title;
        if (Object.prototype.hasOwnProperty.call(body, 'title')) {
          title = cleanText(body.title, 120, '标题');
        }
        let chapterId = doc.chapter_id === null ? null : Number(doc.chapter_id);
        let chapterChanged = false;
        if (Object.prototype.hasOwnProperty.call(body, 'chapter_id')) {
          chapterId =
            body.chapter_id === null
              ? null
              : safeInteger(Number(body.chapter_id), '章节');
          if (chapterId !== null) await requireChapter(ownerId, chapterId);
          chapterChanged =
            chapterId !== (doc.chapter_id === null ? null : Number(doc.chapter_id));
        }
        let folderId =
          doc.folder_id === null || doc.folder_id === undefined
            ? null
            : Number(doc.folder_id);
        let folderChanged = false;
        let folder = null;
        if (folderId !== null) {
          folder = await requireFolder(ownerId, folderId);
        }
        if (Object.prototype.hasOwnProperty.call(body, 'folder_id')) {
          folderId =
            body.folder_id === null || Number(body.folder_id) === 0
              ? null
              : safeInteger(Number(body.folder_id), '文件夹');
          folder = folderId === null ? null : await requireFolder(ownerId, folderId);
          folderChanged =
            folderId !==
            (doc.folder_id === null || doc.folder_id === undefined
              ? null
              : Number(doc.folder_id));
        }
        if (folder) {
          const folderChapterId =
            folder.chapter_id === null || folder.chapter_id === undefined
              ? null
              : Number(folder.chapter_id);
          if (folderChapterId === null) {
            fail('invalid_request', 400, '文件夹尚未归属章节');
          }
          if (chapterId === null) {
            chapterId = folderChapterId;
            chapterChanged =
              chapterId !== (doc.chapter_id === null ? null : Number(doc.chapter_id));
          } else if (Number(chapterId) !== folderChapterId) {
            fail('invalid_request', 400, '文件夹不属于所选章节');
          }
        }
        if (chapterChanged && folderId !== null) {
          const currentFolderChapter =
            folder?.chapter_id === null || folder?.chapter_id === undefined
              ? null
              : Number(folder.chapter_id);
          if (currentFolderChapter !== chapterId) {
            folderId = null;
            folderChanged = true;
          }
        }
        const update = {
          title,
          chapter_id: chapterId,
          folder_id: folderId,
          updated_at: nowIso(),
          version: version + 1,
        };
        if (chapterChanged) {
          update.chapter_order =
            chapterId === null
              ? 0
              : await nextOrder(ownerId, 'chapter_order', chapterId);
        }
        if (folderChanged) {
          update.folder_order =
            folderId === null ? 0 : await nextFolderOrder(ownerId, folderId);
        }
        const result = await db
          .from('documents')
          .update(update)
          .eq('id', docId)
          .eq('owner_id', ownerId)
          .eq('version', version)
          .select(DOC_COLUMNS);
        const updated = first(
          result,
          new AppError('document_name_conflict', 409, '已有同名文档，请换一个标题'),
        );
        if (!updated) {
          const current = await ownedDocument(ownerId, docId);
          fail('version_conflict', 409, '文档已在其他页面更新', {
            current_version: Number(current.version),
          });
        }
        const [chapters, folders] = await Promise.all([
          chapterMap(ownerId),
          allFolders(ownerId),
        ]);
        return json(documentOut(updated, chapters, folders));
      }
      if (docPath && method === 'DELETE') {
        const doc = await ownedDocument(ownerId, safeInteger(Number(docPath[1])));
        await recycleDocumentRow(ownerId, doc);
        return empty(204);
      }
      const blockPath = path.match(/^\/api\/documents\/(\d+)\/blocks$/);
      if (blockPath && method === 'PUT') {
        const version = Number(request.headers.get('if-match') || '0');
        if (!Number.isSafeInteger(version) || version < 1) {
          fail('version_required', 428, '请刷新文档版本后重试');
        }
        const body = await readJson(request, 2 * 1024 * 1024);
        const docId = safeInteger(Number(blockPath[1]));
        if (!Array.isArray(body.blocks)) {
          fail('invalid_input', 400, '模块列表无效');
        }
        return await withUsageLock(ownerId, async () => {
          const current = await ownedDocument(ownerId, docId);
          if (Number(current.version) !== version) {
            fail('version_conflict', 409, '文档已在其他页面更新', {
              current_version: Number(current.version),
            });
          }
          const saved = await saveDocument(
            ownerId,
            docId,
            body,
            version,
            profile,
          );
          const [savedChapters, savedFolders] = await Promise.all([
            chapterMap(ownerId),
            allFolders(ownerId),
          ]);
          return json(documentOut(saved, savedChapters, savedFolders));
        });
      }
      const downloadPath = path.match(/^\/api\/documents\/(\d+)\/download$/);
      if (downloadPath && method === 'GET') {
        const doc = await ownedDocument(ownerId, safeInteger(Number(downloadPath[1])));
        if (doc.kind !== 'source') fail('invalid_request', 400, '仅源码文档支持下载');
        const parts = sortedBlocks(doc.blocks)
          .filter((block) => block.block_type === 'code')
          .map((block) => (typeof block.content?.text === 'string' ? block.content.text : ''));
        let source = '';
        for (const part of parts) {
          if (!part) continue;
          if (source && !/[\r\n]$/.test(source)) source += '\n';
          source += part;
        }
        const filename = `${doc.title}.${sourceExtension(doc.language)}`;
        return new Response(source, {
          status: 200,
          headers: downloadHeaders(filename, 'text/plain; charset=utf-8'),
        });
      }
      const favoritePath = path.match(/^\/api\/documents\/(\d+)\/favorite$/);
      if (favoritePath && (method === 'PUT' || method === 'DELETE')) {
        const docId = safeInteger(Number(favoritePath[1]));
        const doc = await ownedDocument(ownerId, docId);
        let update;
        if (method === 'PUT') {
          const docs = await allDocuments(ownerId);
          const orders = docs
            .filter((item) => item.is_favorite && item.deleted_at === null)
            .map((item) => Number(item.favorite_order || 0));
          update = {
            is_favorite: true,
            favorite_order: orders.length ? Math.max(...orders) + 1 : 0,
          };
        } else {
          update = { is_favorite: false, favorite_order: 0 };
        }
        await db
          .from('documents')
          .update(update)
          .eq('id', docId)
          .eq('owner_id', ownerId);
        return empty(204);
      }
      const visibilityPath = path.match(
        /^\/api\/documents\/(\d+)\/visibility$/,
      );
      if (visibilityPath && method === 'PUT') {
        const body = await readJson(request);
        if (body.visibility !== 'public' && body.visibility !== 'private') {
          fail('invalid_input', 400, '公开状态无效');
        }
        return await withUsageLock(ownerId, async () => {
          const doc = await ownedDocument(
            ownerId,
            safeInteger(Number(visibilityPath[1])),
          );
          if (body.visibility === 'public') {
            const publishedBlocks = sortedBlocks(doc.blocks);
            const usage = await usageFor(ownerId, profile);
            const previousPublished =
              doc.visibility === 'public'
                ? jsonByteLength(doc.published_blocks)
                : 0;
            assertQuota(
              profile,
              usage.used_bytes -
                previousPublished +
                jsonByteLength(publishedBlocks),
            );
            const token = doc.share_token || randomToken();
            const updated = first(
              await db
                .from('documents')
                .update({
                  visibility: 'public',
                  share_token: token,
                  published_at: nowIso(),
                  published_version: Number(doc.version),
                  published_title: doc.title,
                  published_author: profile.display_name,
                  published_blocks: publishedBlocks,
                  updated_at: nowIso(),
                })
                .eq('id', doc.id)
                .eq('owner_id', ownerId)
                .select(DOC_COLUMNS),
            );
            if (!updated) {
              fail('database_unavailable', 503, '公开设置保存失败，请稍后重试');
            }
            return json(publicationOut(updated));
          }
          const updated = first(
            await db
              .from('documents')
              .update({
                visibility: 'private',
                share_token: null,
                published_at: null,
                published_version: null,
                published_title: null,
                published_author: null,
                published_blocks: null,
                updated_at: nowIso(),
              })
              .eq('id', doc.id)
              .eq('owner_id', ownerId)
              .select(DOC_COLUMNS),
          );
          if (!updated) {
            fail('database_unavailable', 503, '公开设置保存失败，请稍后重试');
          }
          return json(publicationOut(updated));
        });
      }

      if (path === '/api/recycle' && method === 'GET') {
        await purgeExpired(ownerId);
        const [chapters, folders] = await Promise.all([
          chapterMap(ownerId),
          allFolders(ownerId),
        ]);
        const docs = (await allDocuments(ownerId))
          .filter((doc) => doc.deleted_at !== null)
          .sort(
            (a, b) =>
              Number(b.deleted_sort_order || 0) - Number(a.deleted_sort_order || 0),
          );
        return json(
          docs.map((doc) => {
            const deletedAt = Date.parse(doc.deleted_at);
            const expiresAt = deletedAt + RECYCLE_DAYS * 24 * 60 * 60 * 1000;
            return {
              id: Number(doc.id),
              document_id: Number(doc.id),
              title: doc.deleted_title || doc.title,
              kind: doc.kind,
              original_chapter_id:
                doc.original_chapter_id === null
                  ? null
                  : Number(doc.original_chapter_id),
              original_chapter_name:
                doc.original_chapter_id === null
                  ? null
                  : chapters.get(Number(doc.original_chapter_id)) || null,
              original_folder_id:
                doc.original_folder_id === null ||
                doc.original_folder_id === undefined
                  ? null
                  : Number(doc.original_folder_id),
              original_folder_name:
                doc.original_folder_id === null ||
                doc.original_folder_id === undefined
                  ? null
                  : folderPath(folders, doc.original_folder_id).names.at(-1) ||
                    null,
              original_folder_path:
                doc.original_folder_id === null ||
                doc.original_folder_id === undefined
                  ? null
                  : folderPath(folders, doc.original_folder_id).label,
              deleted_at: doc.deleted_at,
              expires_at: new Date(expiresAt).toISOString(),
              days_remaining: Math.max(
                0,
                Math.ceil((expiresAt - Date.now()) / (24 * 60 * 60 * 1000)),
              ),
            };
          }),
        );
      }
      const restorePath = path.match(/^\/api\/recycle\/(\d+)\/restore$/);
      if (restorePath && method === 'POST') {
        const docId = safeInteger(Number(restorePath[1]));
        const doc = await ownedDocument(ownerId, docId, { deleted: true });
        const body = await readJson(request);
        const title = body.title
          ? cleanText(body.title, 120, '标题')
          : doc.deleted_title || doc.title;
        const [chapters, folders] = await Promise.all([
          chapterRows(ownerId),
          allFolders(ownerId),
        ]);
        let chapterId =
          doc.original_chapter_id !== null &&
          chapters.some(
            (chapter) => Number(chapter.id) === Number(doc.original_chapter_id),
          )
            ? Number(doc.original_chapter_id)
            : null;
        const originalFolder =
          doc.original_folder_id !== null &&
          doc.original_folder_id !== undefined
            ? folders.find(
                (folder) => Number(folder.id) === Number(doc.original_folder_id),
              ) ?? null
            : null;
        if (originalFolder && chapterId === null) {
          chapterId =
            originalFolder.chapter_id === null ||
            originalFolder.chapter_id === undefined
              ? null
              : Number(originalFolder.chapter_id);
        }
        const folderId =
          originalFolder &&
          originalFolder.chapter_id !== null &&
          originalFolder.chapter_id !== undefined &&
          chapterId !== null &&
          Number(originalFolder.chapter_id) === Number(chapterId)
            ? Number(originalFolder.id)
            : null;
        const update = {
          title,
          deleted_title: null,
          chapter_id: chapterId,
          chapter_order:
            chapterId === null
              ? 0
              : await nextOrder(ownerId, 'chapter_order', chapterId),
          folder_id: folderId,
          folder_order:
            folderId === null ? 0 : await nextFolderOrder(ownerId, folderId),
          original_chapter_id: null,
          original_folder_id: null,
          deleted_at: null,
          deleted_sort_order: null,
          updated_at: nowIso(),
          version: Number(doc.version) + 1,
        };
        const result = await db
          .from('documents')
          .update(update)
          .eq('id', docId)
          .eq('owner_id', ownerId)
          .select(DOC_COLUMNS);
        const restored = first(
          result,
          new AppError('document_name_conflict', 409, '已有同名文档，请先改名再恢复'),
        );
        if (!restored) fail('not_found', 404, '回收站文档不存在');
        const [restoredChapters, restoredFolders] = await Promise.all([
          chapterMap(ownerId),
          allFolders(ownerId),
        ]);
        const payload = documentOut(
          restored,
          restoredChapters,
          restoredFolders,
        );
        if (doc.original_folder_id && folderId === null) {
          payload.restore_notice = '原文件夹已不存在，文档已恢复到根目录';
        }
        return json(payload);
      }

      if (path === '/api/assets' && method === 'POST') {
        return await withUsageLock(
          ownerId,
          async () => json(await uploadAsset(ownerId, request, profile), 201),
        );
      }
      const assetPath = path.match(/^\/api\/assets\/(\d+)\/(file|download)$/);
      if (assetPath && method === 'GET') {
        const asset = await assetForOwner(
          ownerId,
          safeInteger(Number(assetPath[1]), '图片'),
        );
        return streamAsset(asset, assetPath[2] === 'download');
      }

      const orderPath = path.match(
        /^\/api\/orders\/(library|favorites|chapters\/(\d+)|folders\/(\d+))$/,
      );
      if (orderPath && method === 'PUT') {
        const body = await readJson(request);
        const ids = Array.isArray(body.document_ids)
          ? body.document_ids.map((id) => safeInteger(Number(id), '文档'))
          : null;
        if (!ids || new Set(ids).size !== ids.length) {
          fail('invalid_input', 400, '文档顺序无效');
        }
        const docs = (await allDocuments(ownerId)).filter(
          (doc) => doc.deleted_at === null,
        );
        let scope;
        let field;
        let expected;
        if (orderPath[1] === 'favorites') {
          scope = 'favorites';
          field = 'favorite_order';
          expected = docs.filter((doc) => doc.is_favorite);
        } else if (orderPath[1] === 'library') {
          scope = 'library';
          field = 'library_order';
          expected = docs;
        } else if (orderPath[2]) {
          const chapterId = safeInteger(Number(orderPath[2]), '章节');
          scope = 'chapter';
          field = 'chapter_order';
          expected = docs.filter(
            (doc) =>
              doc.chapter_id !== null &&
              Number(doc.chapter_id) === chapterId,
          );
        } else {
          const folderId = Number(orderPath[3]);
          if (!Number.isSafeInteger(folderId) || folderId < 0) {
            fail('invalid_input', 400, '文件夹无效');
          }
          let chapterId = null;
          if (folderId !== 0) {
            const folder = await requireFolder(ownerId, folderId);
            chapterId =
              folder.chapter_id === null || folder.chapter_id === undefined
                ? null
                : Number(folder.chapter_id);
          } else if (Object.prototype.hasOwnProperty.call(body, 'chapter_id')) {
            chapterId = safeInteger(Number(body.chapter_id), '章节');
            await requireChapter(ownerId, chapterId);
          }
          scope = 'folder';
          field = 'folder_order';
          expected = docs.filter((doc) =>
            folderId === 0
              ? (doc.folder_id === null || doc.folder_id === undefined) &&
                (chapterId === null ||
                  (doc.chapter_id !== null &&
                    Number(doc.chapter_id) === chapterId))
              : doc.folder_id !== null &&
                doc.folder_id !== undefined &&
                Number(doc.folder_id) === folderId,
          );
        }
        if (
          ids.length !== expected.length ||
          expected.some((doc) => !ids.includes(Number(doc.id)))
        ) {
          fail(
            'order_conflict',
            409,
            scope === 'favorites'
              ? '收藏顺序与当前范围不一致'
              : scope === 'chapter'
                ? '章节文档顺序与当前范围不一致'
                : scope === 'folder'
                  ? '文件夹文档顺序与当前范围不一致'
                  : '文档顺序与当前范围不一致',
          );
        }
        await persistOrder({
          db,
          table: 'documents',
          ownerId,
          updates: ids.map((id, index) => ({ id, order: index })),
          previousById: new Map(
            expected.map((doc) => [
              Number(doc.id),
              Number(doc[field] || 0),
            ]),
          ),
          field,
          scope,
        });
        return empty(204);
      }

      return json(
        { error: { code: 'not_found', message: '接口不存在', details: {} } },
        404,
      );
    } catch (error) {
      if (error instanceof AppError) return contractError(error);
      if (error instanceof UserContextError) return contractError(error);
      onError?.(error);
      console.error(
        'cqoder_unhandled',
        String(error?.name || 'Error'),
        String(error?.message || '').slice(0, 160),
      );
      return json(
        {
          error: {
            code: 'service_unavailable',
            message: '服务暂时不可用，请稍后重试',
            details: {},
          },
        },
        503,
      );
    }
  };
}
