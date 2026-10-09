import { api, ApiError, buildQuery, setAccessToken } from '../client';

describe('buildQuery', () => {
  it('drops empty values and joins lists', () => {
    expect(buildQuery({ a: '1', b: '', c: undefined, type: ['BUY', 'SELL'], none: [] })).toBe('?a=1&type=BUY%2CSELL');
  });
});

describe('api()', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setAccessToken(null);
  });

  it('refreshes once on 401 and retries with the new token', async () => {
    setAccessToken('expired');
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access: 'fresh', access_expires_in: 900, user: {} }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    await expect(api('/customers')).resolves.toEqual({ ok: true });
    const retried = fetchMock.mock.calls[2][1] as RequestInit;
    expect((retried.headers as Record<string, string>).Authorization).toBe('Bearer fresh');
  });

  it('turns the error envelope into an ApiError', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(
      new Response(JSON.stringify({ error: { code: 'validation_error', message: 'bad', details: { x: ['y'] }, request_id: 'r1' } }), { status: 400 }),
    );
    const error = (await api("/goals/G1").catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.fieldError('x')).toBe('y');
    expect(error.requestId).toBe('r1');
  });
});
