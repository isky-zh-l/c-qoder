// Qoder Cloud Agents provider for AI polish. Server-only.
import { CloudAgentsError, createCloudAgentsClient } from './cloud-agents.mjs';

const CLOUD_ORIGIN = 'https://api.qoder.com.cn';
const RESOURCE_METADATA = {
  app: 'c-study-notes',
  purpose: 'ai-polish',
  implementation: 'notes-site-v1',
};
const AGENT_NAME = 'C 笔记排版助手';
const ENVIRONMENT_NAME = 'C 笔记排版环境';
const SYSTEM_PROMPT = [
  '你是 C 语言学习笔记的排版助手。',
  '输入是一篇用户笔记的 Markdown。你的任务只是润色与排版：',
  '补充小标题、拆分过长段落、把并列内容整理成列表、把对照内容整理成表格、给关键词加高亮。',
  '不要新增原文没有的技术结论，不要删除原有内容，不要改写 C 代码、公式和链接。',
  '只输出处理后的 Markdown 全文，不要解释、前言、结语，也不要用代码围栏包裹全文。',
  '只能使用排版语法白名单里的写法。',
].join('\n');

export class AiProviderError extends Error {
  constructor(code, status, message) {
    super(message);
    this.name = 'AiProviderError';
    this.code = code;
    this.status = status;
  }
}

function safeLabel(error) {
  if (error instanceof CloudAgentsError) return error.code;
  return 'ai_service_unavailable';
}

async function pickModel(client) {
  const models = await client.request('/api/v1/cloud/models');
  const list = Array.isArray(models?.data) ? models.data : [];
  const usable = list
    .filter((model) => model && typeof model.id === 'string')
    .filter((model) => model.is_enabled !== false)
    .sort(
      (a, b) =>
        Number(a.price_factor ?? 99) - Number(b.price_factor ?? 99),
    );
  if (!usable.length) {
    throw new AiProviderError('ai_no_model', 503, 'AI 模型暂时不可用');
  }
  return usable[0].id;
}

async function findOne(client, kind) {
  const matches = await client.findResources(kind, RESOURCE_METADATA);
  return matches[0] ?? null;
}

async function ensureAgent(client, model) {
  const existing = await findOne(client, 'agents');
  if (existing) {
    return { id: existing.id, version: existing.version };
  }
  try {
    const created = await client.request('/api/v1/cloud/agents', {
      method: 'POST',
      idempotencyKey: 'c-study-notes-polish-agent-v1',
      body: {
        name: AGENT_NAME,
        model,
        system: SYSTEM_PROMPT,
        tools: [],
        metadata: RESOURCE_METADATA,
      },
    });
    if (!created?.id || !Number.isInteger(created.version)) {
      throw new AiProviderError('ai_response_invalid', 503, 'AI 返回异常');
    }
    return { id: created.id, version: created.version };
  } catch (error) {
    if (error instanceof AiProviderError) throw error;
    // A concurrent first use may have created the agent already.
    const raced = await findOne(client, 'agents').catch(() => null);
    if (raced) return { id: raced.id, version: raced.version };
    throw error;
  }
}

async function ensureEnvironment(client) {
  const existing = await findOne(client, 'environments');
  if (existing) return existing.id;
  try {
    const created = await client.request('/api/v1/cloud/environments', {
      method: 'POST',
      body: {
        name: ENVIRONMENT_NAME,
        config: { type: 'cloud' },
        metadata: RESOURCE_METADATA,
      },
    });
    if (!created?.id) {
      throw new AiProviderError('ai_response_invalid', 503, 'AI 返回异常');
    }
    return created.id;
  } catch (error) {
    if (error instanceof AiProviderError) throw error;
    const raced = await findOne(client, 'environments').catch(() => null);
    if (raced) return raced.id;
    throw error;
  }
}

function replyText(events) {
  const messages = (Array.isArray(events?.data) ? events.data : []).filter(
    (event) => event?.type === 'agent.message',
  );
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const content = Array.isArray(messages[index].content)
      ? messages[index].content
      : [];
    const text = content
      .filter((block) => block?.type === 'text')
      .map((block) => block.text || '')
      .join('')
      .trim();
    if (text) return text;
  }
  return '';
}

async function waitForReply(client, sessionId) {
  const deadline = Date.now() + 40000;
  let latest = '';
  while (Date.now() < deadline) {
    const [session, events] = await Promise.all([
      client.request(`/api/v1/cloud/sessions/${sessionId}`),
      client.request(
        `/api/v1/cloud/sessions/${sessionId}/events?order=asc&limit=100&types=agent.message`,
      ),
    ]);
    const text = replyText(events);
    if (text) latest = text;
    const status = typeof session?.status === 'string' ? session.status : '';
    if (latest && status === 'idle') return latest;
    if (['failed', 'error', 'cancelled'].includes(status)) {
      throw new AiProviderError('ai_polish_failed', 502, 'AI 未能完成排版');
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  if (latest) return latest;
  throw new AiProviderError(
    'ai_polish_timeout',
    504,
    'AI 正在处理，请稍后再试（本次未生成副本）',
  );
}

export async function polishWithQoder(prompt) {
  const client = createCloudAgentsClient({ origin: CLOUD_ORIGIN });
  try {
    const model = await pickModel(client);
    const agent = await ensureAgent(client, model);
    const environmentId = await ensureEnvironment(client);
    const session = await client.request('/api/v1/cloud/sessions', {
      method: 'POST',
      body: {
        agent: { type: 'agent', id: agent.id, version: agent.version },
        environment_id: environmentId,
        title: '笔记 AI 排版',
        metadata: { app: 'c-study-notes', purpose: 'ai-polish' },
      },
    });
    if (!session?.id) {
      throw new AiProviderError('ai_response_invalid', 503, 'AI 返回异常');
    }
    await client.request(`/api/v1/cloud/sessions/${session.id}/events`, {
      method: 'POST',
      body: {
        events: [
          {
            type: 'user.message',
            content: [{ type: 'text', text: prompt }],
          },
        ],
      },
    });
    return await waitForReply(client, session.id);
  } catch (error) {
    if (error instanceof AiProviderError) throw error;
    const code = safeLabel(error);
    if (code === 'ai_not_configured') {
      throw new AiProviderError('ai_not_configured', 503, 'AI 服务尚未配置');
    }
    if (code === 'ai_rate_limited') {
      throw new AiProviderError('ai_rate_limited', 429, 'AI 请求过于频繁，请稍后重试');
    }
    if (code === 'ai_access_denied') {
      throw new AiProviderError('ai_access_denied', 503, 'AI 服务暂时不可用');
    }
    throw new AiProviderError('ai_service_unavailable', 503, 'AI 服务暂时不可用');
  }
}