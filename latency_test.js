// latency_test.js
import http from "k6/http";
import { Trend } from "k6/metrics";

const checkMs = new Trend("ratelimit_check_ms");

export const options = {
    vus: 10,
    duration: "10s",
    thresholds: { ratelimit_check_ms: ["p(95)<10"] },
};

export default function () {
    const res = http.get("http://127.0.0.1:8000/api/data");
    for (const name in res.headers) {
        if (name.toLowerCase() === "x-ratelimit-check-ms") {
            checkMs.add(parseFloat(res.headers[name]));
        }
    }
}