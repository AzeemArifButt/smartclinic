"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import type { AuthUser } from "@/types";

export default function RegisterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    name: "",
    city: "",
    email: "",
    password: "",
    whatsapp_number: "",
    wa_phone_number_id: "",
    opening_time: "09:00",
    closing_time: "22:00",
  });

  function set(field: string, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const auth = await api.register(form) as AuthUser;
      saveAuth(auth);
      toast.success("Clinic registered! Welcome to SmartClinic.");
      router.replace("/dashboard");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  const field = (label: string, key: keyof typeof form, type = "text", placeholder = "") => (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type={type}
        value={form[key]}
        onChange={(e) => set(key, e.target.value)}
        className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500"
        placeholder={placeholder}
      />
    </div>
  );

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-900 to-brand-700 py-10">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-8">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-brand-900">SmartClinic</h1>
          <p className="text-gray-500 mt-1">Register your clinic</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {field("Clinic Name", "name", "text", "City Medical Centre")}
          {field("City", "city", "text", "Karachi")}
          {field("Owner Email", "email", "email", "owner@clinic.com")}
          {field("Password", "password", "password", "••••••••")}
          {field("WhatsApp Number", "whatsapp_number", "text", "+923001234567")}
          {field("Meta Phone Number ID", "wa_phone_number_id", "text", "123456789012345")}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Opening Time (PKT)</label>
              <input
                type="time"
                value={form.opening_time}
                onChange={(e) => set("opening_time", e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Closing Time (PKT)</label>
              <input
                type="time"
                value={form.closing_time}
                onChange={(e) => set("closing_time", e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-brand-600 hover:bg-brand-700 text-white font-semibold py-2.5 rounded-lg transition disabled:opacity-60 mt-2"
          >
            {loading ? "Registering..." : "Register Clinic"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-500 mt-6">
          Already registered?{" "}
          <Link href="/login" className="text-brand-600 font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
