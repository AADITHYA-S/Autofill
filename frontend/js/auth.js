// frontend/js/auth.js

function saveAccessToken(token) {
    localStorage.setItem("access_token", token);
}

function getAccessToken() {
    return localStorage.getItem("access_token");
}

function isTokenExpired(token) {
    try {
        const payload = token.split(".")[1];
        const decodedPayload = JSON.parse(
            atob(payload.replace(/-/g, "+").replace(/_/g, "/"))
        );

        return !decodedPayload.exp || decodedPayload.exp * 1000 <= Date.now();
    } catch {
        return true;
    }
}

function isAuthenticated() {
    const token = getAccessToken();

    if (!token || isTokenExpired(token)) {
        localStorage.removeItem("access_token");
        return false;
    }

    return true;
}

document.querySelectorAll(".brand[data-authenticated-href]").forEach((brand) => {
    const landingPage = brand.getAttribute("href");
    const dashboard = brand.dataset.authenticatedHref;

    const updateDestination = () => {
        brand.setAttribute("href", isAuthenticated() ? dashboard : landingPage);
    };

    updateDestination();
    brand.addEventListener("click", updateDestination);
});

function logout() {
    localStorage.removeItem("access_token");
    window.location.href = "../login/login.html";
}

/**
 * Use this at the beginning of protected pages.
 */
function requireAuthentication() {
    if (!isAuthenticated()) {
        window.location.href = "../login/login.html";
    }
}

/**
 * Use this on login/register pages if you don't want an already
 * authenticated user to see them.
 */
function redirectIfAuthenticated() {
    if (isAuthenticated()) {
        window.location.href = "../dashboard/dashboard.html";
    }
}
