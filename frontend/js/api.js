const API_BASE_URL = "";

async function apiRequest(endpoint, options = {}) {

    console.log("[API] Starting request:", endpoint);

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

    console.log("[API] Sending fetch:", {
        url: `${API_BASE_URL}${endpoint}`,
        method: options.method || "GET",
        isFormData: options.body instanceof FormData
    });

    const response = await fetch(
        `${API_BASE_URL}${endpoint}`,
        {
            ...options,
            headers
        }
    );

    console.log("[API] Fetch completed:", {
        status: response.status,
        ok: response.ok,
        contentType: response.headers.get("content-type")
    });

    const contentType =
        response.headers.get("content-type") || "";

    let data;

    if (contentType.includes("application/json")) {

        console.log("[API] Waiting for JSON body...");

        data = await response.json();

        console.log(
            "[API] JSON body received:",
            data
        );

    } else {

        console.log("[API] Waiting for text body...");

        data = await response.text();

        console.log(
            "[API] Text body received:",
            data
        );
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

    console.log(
        "[API] Request completed successfully:",
        endpoint
    );

    return data;
}