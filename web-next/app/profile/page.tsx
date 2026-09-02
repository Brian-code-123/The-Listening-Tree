"use client";

import { useState } from "react";
import { API_BASE } from "../lib/api";
import { updateDisplayName, updatePassword } from "../lib/auth";
import { useTranslations } from "../lib/i18n";
import { useRequireAuth } from "../lib/useRequireAuth";

export default function ProfilePage() {
  const { t } = useTranslations();
  const { user, checking } = useRequireAuth();

  // Starts null (not yet edited) so the input can show `user.display_name`
  // once /me resolves, without needing an effect to copy it into state —
  // once the visitor types, this becomes the source of truth instead.
  const [displayNameEdit, setDisplayNameEdit] = useState<string | null>(null);
  const displayName = displayNameEdit ?? user?.display_name ?? "";

  const [nameStatus, setNameStatus] = useState<{ message: string; isError: boolean } | null>(null);
  const [nameError, setNameError] = useState("");
  const [savingName, setSavingName] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [passwordErrors, setPasswordErrors] = useState<Record<string, string>>({});
  const [passwordStatus, setPasswordStatus] = useState<{ message: string; isError: boolean } | null>(null);
  const [savingPassword, setSavingPassword] = useState(false);

  async function handleNameSubmit(e: React.FormEvent) {
    e.preventDefault();
    setNameError("");
    setNameStatus(null);
    setSavingName(true);
    try {
      const { body } = await updateDisplayName(displayName);
      if (body.success) {
        setNameStatus({ message: body.message ?? "", isError: false });
      } else if (body.field) {
        setNameError(body.message ?? "");
      } else {
        setNameStatus({ message: body.message || t("error_generic", "Something went wrong."), isError: true });
      }
    } catch {
      setNameStatus({ message: t("network_error", "Network error, please try again"), isError: true });
    } finally {
      setSavingName(false);
    }
  }

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPasswordErrors({});
    setPasswordStatus(null);
    setSavingPassword(true);
    try {
      const { body } = await updatePassword(currentPassword, newPassword, confirmNewPassword);
      if (body.success) {
        setPasswordStatus({ message: body.message ?? "", isError: false });
        setCurrentPassword("");
        setNewPassword("");
        setConfirmNewPassword("");
      } else if (body.field) {
        setPasswordErrors({ [body.field]: body.message ?? "" });
      } else {
        setPasswordStatus({ message: body.message || t("error_generic", "Something went wrong."), isError: true });
      }
    } catch {
      setPasswordStatus({ message: t("network_error", "Network error, please try again"), isError: true });
    } finally {
      setSavingPassword(false);
    }
  }

  if (checking || !user) {
    return null;
  }

  const avatarLetter = (user.display_name || user.email || "?").charAt(0).toUpperCase();

  return (
    <div className="page-profile" data-theme="light">
      <div className="container-fluid">
        <div className="profile-hero" role="banner">
          <div className="profile-avatar" aria-hidden="true">
            {avatarLetter}
          </div>
          <div className="profile-hero-text">
            <h1>{t("profile_title", "My Profile")}</h1>
            <p>{user.display_name || user.email}</p>
          </div>
        </div>

        <nav className="nav-bar" role="navigation" aria-label={t("main_navigation", "Main navigation")}>
          <div className="lang-switch" role="group" aria-label={t("language_selector", "Language selector")}>
            <a href="/set_language/en" className="lang-btn" aria-label="English">
              EN
            </a>
            <a href="/set_language/zh-HK" className="lang-btn" aria-label="繁體中文">
              繁中
            </a>
          </div>
          <div className="nav-buttons">
            <a href={`${API_BASE}/`} className="btn-accessible btn-secondary-accessible" aria-label={t("normal_mode", "Back to chat")}>
              <span aria-hidden="true">
                <i className="fas fa-comments" />
              </span>
              <span>{t("app_name", "The Listening Tree")}</span>
            </a>
            <a href={`${API_BASE}/logout`} className="btn-accessible btn-danger-accessible" aria-label={t("logout", "Logout")}>
              <span aria-hidden="true">
                <i className="fas fa-sign-out-alt" />
              </span>
              <span>{t("logout", "Logout")}</span>
            </a>
          </div>
        </nav>

        <main>
          <div className="profile-card">
            <div className="profile-card-head">
              <div className="profile-card-icon" aria-hidden="true">
                <i className="fas fa-id-badge" />
              </div>
              <div>
                <h2>{t("display_name", "Display Name")}</h2>
                <p className="card-desc">{user.email}</p>
              </div>
            </div>
            <form onSubmit={handleNameSubmit}>
              <div className="mb-3">
                <label htmlFor="display_name" className="form-label">
                  {t("display_name", "Display Name")}
                </label>
                <input
                  type="text"
                  id="display_name"
                  className="form-control"
                  maxLength={50}
                  placeholder={t("display_name_placeholder", "What should we call you?")}
                  value={displayName}
                  onChange={(e) => setDisplayNameEdit(e.target.value)}
                />
                <div className="field-error">{nameError}</div>
              </div>
              <button type="submit" className="btn btn-primary" disabled={savingName}>
                {t("save_name", "Save Name")}
              </button>
              {nameStatus && <div className={`form-status ${nameStatus.isError ? "error" : "success"}`}>{nameStatus.message}</div>}
            </form>
          </div>

          <div className="profile-card">
            <div className="profile-card-head">
              <div className="profile-card-icon" aria-hidden="true">
                <i className="fas fa-lock" />
              </div>
              <h2>{t("save_password", "Change Password")}</h2>
            </div>
            <form onSubmit={handlePasswordSubmit}>
              <div className="mb-3">
                <label htmlFor="current_password" className="form-label">
                  {t("current_password", "Current Password")}
                </label>
                <input
                  type="password"
                  id="current_password"
                  className="form-control"
                  autoComplete="current-password"
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                />
                <div className="field-error">{passwordErrors.current_password}</div>
              </div>
              <div className="mb-3">
                <label htmlFor="new_password" className="form-label">
                  {t("new_password", "New Password")}
                </label>
                <input
                  type="password"
                  id="new_password"
                  className="form-control"
                  autoComplete="new-password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
                <div className="field-error">{passwordErrors.new_password}</div>
              </div>
              <div className="mb-3">
                <label htmlFor="confirm_new_password" className="form-label">
                  {t("confirm_new_password", "Confirm New Password")}
                </label>
                <input
                  type="password"
                  id="confirm_new_password"
                  className="form-control"
                  autoComplete="new-password"
                  required
                  value={confirmNewPassword}
                  onChange={(e) => setConfirmNewPassword(e.target.value)}
                />
                <div className="field-error">{passwordErrors.confirm_new_password}</div>
              </div>
              <button type="submit" className="btn btn-primary" disabled={savingPassword}>
                {t("save_password", "Change Password")}
              </button>
              {passwordStatus && (
                <div className={`form-status ${passwordStatus.isError ? "error" : "success"}`}>{passwordStatus.message}</div>
              )}
            </form>
          </div>
        </main>
      </div>
    </div>
  );
}
