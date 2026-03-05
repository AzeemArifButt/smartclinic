"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Clock, Users } from "lucide-react";

interface DoctorStatus {
  doctor_name: string;
  specialty: string | null;
  current_serving: number;
  total_issued_today: number;
}

interface ClinicStatus {
  clinic_name: string;
  city: string;
  opening_time: string;
  closing_time: string;
  doctors: DoctorStatus[];
}

export default function PublicStatusPage({ params }: { params: { slug: string } }) {
  const [status, setStatus] = useState<ClinicStatus | null>(null);
  const [error, setError] = useState("");

  async function load() {
    try {
      const data = await api.getPublicStatus(params.slug) as ClinicStatus;
      setStatus(data);
    } catch {
      setError("Clinic not found.");
    }
  }

  useEffect(() => {
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, [params.slug]);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500 text-lg">{error}</p>
      </div>
    );
  }

  if (!status) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-400 animate-pulse">Loading...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-900 to-brand-700 p-6">
      <div className="max-w-lg mx-auto">
        {/* Header */}
        <div className="text-center text-white mb-8 mt-4">
          <h1 className="text-3xl font-bold">{status.clinic_name}</h1>
          <p className="text-blue-200 mt-1">{status.city}</p>
          <div className="flex items-center justify-center gap-1.5 text-blue-200 text-sm mt-2">
            <Clock size={14} />
            {status.opening_time} – {status.closing_time} PKT
          </div>
          <p className="text-xs text-blue-300 mt-3">Live queue status · Updates every 10 seconds</p>
        </div>

        {/* Doctor cards */}
        <div className="space-y-4">
          {status.doctors.map((d) => (
            <div key={d.doctor_name} className="bg-white rounded-2xl shadow-lg p-6">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-lg font-bold text-gray-800">Dr. {d.doctor_name}</h2>
                  {d.specialty && (
                    <p className="text-sm text-gray-500">{d.specialty}</p>
                  )}
                </div>
                <div className="flex items-center gap-1 text-gray-500 text-sm">
                  <Users size={15} />
                  {d.total_issued_today} today
                </div>
              </div>
              <div className="bg-brand-600 rounded-xl p-5 text-white text-center">
                <p className="text-sm font-medium opacity-80">Now Serving</p>
                <p className="text-5xl font-bold mt-1">#{d.current_serving}</p>
              </div>
              <p className="text-center text-sm text-gray-400 mt-3">
                {d.total_issued_today - d.current_serving > 0
                  ? `${d.total_issued_today - d.current_serving} patient(s) waiting`
                  : "No patients waiting"}
              </p>
            </div>
          ))}
        </div>

        {status.doctors.length === 0 && (
          <div className="bg-white rounded-2xl shadow p-8 text-center text-gray-400">
            No active doctors at the moment.
          </div>
        )}

        {/* WhatsApp CTA */}
        <div className="bg-white/10 rounded-2xl p-5 text-center text-white mt-6">
          <p className="text-sm font-medium">Book your appointment via WhatsApp</p>
          <p className="text-blue-200 text-sm mt-1">Send any message to get started</p>
        </div>
      </div>
    </div>
  );
}
