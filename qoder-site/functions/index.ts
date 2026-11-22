import {
  createDatabaseClient,
  createSiteContext,
} from './_qoder/backend.mjs';
import { createStorageClient } from './_qoder/storage.mjs';
import { getUser, UserContextError } from './auth.mjs';
import { application, AppError } from './routes.mjs';

const db = createDatabaseClient();
const storage = createStorageClient();
const DEMO_OWNER_ID = 'demo';

function demoUser(request) {
  const cookie = request.headers.get('cookie') || '';
  if (!/(?:^|;\s*)cq_demo=1(?:;|$)/.test(cookie)) return null;
  return {
    user_id: DEMO_OWNER_ID,
    name: '示例学习者',
    picture: '',
    site_id: '',
    host_id: '',
    session_expires_at: Math.floor(Date.now() / 1000) + 30 * 24 * 60 * 60,
  };
}

function normalizeContextUser(value) {
  if (!value || typeof value !== 'object') return null;
  const userId = value.user_id ?? value.id;
  if (typeof userId !== 'string' || !userId) return null;
  return {
    user_id: userId,
    name: typeof value.name === 'string' ? value.name : '',
    picture: typeof value.picture === 'string' ? value.picture : '',
    site_id: typeof value.site_id === 'string' ? value.site_id : '',
    host_id: typeof value.host_id === 'string' ? value.host_id : '',
    session_expires_at:
      Number(value.session_expires_at) ||
      Math.floor(Date.now() / 1000) + 60,
  };
}

function resolveUser(request, context) {
  let headerUser = null;
  try {
    headerUser = getUser(request);
  } catch (error) {
    if (error instanceof UserContextError) throw error;
    throw error;
  }
  return headerUser || normalizeContextUser(context?.user);
}

function errorResponse(error, requestId) {
  if (error instanceof AppError || error instanceof UserContextError) {
    return Response.json(
      {
        error: {
          code: error.code,
          message: error.message,
          details: error.details || {},
        },
      },
      {
        status: error.status || 400,
        headers: {
          'cache-control': 'private, no-store',
          pragma: 'no-cache',
          'x-content-type-options': 'nosniff',
        },
      },
    );
  }
  return Response.json(
    {
      error: {
        code: 'service_unavailable',
        message: '服务暂时不可用，请稍后重试',
        details: {},
      },
    },
    {
      status: 503,
      headers: {
        'cache-control': 'private, no-store',
        pragma: 'no-cache',
        'x-content-type-options': 'nosniff',
      },
    },
  );
}

Deno.serve(async (request) => {
  let context;
  try {
    context = createSiteContext(request);
    const user = resolveUser(request, context) || demoUser(request);
    if (new URL(request.url).pathname.endsWith('/api/auth/session')) {
      console.log(
        JSON.stringify({
          event: 'auth_context',
          header: Boolean(request.headers.get('x-qoder-user-context')),
          context_user: Boolean(context?.user),
          resolved: Boolean(user),
        }),
      );
    }
    const handle = application({
      db,
      storage,
      getUser: () => user,
      requireUser: () => {
        if (!user) throw new UserContextError('login_required', 401);
        return user;
      },
    });
    return await handle(context);
  } catch (error) {
    return errorResponse(error, context?.requestId);
  }
});
