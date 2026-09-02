"use client";

import { useState } from "react";
import { register, sendVerificationCode } from "../lib/auth";
import { useTranslations } from "../lib/i18n";

function passwordStrength(password: string): number {
  let strength = 0;
  if (password.length >= 8) strength++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
  if (/[0-9]/.test(password)) strength++;
  if (/[^a-zA-Z0-9]/.test(password)) strength++;
  return strength;
}

export default function RegisterPage() {
  const { t } = useTranslations();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [verificationCode, setVerificationCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const [codeCooldown, setCodeCooldown] = useState(0);
  const [sendingCode, setSendingCode] = useState(false);
  const [verifyStatus, setVerifyStatus] = useState<{ message: string; isError: boolean } | null>(null);

  const strength = passwordStrength(password);
  const showMatch = confirmPassword.length > 0;
  const passwordsMatch = password === confirmPassword && password.length > 0;

  function tickCooldown(seconds: number) {
    setCodeCooldown(seconds);
    const interval = setInterval(() => {
      setCodeCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }

  async function handleSendCode() {
    const trimmed = email.trim();
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setVerifyStatus({ message: t("email_invalid", "Please enter a valid email first"), isError: true });
      return;
    }
    setSendingCode(true);
    try {
      const { body } = await sendVerificationCode(trimmed);
      if (body.success) {
        setVerifyStatus({ message: body.message, isError: false });
        tickCooldown(60);
      } else {
        setVerifyStatus({ message: body.message, isError: true });
        setSendingCode(false);
      }
    } catch {
      setVerifyStatus({ message: t("network_error", "Network error, please try again"), isError: true });
      setSendingCode(false);
    }
    if (codeCooldown === 0) setSendingCode(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFieldErrors({});
    setFormError("");
    setSubmitting(true);
    try {
      const { body } = await register(email, password, confirmPassword, verificationCode);
      if (body.success) {
        window.location.href = body.redirect || "/";
        return;
      }
      if (body.field) {
        setFieldErrors({ [body.field]: body.message ?? "" });
      } else {
        setFormError(body.message ?? "");
      }
    } catch {
      setFormError(t("network_error", "Network error, please try again"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-register" data-theme="light">
      <div className="auth-lang-switch">
        <a href="/set_language/en">EN</a>
        <a href="/set_language/zh-HK">繁中</a>
      </div>

      <div className="auth-container">
        <div className="auth-welcome">
          <div className="auth-logo" role="img" aria-label={t("app_name", "The Listening Tree")}>
            🌳
          </div>
          <h1>{t("join_community", "Join Our Community!")}</h1>
          <p>{t("join_community_desc", "Create your account and start your journey with us. It only takes a moment!")}</p>
          <div style={{ marginTop: 30 }}>
            <blockquote className="bible-verse">
              <p>&quot;My command is this: Love each other as I have loved you.&quot;</p>
              <footer>
                <em>— John 15:12 (NIV)</em>
              </footer>
            </blockquote>
          </div>
        </div>

        <div className="auth-form-section">
          <div className="auth-header">
            <h2>{t("register_title", "Register")}</h2>
            <p className="auth-subtitle">{t("register_desc", "Please fill in your details to get started")}</p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            <div className="form-group mb-3">
              <label htmlFor="email" className="form-label">
                <i className="fas fa-envelope" /> {t("email", "Email")}
              </label>
              <div className="form-control-wrapper">
                <input
                  type="email"
                  id="email"
                  className="form-control"
                  placeholder="your.email@example.com"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
              <div className="field-error">{fieldErrors.email}</div>
            </div>

            <div className="form-group mb-3">
              <label htmlFor="password" className="form-label">
                <i className="fas fa-lock" /> {t("password", "Password")}
              </label>
              <div className="form-control-wrapper">
                <input
                  type={showPassword ? "text" : "password"}
                  id="password"
                  className="form-control"
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="password-toggle"
                  aria-label="Show password"
                  onClick={() => setShowPassword((v) => !v)}
                >
                  <i className={showPassword ? "fas fa-eye-slash" : "fas fa-eye"} />
                </button>
              </div>
              <div className="password-strength">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className={`password-strength-bar${i < strength ? " active" : ""}`} />
                ))}
              </div>
              <div className="password-hint">
                <i className="fas fa-info-circle" /> <span>{t("password_hint", "Use at least 8 characters with letters and numbers")}</span>
              </div>
              <div className="field-error">{fieldErrors.password}</div>
            </div>

            <div className="form-group mb-3">
              <label htmlFor="confirm_password" className="form-label">
                <i className="fas fa-lock" /> {t("confirm_password", "Confirm Password")}
              </label>
              <div className="form-control-wrapper">
                <input
                  type={showConfirmPassword ? "text" : "password"}
                  id="confirm_password"
                  className="form-control"
                  autoComplete="new-password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                />
                <button
                  type="button"
                  className="password-toggle"
                  aria-label="Show password"
                  onClick={() => setShowConfirmPassword((v) => !v)}
                >
                  <i className={showConfirmPassword ? "fas fa-eye-slash" : "fas fa-eye"} />
                </button>
              </div>
              {showMatch && (
                <div className={`password-match show${passwordsMatch ? " match" : " no-match"}`}>
                  <i className={passwordsMatch ? "fas fa-check-circle" : "fas fa-times-circle"} />
                  <span>{passwordsMatch ? t("passwords_match", "Passwords match!") : t("passwords_no_match", "Passwords do not match")}</span>
                </div>
              )}
              <div className="field-error">{fieldErrors.confirm_password}</div>
            </div>

            <div className="form-group mb-3">
              <label htmlFor="verification_code" className="form-label">
                <i className="fas fa-shield-alt" /> {t("verification_code", "Verification Code")}
              </label>
              <div className="form-control-wrapper verify-code-group">
                <input
                  type="text"
                  id="verification_code"
                  className="form-control"
                  inputMode="numeric"
                  maxLength={6}
                  pattern="[0-9]{6}"
                  placeholder="123456"
                  autoComplete="one-time-code"
                  required
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                />
                <button type="button" className="btn" disabled={sendingCode || codeCooldown > 0} onClick={handleSendCode}>
                  {codeCooldown > 0 ? `${codeCooldown}s` : t("send_code", "Send Code")}
                </button>
              </div>
              <div className="field-error">{fieldErrors.verification_code}</div>
              {verifyStatus && (
                <div className={`field-status ${verifyStatus.isError ? "is-error" : "is-success"}`}>{verifyStatus.message}</div>
              )}
            </div>

            {formError && (
              <div className="alert alert-danger" role="alert">
                {formError}
              </div>
            )}

            <button type="submit" className="btn btn-primary w-100" disabled={submitting}>
              {t("register", "Register")}
            </button>
          </form>

          <div className="help-section">
            <h3>
              <i className="fas fa-shield-alt" /> {t("privacy_title", "Your Privacy Matters")}
            </h3>
            <p>{t("privacy_desc", "We protect your personal information and will never share it without your permission.")}</p>
          </div>

          <div className="auth-footer">
            <p className="text-center mt-3">
              {t("already_have_account", "Already have an account?")}{" "}
              <a href="/login" className="form-link">
                {t("login", "Login")} <i className="fas fa-arrow-right" />
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
