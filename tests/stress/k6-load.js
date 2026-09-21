import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:5100';
const SMOKE = __ENV.PROFILE === 'smoke';

const stages = SMOKE
  ? [{ duration: '10s', target: 10 }, { duration: '10s', target: 10 }, { duration: '5s', target: 0 }]
  : [
      { duration: '30s', target: 25 },
      { duration: '60s', target: 50 },
      { duration: '30s', target: 100 },
      { duration: '20s', target: 0 },
    ];

export const options = {
  scenarios: {
    public: { executor: 'ramping-vus', exec: 'publicFlow', startVUs: 0, stages, tags: { flow: 'public' } },
    authed: {
      executor: 'ramping-vus',
      exec: 'authedFlow',
      startVUs: 0,
      stages: stages.map((s) => ({ ...s, target: Math.ceil(s.target / 2) })),
      tags: { flow: 'authed' },
    },
  },
  // Pass/fail criteria (referenced verbatim in docs/TESTING.md)
  thresholds: {
    'http_req_failed{flow:public}': ['rate<0.01'],
    'http_req_duration{flow:public}': ['p(95)<500'],
    'http_req_failed{flow:authed}': ['rate<0.01'],
    'http_req_duration{flow:authed}': ['p(95)<1500'],
    checks: ['rate>0.99'],
  },
};

// One login only: /auth/login is rate limited (10/min/IP), so every VU reuses this session.
export function setup() {
  const res = http.post(
    `${BASE}/auth/login`,
    { email: __ENV.K6_EMAIL, password: __ENV.K6_PASSWORD, remember_me: 'on' },
    { headers: { Accept: 'application/json' } },
  );
  const ok = check(res, { 'setup login succeeded': (r) => r.status === 200 && r.json('success') === true });
  if (!ok) throw new Error(`setup login failed: ${res.status} ${res.body}`);
  return { cookie: res.cookies['lt_session'][0].value };
}

export function publicFlow() {
  for (const path of ['/health', '/translations/en', '/config']) {
    const r = http.get(`${BASE}${path}`);
    check(r, { [`${path} is 200`]: (x) => x.status === 200 });
  }
  sleep(1);
}

export function authedFlow(data) {
  const params = { headers: { Cookie: `lt_session=${data.cookie}` } };
  for (const path of ['/me', '/conversations', '/get_reminders']) {
    const r = http.get(`${BASE}${path}`, params);
    check(r, { [`${path} is 200`]: (x) => x.status === 200 });
  }
  const chat = http.post(`${BASE}/get_response`, { msg: 'hello' }, params);
  check(chat, { 'chat reply is 200': (x) => x.status === 200 });
  sleep(1);
}
