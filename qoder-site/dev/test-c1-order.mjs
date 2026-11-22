import assert from 'node:assert/strict';
import { AppError, persistOrder } from '../functions/routes.mjs';

function makeDb(mode) {
  const calls = [];
  let writes = 0;
  const db = {
    from(table) {
      return {
        update(patch) {
          const filters = [];
          const query = {
            eq(column, value) {
              filters.push([column, value]);
              return query;
            },
            select() {
              return query;
            },
            then(resolve, reject) {
              writes += 1;
              const id = filters[0]?.[1];
              const failWrite =
                (mode === 'fail-second' || mode === 'fail-rollback') &&
                writes === 2;
              const failRollback = mode === 'fail-rollback' && writes === 3;
              const failed = failWrite || failRollback;
              calls.push({ table, patch, id, failed });
              return Promise.resolve(
                failed
                  ? { data: null, error: { code: 'network' } }
                  : { data: [{ id }], error: null },
              ).then(resolve, reject);
            },
          };
          return query;
        },
      };
    },
  };
  return { db, calls };
}

async function run(mode) {
  const { db, calls } = makeDb(mode);
  try {
    await persistOrder({
      db,
      table: 'documents',
      ownerId: 'owner-a',
      field: 'library_order',
      scope: 'library',
      previousById: new Map([
        [1, 10],
        [2, 20],
        [3, 30],
      ]),
      updates: [
        { id: 1, order: 0 },
        { id: 2, order: 1 },
        { id: 3, order: 2 },
      ],
    });
    return { calls };
  } catch (error) {
    return { calls, error };
  }
}

{
  const { calls } = await run('success');
  assert.equal(calls.length, 3);
  assert.deepEqual(
    calls.map((call) => call.patch.library_order),
    [0, 1, 2],
  );
  console.log('ok success');
}

{
  const { calls, error } = await run('fail-second');
  assert.ok(error instanceof AppError);
  assert.equal(error.code, 'order_write_failed');
  assert.equal(calls.length, 3);
  assert.deepEqual(calls[2].patch, { library_order: 10 });
  console.log('ok partial rollback');
}

{
  const { calls, error } = await run('fail-rollback');
  assert.ok(error instanceof AppError);
  assert.match(error.message, /回退未完成/);
  assert.equal(calls.length, 3);
  console.log('ok rollback failure reported');
}
