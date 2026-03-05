"use client";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { Complaint } from "@/types";
import { CheckCircle, MessageSquare } from "lucide-react";

interface Props {
  onUnreadChange: (count: number) => void;
}

export default function ComplaintsPanel({ onUnreadChange }: Props) {
  const [complaints, setComplaints] = useState<Complaint[]>([]);

  async function load() {
    const data = await api.getComplaints() as Complaint[];
    setComplaints(data);
    onUnreadChange(data.filter((c) => !c.is_read).length);
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  async function markRead(id: number) {
    await api.markComplaintRead(id);
    toast.success("Marked as read");
    load();
  }

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
        <MessageSquare size={20} />
        Patient Complaints
      </h2>

      {complaints.length === 0 ? (
        <p className="text-gray-400 text-sm">No complaints yet.</p>
      ) : (
        <div className="space-y-3">
          {complaints.map((c) => (
            <div
              key={c.id}
              className={`rounded-xl border p-4 ${
                c.is_read ? "border-gray-100 bg-white" : "border-red-200 bg-red-50"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-700">{c.patient_phone}</p>
                  <p className="text-sm text-gray-600 mt-1 break-words">{c.message}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    {new Date(c.created_at).toLocaleString("en-PK")}
                  </p>
                </div>
                {!c.is_read && (
                  <button
                    onClick={() => markRead(c.id)}
                    title="Mark as read"
                    className="flex-shrink-0 text-green-600 hover:text-green-700"
                  >
                    <CheckCircle size={20} />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
