function loadValidationService() {
  jest.resetModules();
  process.env.MAX_URL_LENGTH = "2048";
  process.env.DEFAULT_AUDIT_MODE = "balanced";
  return require("../../api/services/validationService");
}

describe("validationService", () => {
  test("rejects missing URL", () => {
    const { validateAuditRequest } = loadValidationService();
    const result = validateAuditRequest({ mode: "fast" });

    expect(result.valid).toBe(false);
    expect(result.errors[0].code).toBe("MISSING_URL");
  });

  test("rejects non-http and non-https protocol", () => {
    const { validateAuditRequest } = loadValidationService();
    const result = validateAuditRequest({ url: "ftp://example.com" });

    expect(result.valid).toBe(false);
    expect(result.errors[0].code).toBe("INVALID_PROTOCOL");
  });

  test("rejects localhost", () => {
    const { validateAuditRequest } = loadValidationService();
    const result = validateAuditRequest({ url: "http://localhost:8000" });

    expect(result.valid).toBe(false);
    expect(result.errors[0].code).toBe("BLOCKED_HOST");
  });

  test("rejects private 192.168.x.x host", () => {
    const { validateAuditRequest } = loadValidationService();
    const result = validateAuditRequest({ url: "http://192.168.0.5/page" });

    expect(result.valid).toBe(false);
    expect(result.errors[0].code).toBe("BLOCKED_HOST");
  });

  test("rejects URL exceeding max length", () => {
    const { validateAuditRequest } = loadValidationService();
    const longPath = "a".repeat(2050);
    const result = validateAuditRequest({ url: `https://example.com/${longPath}` });

    expect(result.valid).toBe(false);
    expect(result.errors[0].code).toBe("URL_TOO_LONG");
  });

  test("accepts valid https URL", () => {
    const { validateAuditRequest } = loadValidationService();
    const result = validateAuditRequest({ url: "https://example.com/path/" });

    expect(result.valid).toBe(true);
    expect(result.normalized.url).toBe("https://example.com/path");
  });

  test("normalizes mode casing", () => {
    const { validateAuditRequest } = loadValidationService();
    const result = validateAuditRequest({ url: "https://example.com", mode: "DeEp" });

    expect(result.valid).toBe(true);
    expect(result.normalized.mode).toBe("deep");
  });

  test("defaults mode to balanced", () => {
    const { validateAuditRequest } = loadValidationService();
    const result = validateAuditRequest({ url: "https://example.com" });

    expect(result.valid).toBe(true);
    expect(result.normalized.mode).toBe("balanced");
  });
});
