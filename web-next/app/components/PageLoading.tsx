"use client";

import { useTheme } from "../lib/useTheme";

export default function PageLoading() {
  const { theme } = useTheme();
  return (
    <div
      data-theme={theme}
      style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh" }}
    >
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: "2.5rem" }}>🌳</div>
        <i className="fas fa-spinner fa-spin" style={{ fontSize: "1.5rem", marginTop: 12 }} />
      </div>
    </div>
  );
}
