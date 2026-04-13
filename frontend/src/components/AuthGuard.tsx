"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore, type AuthUser } from "@/lib/auth";

/**
 * AuthGuard — wraps dashboard layout to enforce authentication.
 *
 * While loading it shows a skeleton.  If there's no valid session it
 * redirects to /login.  Optionally restricts to specific roles.
 */
export function AuthGuard({
  children,
  requiredRoles,
}: {
  children: React.ReactNode;
  requiredRoles?: AuthUser["role"][];
}) {
  const router = useRouter();
  const { user, accessToken, fetchUser } = useAuthStore();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    async function check() {
      if (!accessToken) {
        router.replace("/login");
        return;
      }
      if (!user) {
        await fetchUser();
      }
      setChecking(false);
    }
    check();
  }, [accessToken, user, fetchUser, router]);

  // Still verifying session
  if (checking || (!user && accessToken)) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-950">
        <div className="flex flex-col items-center gap-4">
          <svg className="animate-spin h-8 w-8 text-blue-400" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p className="text-slate-400 text-sm">Verifying session...</p>
        </div>
      </div>
    );
  }

  // No valid session
  if (!user) {
    return null; // redirect happens in useEffect
  }

  // Role check
  if (requiredRoles && !requiredRoles.includes(user.role)) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-950">
        <div className="text-center">
          <h2 className="text-xl font-semibold text-white mb-2">Access Denied</h2>
          <p className="text-slate-400">
            You need {requiredRoles.join(" or ")} access for this page.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
