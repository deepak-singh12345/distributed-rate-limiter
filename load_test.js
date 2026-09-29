import http from "k6/http";
import { Counter, Trend } from "k6/metrics";

const ok200 = new Counter("status_200");
const rejected429 = new Counter("status_429");
const checkMs = new Trend("ratelimit_check_ms");


const failed = new Counter("status_other");   // add near the other counters

export const options = {
    scenarios: {
        burst: {
            executor: "per-vu-iterations",
            vus: 50,
            iterations: 5,        // 50 x 5 = 250 requests total
            maxDuration: "30s",
        },
    },
    thresholds: {
        status_200: ["count==100"],
        status_429: ["count==150"],
        status_other: ["count==0"],     // any connection error or 5xx fails the test
    },
};

export default function () {
    const res = http.get("http://127.0.0.1:8000/api/data");
    if (res.status === 200) ok200.add(1);
    else if (res.status === 429) rejected429.add(1);
    else failed.add(1);

    for (const name in res.headers) {
        if (name.toLowerCase() === "x-ratelimit-check-ms") {
            checkMs.add(parseFloat(res.headers[name]));
        }
    }
}