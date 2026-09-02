"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "../lib/api";
import { login } from "../lib/auth";
import { fetchConfig } from "../lib/config";
import { useTranslations } from "../lib/i18n";

export default function LoginPage() {
  const { t } = useTranslations();
  const [googleEnabled, setGoogleEnabled] = useState(false);

  useEffect(() => {
    fetchConfig()
      .then((c) => setGoogleEnabled(c.google_enabled))
      .catch(() => {});
  }, []);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const { body } = await login(email, password, rememberMe);
      if (body.success) {
        window.location.href = body.redirect || `${API_BASE}/`;
        return;
      }
      setError(body.message ?? "");
    } catch {
      setError(t("network_error", "Network error, please try again"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page-login" data-theme="light">
      <div className="auth-lang-switch">
        <a href="/set_language/en">EN</a>
        <a href="/set_language/zh-HK">繁中</a>
      </div>

      <div className="auth-container">
        <div className="auth-welcome">
          <div className="auth-logo" role="img" aria-label={t("app_name", "The Listening Tree")}>
            🌳
          </div>
          <h1>{t("welcome_back", "Welcome Back!")}</h1>
          <p>{t("welcome_back_desc", "We're happy to see you again. Sign in to continue your journey with us.")}</p>
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
            <h2>{t("sign_in", "Sign In")}</h2>
            <p className="auth-subtitle">{t("sign_in_desc", "Please enter your details to continue")}</p>
          </div>

          {error && (
            <div className="alert alert-danger" role="alert">
              {error}
            </div>
          )}

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
                  placeholder="example@gmail.com"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
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
                  autoComplete="current-password"
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
              <div className="form-text text-end forgot-password-link">
                <a href={`${API_BASE}/forgot_password`} className="form-link text-decoration-none">
                  {t("forgot_password", "Forgot password?")} <i className="fas fa-arrow-right" />
                </a>
              </div>
            </div>

            <div className="form-group mb-3 form-check">
              <input
                type="checkbox"
                id="remember_me"
                className="form-check-input"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
              />
              <label htmlFor="remember_me" className="form-check-label">
                {t("remember_me", "Keep me signed in for 90 days")}
              </label>
            </div>

            <button type="submit" className="btn btn-primary w-100" disabled={submitting}>
              {t("sign_in", "Sign In")}
            </button>
          </form>

          {googleEnabled && (
            <>
              <div className="auth-divider">
                <span>{t("or_divider", "or")}</span>
              </div>
              <a href={`${API_BASE}/auth/google`} className="btn btn-outline-secondary w-100 google-btn">
                <i className="fa-brands fa-google" /> {t("sign_in_with_google", "Sign in with Google")}
              </a>
            </>
          )}

          <div className="help-section">
            <h3>
              <i className="fas fa-info-circle" /> {t("need_help_title", "Need Help?")}
            </h3>
            <p>{t("need_help_desc", "If you have trouble logging in, please contact our support team. We are here to help you.")}</p>
          </div>

          <div className="auth-footer">
            <p className="text-center mt-3">
              {t("no_account", "Don't have an account?")}{" "}
              <a href="/register" className="form-link">
                {t("register", "Register")} <i className="fas fa-arrow-right" />
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
