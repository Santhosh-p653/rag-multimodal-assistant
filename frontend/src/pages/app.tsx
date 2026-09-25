import Home from "./index";

/**
 * User UI Route (/app)
 * Specialized exclusively for technician & operator chat and multilingual voice troubleshooting.
 * Admin upload, file deletion, and backend management routes are strictly isolated to /admin.
 */
export default function AppPage() {
  return <Home />;
}
