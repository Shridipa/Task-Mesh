import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
    vus: 10,
    duration: '10s',
};

export default function () {
    // We'll hit the /jobs endpoint to simulate load
    // Note: since it's an authenticated endpoint, we use the DEV_HEADERS or ADMIN_HEADERS
    const url = 'http://host.docker.internal:8000/jobs';
    const payload = JSON.stringify({
        job_type: 'email',
        payload: { to: 'loadtest@example.com' },
        priority: 5,
    });
    
    const params = {
        headers: {
            'Content-Type': 'application/json',
            'X-Role': 'admin',
        },
    };

    const res = http.post(url, payload, params);
    
    check(res, {
        'is status 201': (r) => r.status === 201,
        'is rate limited (429)': (r) => r.status === 429,
    });
    
    // Add a small sleep to avoid overwhelming a purely in-memory dummy
    sleep(0.01);
}
