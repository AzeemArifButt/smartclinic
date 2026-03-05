import { getToken } from "./auth";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}/api${path}`, { ...options, headers });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || "Request failed");
  }

  return res.json();
}

// Auth
export const api = {
  register: (data: object) =>
    request("/clinic/register", { method: "POST", body: JSON.stringify(data) }),

  login: (data: object) =>
    request("/auth/login", { method: "POST", body: JSON.stringify(data) }),

  getClinic: () => request("/clinic/me"),

  updateClinic: (data: object) =>
    request("/clinic/me", { method: "PUT", body: JSON.stringify(data) }),

  getQrCode: () => `${BASE}/api/clinic/qr`,

  // Queue
  getQueueStats: () => request("/queue/stats"),

  nextToken: (doctor_id: number) =>
    request(`/queue/next?doctor_id=${doctor_id}`, { method: "POST" }),

  resetQueue: (doctor_id: number) =>
    request(`/queue/reset?doctor_id=${doctor_id}`, { method: "POST" }),

  // Tokens
  getTodayTokens: (doctor_id: number) =>
    request(`/tokens/today?doctor_id=${doctor_id}`),

  issueWalkin: (doctor_id: number) =>
    request("/token/issue-walkin", { method: "POST", body: JSON.stringify({ doctor_id }) }),

  // Doctors
  getDoctors: () => request("/doctors"),

  createDoctor: (data: object) =>
    request("/doctors", { method: "POST", body: JSON.stringify(data) }),

  updateDoctor: (id: number, data: object) =>
    request(`/doctors/${id}`, { method: "PUT", body: JSON.stringify(data) }),

  deleteDoctor: (id: number) =>
    request(`/doctors/${id}`, { method: "DELETE" }),

  // Complaints
  getComplaints: () => request("/complaints"),

  getUnreadCount: () => request<{ unread: number }>("/complaints/unread-count"),

  markComplaintRead: (id: number) =>
    request(`/complaints/${id}/read`, { method: "POST" }),

  // Public status (no auth)
  getPublicStatus: async (slug: string) => {
    const res = await fetch(`${BASE}/api/status/${slug}`);
    if (!res.ok) throw new Error("Clinic not found");
    return res.json();
  },
};
