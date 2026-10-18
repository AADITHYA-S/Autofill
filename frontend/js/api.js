const API_BASE_URL = String(window.MEDFORM_API_BASE_URL || "").replace(/\/$/, "");

async function apiRequest(endpoint, options = {}) {

    const token = localStorage.getItem("access_token");

    const headers = {
        ...(options.headers || {})
    };

    if (!(options.body instanceof FormData)) {
        headers["Content-Type"] = "application/json";
    }

    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(
        `${API_BASE_URL}${endpoint}`,
        {
            ...options,
            headers
        }
    );

    const contentType =
        response.headers.get("content-type") || "";

    let data;

    if (contentType.includes("application/json")) {

        data = await response.json();

    } else {

        data = await response.text();

    }

    if (!response.ok) {

        if (response.status === 401) {
            localStorage.removeItem("access_token");
        }

        let message = "Something went wrong.";

        if (
            typeof data === "object" &&
            data?.detail
        ) {
            message = data.detail;

        } else if (
            typeof data === "string" &&
            data.trim()
        ) {
            message = data;
        }

        throw new Error(message);
    }

    return data;
}