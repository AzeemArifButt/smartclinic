"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getAuth } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const auth = getAuth();
    router.replace(auth ? "/dashboard" : "/login");
  }, [router]);
  return null;
}
