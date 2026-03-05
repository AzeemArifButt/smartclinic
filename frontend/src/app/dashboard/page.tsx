"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { getAuth, clearAuth } from "@/lib/auth";
import type { QueueStats, QueueState } from "@/types";
import QueueTab from "@/components/QueueTab";
import ComplaintsPanel from "@/components/ComplaintsPanel";
import { Settings, LogOut, MessageSquare } from "lucide-react";

export default function DashboardPage() {
  const router = useRouter();
  const auth = getAuth();

  const [stats, setStats] = useState<QueueStats | null>(null);
  const [activeTab, setActiveTab] = useState<number | "complaints">(0);
  const [unreadComplaints, setUnreadComplaints] = useState(0);

  const loadStats = useCallback(async () => {
    try {
      const data = await api.getQueueStats() as QueueStats;
      setStats(data);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    if (!auth) {
      router.replace("/login");
      return;
    }
    loadStats();
    const interval = setInterval(loadStats, 5000);
    return () => clearInterval(interval);
  }, [auth, router, loadStats]);

  function handleLogout() {
    clearAuth();
    router.replace("/login");
    toast.success("Logged out");
  }

  if (!auth) return null;

  const doctors = stats?.doctors ?? [];
  const activeDoctor: QueueState | undefined =
    typeof activeTab === "number" ? doctors[activeTab] : undefined;

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-brand-900 text-white px-6 py-4 flex items-center justify-between shadow">
        <div>
          <h1 className="text-xl font-bold">{auth.clinic_name}</h1>
          <p className="text-xs text-blue-200 capitalize">{auth.role}</p>
        </div>
        <div className="flex items-center gap-3">
          {auth.role === "owner" && (
            <Link
              href="/dashboard/settings"
              className="flex items-center gap-1.5 text-sm text-blue-200 hover:text-white transition"
            >
              <Settings size={16} />
              Settings
            </Link>
          )}
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-sm text-blue-200 hover:text-white transition"
          >
            <LogOut size={16} />
            Logout
          </button>
        </div>
      </header>

      {/* Tab bar */}
      <div className="bg-white border-b border-gray-200 px-6 flex items-center gap-1 overflow-x-auto">
        {doctors.map((d, i) => (
          <button
            key={d.doctor_id}
            onClick={() => setActiveTab(i)}
            className={`px-5 py-3.5 text-sm font-medium whitespace-nowrap border-b-2 transition ${
              activeTab === i
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-gray-500 hover:text-gray-800"
            }`}
          >
            Dr. {d.doctor_name}
          </button>
        ))}
        <button
          onClick={() => setActiveTab("complaints")}
          className={`flex items-center gap-1.5 px-5 py-3.5 text-sm font-medium whitespace-nowrap border-b-2 transition ${
            activeTab === "complaints"
              ? "border-brand-600 text-brand-600"
              : "border-transparent text-gray-500 hover:text-gray-800"
          }`}
        >
          <MessageSquare size={15} />
          Complaints
          {unreadComplaints > 0 && (
            <span className="ml-1 bg-red-500 text-white text-xs font-bold rounded-full w-5 h-5 flex items-center justify-center">
              {unreadComplaints > 9 ? "9+" : unreadComplaints}
            </span>
          )}
        </button>
      </div>

      {/* Content */}
      <main className="flex-1 max-w-5xl w-full mx-auto">
        {activeTab === "complaints" ? (
          <div className="p-6">
            <ComplaintsPanel onUnreadChange={setUnreadComplaints} />
          </div>
        ) : activeDoctor ? (
          <QueueTab key={activeDoctor.doctor_id} state={activeDoctor} onRefresh={loadStats} />
        ) : (
          <div className="p-6 text-center text-gray-400">
            <p className="text-lg mt-12">No active doctors.</p>
            {auth.role === "owner" && (
              <Link
                href="/dashboard/settings"
                className="mt-4 inline-block text-brand-600 hover:underline font-medium"
              >
                Add doctors in Settings
              </Link>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
