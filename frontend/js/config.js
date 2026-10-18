/* Deployment configuration.
 * Leave empty when the frontend and API share the same origin.
 * For separate hosting, set this to the backend origin, e.g. https://api.example.com
 * Do not put API keys or other secrets in frontend configuration.
 */
window.MEDFORM_API_BASE_URL = window.MEDFORM_API_BASE_URL || "";
window.MEDFORM_DEBUG = window.MEDFORM_DEBUG === true;
