"use client";
import { useState } from "react";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import type { QueueState } from "@/types";
import TokenTable from "./TokenTable";
import { ArrowRight, RotateCcw, UserPlus } from "lucide-react";

interface Props {
  state: QueueState;
  onRefresh: () => void;
}

export default function QueueTab({ state, onRefresh }: Props) {
  const [refreshTick, setRefreshTick] = useState(0);

  async function handleNext() {
    try {
      await api.nextToken(state.doctor_id);
      toast.success(`Now serving #${state.current_serving + 1}`);
      onRefresh();
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  }

  async function handleReset() {
    if (!confirm("Reset queue for this doctor? This clears today's count.")) return;
    try {
      await api.resetQueue(state.doctor_id);
      toast.success("Queue reset");
      onRefresh();
      setRefreshTick((t) => t + 1);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  }

  async function handleWalkin() {
    try {
      const token = await api.issueWalkin(state.doctor_id) as { token_number: number };
      toast.success(`Walk-in token #${token.token_number} issued`);
      onRefresh();
      setRefreshTick((t) => t + 1);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <div className="p-6">
      {/* Stats row */}
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-brand-600 rounded-2xl p-6 text-white text-center">
          <p className="text-sm font-medium opacity-80 mb-1">Now Serving</p>
          <p className="text-6xl font-bold">#{state.current_serving}</p>
        </div>
        <div className="bg-gray-100 rounded-2xl p-6 text-center">
          <p className="text-sm font-medium text-gray-500 mb-1">Issued Today</p>
          <p className="text-6xl font-bold text-gray-800">{state.total_issued_today}</p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3 mb-6">
        <button
          onClick={handleNext}
          className="flex items-center gap-2 bg-brand-600 hover:bg-brand-700 text-white font-semibold px-6 py-3 rounded-xl transition"
        >
          <ArrowRight size={18} />
          NEXT
        </button>

        <button
          onClick={handleWalkin}
          className="flex items-center gap-2 bg-amber-500 hover:bg-amber-600 text-white font-semibold px-5 py-3 rounded-xl transition"
        >
          <UserPlus size={18} />
          Issue Walk-in Token
        </button>

        <button
          onClick={handleReset}
          className="flex items-center gap-2 bg-gray-200 hover:bg-gray-300 text-gray-700 font-semibold px-5 py-3 rounded-xl transition"
        >
          <RotateCcw size={18} />
          Reset Day
        </button>
      </div>

      {/* Token list */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-100">
          <h3 className="text-sm font-semibold text-gray-600">Today&apos;s Tokens</h3>
        </div>
        <TokenTable doctorId={state.doctor_id} refreshTick={refreshTick} />
      </div>
    </div>
  );
}
