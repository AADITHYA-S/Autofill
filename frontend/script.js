// frontend/script.js
// Public landing-page navigation.
//
// Login and Sign up are public.
// Documents, Forms, and Profile are protected.
// If a protected destination is selected without a token,
// the user is sent to the login page instead.

const toast = document.getElementById("toast");

function showToast(message) {
    if (!toast) {
        return;
    }

    toast.textContent = message;
    toast.classList.add("show");

    clearTimeout(window.toastTimer);

    window.toastTimer = setTimeout(() => {
        toast.classList.remove("show");
    }, 2400);
}


/*
 * Protected pages
 */
const protectedRoutes = {
    dashboard: "pages/dashboard/dashboard.html",
    upload: "pages/upload/upload.html",
    documents: "pages/upload/upload.html",
    fill: "pages/autofill/autofill.html",
    profile: "pages/profile/profile.html"
};


/*
 * Check whether the user is logged in.
 *
 * auth.js stores the JWT as "access_token" in localStorage.
 */
function isUserAuthenticated() {
    if (typeof isAuthenticated === "function") {
        return isAuthenticated();
    }

    return Boolean(localStorage.getItem("access_token"));
}


/*
 * Navigate to a protected page.
 *
 * Logged in:
 *      → requested page
 *
 * Not logged in:
 *      → login page
 */
function goToProtectedPage(action) {
    const destination = protectedRoutes[action];

    if (!destination) {
        return;
    }

    if (!isUserAuthenticated()) {
        window.location.href = "pages/login/login.html";
        return;
    }

    window.location.href = destination;
}


/*
 * Handle all protected landing-page buttons.
 */
document.querySelectorAll("[data-action]").forEach((element) => {
    element.addEventListener("click", (event) => {
        const action = element.dataset.action;

        if (protectedRoutes[action]) {
            event.preventDefault();
            goToProtectedPage(action);
        }
    });
});


/*
 * Navigation highlighting
 */
document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", () => {
        document.querySelectorAll(".nav-link").forEach((item) => {
            item.classList.remove("active");
        });

        link.classList.add("active");
    });
});


/*
 * Add a class when the user is already authenticated.
 *
 * This is optional and allows the landing page CSS to style
 * authenticated users differently later if needed.
 */
if (isUserAuthenticated()) {
    document.body.classList.add("authenticated");
}