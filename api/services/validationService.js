const net = require("net");
const config = require("../../config");
const { ALLOWED_MODES } = require("../models/job.model");

const BLOCKED_LITERAL_HOSTS = new Set(["localhost", "0.0.0.0", "::1"]);

function isPrivateIpv4(hostname) {
  const segments = hostname.split(".").map((part) => Number.parseInt(part, 10));
  if (segments.length !== 4 || segments.some((part) => Number.isNaN(part) || part < 0 || part > 255)) {
    return false;
  }

  const [a, b] = segments;

  if (a === 10) {
    return true;
  }
  if (a === 127) {
    return true;
  }
  if (a === 192 && b === 168) {
    return true;
  }
  if (a === 172 && b >= 16 && b <= 31) {
    return true;
  }

  return false;
}

function isBlockedHost(hostname) {
  const host = String(hostname || "").trim().toLowerCase();
  if (!host) {
    return true;
  }

  if (BLOCKED_LITERAL_HOSTS.has(host)) {
    return true;
  }

  if (host.endsWith(".local") || host.endsWith(".internal")) {
    return true;
  }

  const ipVersion = net.isIP(host);
  if (ipVersion === 4 && isPrivateIpv4(host)) {
    return true;
  }

  if (ipVersion === 6 && host === "::1") {
    return true;
  }

  return false;
}

function normalizeMode(mode) {
  if (mode === undefined || mode === null || String(mode).trim() === "") {
    return config.DEFAULT_AUDIT_MODE;
  }

  return String(mode).trim().toLowerCase();
}

function normalizeUrl(rawUrl) {
  const parsed = new URL(rawUrl);

  if (parsed.pathname && parsed.pathname.length > 1) {
    parsed.pathname = parsed.pathname.replace(/\/+$/, "");
  }

  const isRootPath = !parsed.pathname || parsed.pathname === "/";
  const rootPath = isRootPath ? "" : parsed.pathname;

  return `${parsed.origin}${rootPath}${parsed.search}`;
}

function validateAuditRequest(body) {
  const errors = [];

  if (!body || body.url === undefined || body.url === null || String(body.url).trim() === "") {
    errors.push({ message: "URL is required", code: "MISSING_URL" });
    return { valid: false, errors, normalized: null };
  }

  if (typeof body.url !== "string") {
    errors.push({ message: "URL must be a string", code: "URL_NOT_STRING" });
    return { valid: false, errors, normalized: null };
  }

  const urlValue = body.url.trim();

  if (urlValue.length > config.MAX_URL_LENGTH) {
    errors.push({ message: `URL exceeds max length of ${config.MAX_URL_LENGTH}`, code: "URL_TOO_LONG" });
    return { valid: false, errors, normalized: null };
  }

  let parsed;
  try {
    parsed = new URL(urlValue);
  } catch (error) {
    errors.push({ message: "URL is malformed", code: "MALFORMED_URL" });
    return { valid: false, errors, normalized: null };
  }

  const protocol = String(parsed.protocol || "").toLowerCase();
  if (protocol !== "http:" && protocol !== "https:") {
    errors.push({ message: "Only http and https URLs are allowed", code: "INVALID_PROTOCOL" });
    return { valid: false, errors, normalized: null };
  }

  if (isBlockedHost(parsed.hostname)) {
    errors.push({ message: "Target host is blocked for security reasons", code: "BLOCKED_HOST" });
    return { valid: false, errors, normalized: null };
  }

  const mode = normalizeMode(body.mode);
  if (!ALLOWED_MODES.includes(mode)) {
    errors.push({
      message: `Mode must be one of: ${ALLOWED_MODES.join(", ")}`,
      code: "INVALID_MODE",
    });
    return { valid: false, errors, normalized: null };
  }

  const normalized = {
    url: normalizeUrl(urlValue),
    mode,
  };

  return {
    valid: true,
    errors,
    normalized,
  };
}

module.exports = {
  validateAuditRequest,
  normalizeMode,
  normalizeUrl,
  isBlockedHost,
};
