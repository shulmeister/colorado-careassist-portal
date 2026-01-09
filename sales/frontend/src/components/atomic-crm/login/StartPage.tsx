import { useQuery } from "@tanstack/react-query";
import { useDataProvider } from "ra-core";
import { Navigate } from "react-router-dom";
import { LoginPage } from "@/components/admin/login-page";

import type { CrmDataProvider } from "../providers/types";
import { LoginSkeleton } from "./LoginSkeleton";

const checkPortalSession = async () => {
  try {
    const res = await fetch("/auth/me", { credentials: "include" });
    if (!res.ok) return false;
    const body = await res.json();
    return !!body?.user?.email;
  } catch {
    return false;
  }
};

export const StartPage = () => {
  const dataProvider = useDataProvider<CrmDataProvider>();
  const {
    data: isInitialized,
    error,
    isPending,
  } = useQuery({
    queryKey: ["init"],
    queryFn: async () => dataProvider.isInitialized(),
  });
  const {
    data: hasPortalSession,
    isPending: checkingPortal,
  } = useQuery({
    queryKey: ["portal-session"],
    queryFn: checkPortalSession,
  });

  if (isPending || checkingPortal) return <LoginSkeleton />;
  if (hasPortalSession) return <Navigate to="/" replace />;
  if (error) return <LoginPage />;
  if (isInitialized) return <LoginPage />;

  return <Navigate to="/sign-up" />;
};
