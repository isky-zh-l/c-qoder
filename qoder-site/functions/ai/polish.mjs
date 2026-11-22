// AI polish module. Depends only on the injected Markdown parser and provider.
import { AI_MARKDOWN_GUIDE } from './guide.mjs';
import { AiProviderError, polishWithQoder } from './provider.mjs';

export class AiPolishError extends Error {
  constructor(code, status, message) {
    super(message);
    this.name = 'AiPolishError';
    this.code = code;
    this.status = status;
  }
}

const MAX_NOTE_CHARS = 60000;
const MAX_REPLY_CHARS = 200000;

function sortedBlocks(blocks) {
  return (Array.isArray(blocks) ? [...blocks] : []).sort(
    (a, b) =>
      Number(a.sort_order || 0) - Number(b.sort_order || 0) ||
      Number(a.id || 0) - Number(b.id || 0),
  );
}

function escapeCell(value) {
  return String(value ?? '')
    .replace(/\r?\n/g, ' ')
    .replace(/\|/g, '\\|');
}

function tableToMarkdown(content) {
  const headers = Array.isArray(content.headers) ? content.headers : [];
  const rows = Array.isArray(content.rows) ? content.rows : [];
  if (!headers.length) return '';
  const header = `| ${headers.map(escapeCell).join(' | ')} |`;
  const separator = `| ${headers.map(() => '---').join(' | ')} |`;
  const body = rows.map(
    (row) => `| ${headers.map((_, index) => escapeCell(row?.[index])).join(' | ')} |`,
  );
  return [header, separator, ...body].join('\n');
}

export function blocksToMarkdown(blocks) {
  const parts = [];
  for (const block of sortedBlocks(blocks)) {
    const content = block.content || {};
    if (block.block_type === 'rich_text') {
      const moduleName = typeof content.module === 'string' ? content.module : '';
      if (moduleName === 'table') {
        const table = tableToMarkdown(content);
        if (table) parts.push(table);
      } else if (moduleName === 'divider') {
        parts.push('---');
      } else if (typeof content.markdown === 'string' && content.markdown.trim()) {
        parts.push(content.markdown.trim());
      }
      continue;
    }
    if (block.block_type === 'code') {
      const language = content.language === 'h' ? 'h' : content.language === 'c' ? 'c' : 'text';
      const text = typeof content.text === 'string' ? content.text : '';
      parts.push('```' + language + '\n' + text + '\n```');
      continue;
    }
    if (block.block_type === 'formula') {
      const latex = typeof content.latex === 'string' ? content.latex.trim() : '';
      if (latex) parts.push('$$\n' + latex + '\n$$');
      continue;
    }
    if (block.block_type === 'remark') {
      if (typeof content.markdown === 'string' && content.markdown.trim()) {
        parts.push(content.markdown.trim());
      }
      continue;
    }
    if (block.block_type === 'image') {
      if (block.asset_id !== null && block.asset_id !== undefined) {
        parts.push(`⟦IMG:${Number(block.asset_id)}⟧`);
      }
    }
  }
  return parts.join('\n\n').trim();
}

function stripOuterFence(text) {
  const trimmed = text.trim();
  const match = trimmed.match(/^```[A-Za-z0-9_-]*\s*\n([\s\S]*?)\n```$/);
  return match ? match[1].trim() : trimmed;
}

function buildPrompt(markdown) {
  return [
    '请按下面的语法白名单，润色这篇 C 语言学习笔记。',
    '只调整结构与排版；代码、公式和链接原样保留；不要解释。',
    '形如 ⟦IMG:数字⟧ 的行是受保护图片占位符，必须原样保留、单独成行，不要翻译、合并、删除或改写。',
    '',
    '<style-guide>',
    AI_MARKDOWN_GUIDE,
    '</style-guide>',
    '',
    '<note>',
    markdown,
    '</note>',
    '',
    '只输出润色后的 Markdown 全文，不要代码围栏包裹全文。',
  ].join('\n');
}

function isFakeMode() {
  const deno = globalThis.Deno?.env?.get?.('AI_POLISH_FAKE');
  const node = globalThis.process?.env?.AI_POLISH_FAKE;
  return deno === '1' || node === '1';
}

async function polishWithFake(markdown) {
  await new Promise((resolve) => setTimeout(resolve, 600));
  return [
    markdown,
    '',
    '## AI 排版检查',
    '',
    '- ==本地模拟润色== 已运行，用于界面验收',
    `- 原文共 ${markdown.split('\n').length} 行`,
  ].join('\n');
}

export async function runAiPolish({ document, parseBlocks }) {
  if (!document || document.kind !== 'note') {
    throw new AiPolishError('ai_unsupported_kind', 422, '只有笔记支持 AI 润色');
  }
  const markdown = blocksToMarkdown(document.blocks);
  if (!markdown || markdown.length < 20) {
    throw new AiPolishError('ai_note_too_short', 422, '笔记内容太少，暂不需要 AI 润色');
  }
  if (markdown.length > MAX_NOTE_CHARS) {
    throw new AiPolishError(
      'ai_note_too_large',
      413,
      '笔记超过 AI 润色的大小上限（约 6 万字符）',
    );
  }
  const prompt = buildPrompt(markdown);
  let raw;
  try {
    raw = isFakeMode()
      ? await polishWithFake(markdown)
      : await polishWithQoder(prompt);
  } catch (error) {
    if (error instanceof AiProviderError) {
      throw new AiPolishError(error.code, error.status, error.message);
    }
    throw new AiPolishError('ai_service_unavailable', 503, 'AI 服务暂时不可用');
  }
  const cleaned = stripOuterFence(String(raw || '').replace(/^\uFEFF/, ''));
  if (!cleaned) {
    throw new AiPolishError('ai_empty_reply', 502, 'AI 没有返回可用内容');
  }
  if (cleaned.length > MAX_REPLY_CHARS) {
    throw new AiPolishError('ai_reply_too_large', 502, 'AI 返回内容过大');
  }
  const parsed = parseBlocks(cleaned);
  const blocks = restoreImageBlocks(parsed, document.blocks);
  if (!blocks.length) {
    throw new AiPolishError('ai_empty_reply', 502, 'AI 没有返回可用内容');
  }
  return { markdown: cleaned, blocks };
}

export function restoreImageBlocks(blocks, originalBlocks) {
  const images = new Map();
  for (const block of sortedBlocks(originalBlocks)) {
    if (block.block_type === 'image' && block.asset_id !== null && block.asset_id !== undefined) {
      images.set(Number(block.asset_id), block);
    }
  }
  const used = new Set();
  const tokenRe = /⟦IMG:(\d+)⟧/g;
  const output = [];
  const pushImage = (id) => {
    const image = images.get(id);
    if (!image || used.has(id)) return;
    used.add(id);
    output.push({
      block_type: 'image',
      content: {
        alt: typeof image.content?.alt === 'string' ? image.content.alt : '',
        caption:
          typeof image.content?.caption === 'string' ? image.content.caption : '',
      },
      asset_id: Number(image.asset_id),
    });
  };
  for (const block of blocks) {
    const markdown =
      block.block_type === 'rich_text' && typeof block.content?.markdown === 'string'
        ? block.content.markdown
        : '';
    if (!markdown.includes('⟦IMG:')) {
      output.push(block);
      continue;
    }
    if (block.content.module === 'paragraph') {
      let last = 0;
      tokenRe.lastIndex = 0;
      let match;
      while ((match = tokenRe.exec(markdown))) {
        const before = markdown.slice(last, match.index).trim();
        if (before) {
          output.push({
            ...block,
            content: { ...block.content, markdown: before },
          });
        }
        pushImage(Number(match[1]));
        last = match.index + match[0].length;
      }
      const after = markdown.slice(last).trim();
      if (after) {
        output.push({
          ...block,
          content: { ...block.content, markdown: after },
        });
      }
      continue;
    }
    const stripped = markdown.replace(/⟦IMG:\d+⟧/g, '').trim();
    if (stripped) {
      output.push({
        ...block,
        content: { ...block.content, markdown: stripped },
      });
    }
  }
  for (const id of images.keys()) {
    if (!used.has(id)) pushImage(id);
  }
  return output.map((block, index) => ({ ...block, id: index + 1, sort_order: index }));
}

export function aiTitleFor(title) {
  const suffix = ' · AI 润色';
  const base = String(title || '未命名笔记').slice(0, 120 - suffix.length);
  return `${base}${suffix}`;
}