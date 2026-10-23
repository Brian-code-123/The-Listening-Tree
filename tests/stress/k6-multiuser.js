// Many different signed-in users chatting with a slow (mock) model while other
// people log in. See run-multiuser.sh. The model here is the mock in
// mock_zhipu.py: 0.5 s to the first words, about 3.5 s for a whole reply.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:5100';
const USERS = JSON.parse(__ENV.K6_USERS);
const PASSWORD = __ENV.K6_PASSWORD;
const fullReply = new Trend('chat_full_reply_ms', true);
const serverErrors = new Counter('server_errors');

export const options = {
  scenarios: {
    chatters: { executor: 'constant-vus', vus: USERS.length, duration: '60s', exec: 'chat' },
    login_burst: { executor: 'per-vu-iterations', vus: 30, iterations: 2, startTime: '20s', exec: 'loginBurst' },
    watcher: { executor: 'constant-vus', vus: 2, duration: '60s', exec: 'watch' },
  },
  thresholds: {
    // k6 buffers a streamed body, so this is the time for the WHOLE reply: the mock
    // model takes about 3.5 s, so 6 s leaves room for queueing but not for a stall.
    // The time to the first words was measured separately (docs/TESTING.md).
    chat_full_reply_ms: ['p(95)<6000'],
    'http_req_duration{kind:me}': ['p(95)<500'],
    server_errors: ['count==0'],
    checks: ['rate>0.99'],
  },
};

// Each user gets their own address, as the limiter would see real people.
const ip = (i) => `198.51.100.${(i % 250) + 1}`;
const headers = (i, extra = {}) => ({ 'X-Forwarded-For': ip(i), ...extra });

export function setup() {
  return USERS.map((email, i) => {
    const res = http.post(`${BASE}/auth/login`, { email, password: PASSWORD }, { headers: headers(i, { Accept: 'application/json' }) });
    if (res.status !== 200) throw new Error(`login ${i} failed: ${res.status}`);
    const jar = http.cookieJar();
    return { email, cookie: res.cookies['lt_session'][0].value };
  });
}

export function chat(data) {
  const i = (__VU - 1) % data.length;
  const params = { headers: headers(i, { Cookie: `lt_session=${data[i].cookie}`, Accept: 'text/event-stream' }), tags: { kind: 'chat' } };
  const start = Date.now();
  const res = http.post(`${BASE}/get_response`, { msg: 'I did not sleep well last night.' }, params);
  if (res.status >= 500) serverErrors.add(1);
  check(res, { 'chat answered 200 or limited 429': (r) => r.status === 200 || r.status === 429 });
  if (res.status === 200) {
    fullReply.add(Date.now() - start);
  }
  sleep(3);
}

export function loginBurst() {
  const i = __VU - 1;
  const res = http.post(`${BASE}/auth/login`, { email: USERS[i % USERS.length], password: PASSWORD }, { headers: headers(100 + i, { Accept: 'application/json' }), tags: { kind: 'login' } });
  if (res.status >= 500) serverErrors.add(1);
  if (res.status !== 200) console.log(`login ${__VU} got ${res.status}: ${String(res.body).slice(0, 90)}`);
  check(res, { 'login answered 200': (r) => r.status === 200 });
  // Not 5: uvicorn closes an idle connection after 5 s, and a client that reuses it at
  // that very moment gets a reset, which would look like a failed login.
  sleep(8);
}

export function watch(data) {
  const res = http.get(`${BASE}/me`, { headers: headers(0, { Cookie: `lt_session=${data[0].cookie}` }), tags: { kind: 'me' } });
  if (res.status >= 500) serverErrors.add(1);
  check(res, { '/me is 200': (r) => r.status === 200 });
  sleep(0.5);
}
