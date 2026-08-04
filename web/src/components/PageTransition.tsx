import type { ReactNode } from "react";
import { useLocation } from "@tanstack/react-router";

interface PageTransitionProps {
  children: ReactNode;
}

export default function PageTransition({ children }: PageTransitionProps) {
  const location = useLocation();

  return <div key={location.pathname}>{children}</div>;
}
