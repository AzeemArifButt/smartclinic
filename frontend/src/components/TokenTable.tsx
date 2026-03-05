"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Token } from "@/types";

interface Props {
  doctorId: number;
  refreshTick: number;
}

export default function TokenTable({ doctorId, refreshTick }: Props) {
  const [tokens, setTokens] = useState<Token[]>([]);

  useEffect(() => {
    api.getTodayTokens(doctorId).then((data) => setTokens(data as Token[]));
  }, [doctorId, refreshTick]);

  if (!tokens.length) {
    return <p className="text-gray-400 text-sm mt-3">No tokens issued today.</p>;
  }

  return (
    <div className="overflow-x-auto mt-4">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-gray-50 text-gray-500 text-left">
            <th className="px-4 py-2 font-medium">Token #</th>
            <th className="px-4 py-2 font-medium">Phone</th>
            <th className="px-4 py-2 font-medium">Time</th>
            <th className="px-4 py-2 font-medium">Type</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {tokens.map((t) => (
            <tr key={t.id} className="hover:bg-gray-50">
              <td className="px-4 py-2 font-semibold">#{t.token_number}</td>
              <td className="px-4 py-2 text-gray-600">{t.patient_phone || "—"}</td>
              <td className="px-4 py-2 text-gray-500">
                {new Date(t.issued_at).toLocaleTimeString("en-PK", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </td>
              <td className="px-4 py-2">
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    t.token_type === "walkin"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-green-100 text-green-700"
                  }`}
                >
                  {t.token_type === "walkin" ? "Walk-in" : "WhatsApp"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
