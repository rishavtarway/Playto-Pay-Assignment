// Single axios instance for the whole app — auth token is stored in
// localStorage and attached to every request via an interceptor.
import axios from "axios";

const client = axios.create({ baseURL: "/api/v1" });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Token ${token}`;
  return config;
});

// On 401, drop the stale token and bounce to /login.
client.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);

export default client;
