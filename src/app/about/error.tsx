"use client";

import { RouteErrorPage } from "@/components/ui/RouteErrorPage";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return <RouteErrorPage error={error} reset={reset} variant="about" />;
}
