import axios from 'axios';

// Since the client calls the Next.js API route proxy, baseURL should be relative
const API_BASE_URL = '/api/beacon/v1';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to attach Supabase token if available
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('supabase_access_token');
  if (token) {
    config.headers['X-Supabase-Token'] = token;
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});

export const api = {
  getProjects: async () => {
    const response = await apiClient.get('/projects/');
    return response.data;
  },
  createProject: async (data: { name: string; url: string }) => {
    const response = await apiClient.post('/projects/', data);
    return response.data;
  },
  deleteProject: async (projectId: string) => {
    const response = await apiClient.delete(`/projects/${projectId}`);
    return response.data;
  },
  getProject: async (projectId: string) => {
    const response = await apiClient.get(`/projects/${projectId}`);
    return response.data;
  },
  getScans: async (projectId: string) => {
    const response = await apiClient.get(`/scans/${projectId}`);
    return response.data;
  },
  getScanProgress: async (projectId: string, scanId: string) => {
    const response = await apiClient.get(`/scans/${projectId}/${scanId}/progress`);
    return response.data;
  },
  startScan: async (data: { project_id: string; scan_mode: string }) => {
    const response = await apiClient.post('/scans/', data);
    return response.data;
  },
  getScan: async (
    projectId: string,
    scanId: string,
    options?: { profile?: string; persona?: string; view?: string }
  ) => {
    const params = new URLSearchParams();
    if (options?.profile) params.append("profile", options.profile);
    if (options?.persona) params.append("persona", options.persona);
    if (options?.view) params.append("view", options.view);
    const queryString = params.toString() ? `?${params.toString()}` : "";
    const response = await apiClient.get(`/scans/${projectId}/${scanId}${queryString}`);
    return response.data;
  },
  getProfiles: async () => {
    const response = await apiClient.get('/profiles');
    return response.data;
  },
  getPersonas: async () => {
    const response = await apiClient.get('/personas');
    return response.data;
  },
  exportScan: async (projectId: string, scanId: string, format: "sarif" | "earl" | "markdown" | "json" | "csv") => {
    const response = await apiClient.get(`/scans/${projectId}/${scanId}/export/${format}`, {
      responseType: format === "markdown" || format === "csv" ? "text" : "json",
    });
    return response.data;
  },
  generateAccessibilityStatement: async (
    projectId: string,
    scanId: string,
    orgName?: string,
    profile?: string,
  ) => {
    const params = new URLSearchParams();
    if (orgName) params.append("org_name", orgName);
    if (profile) params.append("profile", profile);
    const queryString = params.toString() ? `?${params.toString()}` : "";
    const response = await apiClient.get(`/scans/${projectId}/${scanId}/statement${queryString}`);
    return response.data;
  },
};

export function downloadScanReport(projectId: string, scanId: string, format: "sarif" | "earl" | "markdown" | "json" | "csv") {
  const extensionMap: Record<string, string> = {
    sarif: "sarif",
    earl: "earl.jsonld",
    markdown: "md",
    json: "json",
    csv: "csv",
  };
  const ext = extensionMap[format] || format;
  const link = document.createElement("a");
  link.href = `/api/beacon/v1/scans/${encodeURIComponent(projectId)}/${encodeURIComponent(scanId)}/export/${encodeURIComponent(format)}`;
  link.download = `beacon-scan-${scanId}.${ext}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

export default api;

export function toUserFacingError(error: unknown): { message: string; retryable: boolean } {
  let message = "An unexpected error occurred.";
  let retryable = true;

  if (typeof error === "object" && error !== null && "response" in error) {
    const resp = (error as { response?: { status?: number; data?: { error?: string; detail?: string } } }).response;
    const status = resp?.status;
    const data = resp?.data;

    if (status === 401 || status === 403) {
      message = data?.error || data?.detail || "Access denied. Please check your credentials.";
      retryable = false;
    } else if (status === 404) {
      message = data?.error || data?.detail || "Requested resource not found.";
      retryable = false;
    } else if (status === 502) {
      const isCloud = typeof window !== "undefined" && !window.location.hostname.includes("localhost") && window.location.hostname !== "127.0.0.1";
      message = data?.error || (isCloud
        ? "BEACON backend is waking up or temporarily unreachable. Cloud instances (e.g. Render free tier) spin down when idle and take ~30–60 seconds to cold boot. Please wait a moment and retry."
        : "BEACON backend is offline. Please start the backend server on port 8000 (`py -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`).");
      retryable = true;
    } else if (status && status >= 500) {
      message = data?.error || data?.detail || "Server error occurred. Please try again later.";
    } else {
      message = data?.error || data?.detail || `Error: ${status} - ${(error as { message?: string }).message || "Unknown error"}`;
    }
  } else if (typeof error === "object" && error !== null && "request" in error) {
    message = "Network error. Please check your connection and try again.";
  } else if (error instanceof Error) {
    message = error.message;
  } else if (typeof error === "string") {
    message = error;
  }

  return { message, retryable };
}

