"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { getAuth } from "@/lib/auth";
import type { Doctor, Clinic } from "@/types";
import { ArrowLeft, Plus, Pencil, Trash2, QrCode } from "lucide-react";

export default function SettingsPage() {
  const router = useRouter();
  const auth = getAuth();

  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [clinic, setClinic] = useState<Clinic | null>(null);
  const [newName, setNewName] = useState("");
  const [newSpecialty, setNewSpecialty] = useState("");
  const [editId, setEditId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editSpecialty, setEditSpecialty] = useState("");

  useEffect(() => {
    if (!auth || auth.role !== "owner") {
      router.replace("/dashboard");
      return;
    }
    loadDoctors();
    api.getClinic().then((c) => setClinic(c as Clinic));
  }, []);

  async function loadDoctors() {
    const data = await api.getDoctors() as Doctor[];
    setDoctors(data);
  }

  async function addDoctor(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      await api.createDoctor({ name: newName.trim(), specialty: newSpecialty.trim() || null });
      toast.success("Doctor added");
      setNewName("");
      setNewSpecialty("");
      loadDoctors();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  }

  async function saveEdit(id: number) {
    try {
      await api.updateDoctor(id, { name: editName, specialty: editSpecialty || null });
      toast.success("Updated");
      setEditId(null);
      loadDoctors();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  }

  async function toggleActive(d: Doctor) {
    await api.updateDoctor(d.id, { is_active: !d.is_active });
    loadDoctors();
  }

  async function deleteDoctor(id: number) {
    if (!confirm("Delete this doctor? This cannot be undone.")) return;
    await api.deleteDoctor(id);
    toast.success("Doctor removed");
    loadDoctors();
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-brand-900 text-white px-6 py-4 flex items-center gap-4">
        <Link href="/dashboard" className="text-blue-200 hover:text-white">
          <ArrowLeft size={20} />
        </Link>
        <h1 className="text-xl font-bold">Settings — {clinic?.name}</h1>
      </header>

      <main className="max-w-2xl mx-auto p-6 space-y-8">
        {/* QR Code */}
        {clinic && (
          <section className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <QrCode size={20} />
              Clinic QR Code
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              Print and display this QR so patients can check queue status.
            </p>
            <a
              href={api.getQrCode()}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 bg-brand-600 text-white px-5 py-2.5 rounded-lg font-medium hover:bg-brand-700 transition"
            >
              <QrCode size={16} />
              Download QR Code
            </a>
            <p className="text-xs text-gray-400 mt-2">
              Points to:{" "}
              <span className="font-mono">
                {process.env.NEXT_PUBLIC_API_URL?.replace("/api", "")}/status/{clinic.slug}
              </span>
            </p>
          </section>
        )}

        {/* Add Doctor */}
        <section className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
            <Plus size={20} />
            Add Doctor
          </h2>
          <form onSubmit={addDoctor} className="flex flex-col sm:flex-row gap-3">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Doctor name"
              required
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <input
              value={newSpecialty}
              onChange={(e) => setNewSpecialty(e.target.value)}
              placeholder="Specialty (optional)"
              className="flex-1 border border-gray-300 rounded-lg px-4 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <button
              type="submit"
              className="bg-brand-600 hover:bg-brand-700 text-white font-semibold px-5 py-2.5 rounded-lg transition"
            >
              Add
            </button>
          </form>
        </section>

        {/* Doctors list */}
        <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-800">Doctors ({doctors.length})</h2>
          </div>
          {doctors.length === 0 ? (
            <p className="text-gray-400 text-sm p-6">No doctors added yet.</p>
          ) : (
            <ul className="divide-y divide-gray-100">
              {doctors.map((d) => (
                <li key={d.id} className="px-6 py-4">
                  {editId === d.id ? (
                    <div className="flex gap-3 flex-wrap">
                      <input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                      />
                      <input
                        value={editSpecialty}
                        onChange={(e) => setEditSpecialty(e.target.value)}
                        placeholder="Specialty"
                        className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
                      />
                      <button
                        onClick={() => saveEdit(d.id)}
                        className="bg-brand-600 text-white px-4 py-1.5 rounded-lg text-sm"
                      >
                        Save
                      </button>
                      <button
                        onClick={() => setEditId(null)}
                        className="text-gray-500 text-sm px-3 py-1.5"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium text-gray-800">
                          Dr. {d.name}
                          {!d.is_active && (
                            <span className="ml-2 text-xs text-gray-400 font-normal">
                              (inactive)
                            </span>
                          )}
                        </p>
                        {d.specialty && (
                          <p className="text-sm text-gray-500">{d.specialty}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleActive(d)}
                          className={`text-xs px-3 py-1 rounded-full font-medium ${
                            d.is_active
                              ? "bg-green-100 text-green-700 hover:bg-green-200"
                              : "bg-gray-100 text-gray-500 hover:bg-gray-200"
                          }`}
                        >
                          {d.is_active ? "Active" : "Inactive"}
                        </button>
                        <button
                          onClick={() => {
                            setEditId(d.id);
                            setEditName(d.name);
                            setEditSpecialty(d.specialty || "");
                          }}
                          className="text-gray-400 hover:text-brand-600"
                        >
                          <Pencil size={16} />
                        </button>
                        <button
                          onClick={() => deleteDoctor(d.id)}
                          className="text-gray-400 hover:text-red-500"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
