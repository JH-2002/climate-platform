import { describe, expect, it } from "vitest";
import { originOf, securityHeaders } from "@/lib/security-headers.mjs";

const MAPS = ["https://tiles.openfreemap.org/styles/liberty", "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"];

function csp(dev: boolean): string {
  return securityHeaders({ dev, mapUrls: MAPS }).find((h) => h.key === "Content-Security-Policy")!.value;
}

describe("cabeçalhos de segurança (FR-170, BR-171)", () => {
  it("produção: sem eval, mapas liberados, quadros e objetos fechados", () => {
    const policy = csp(false);
    expect(policy).toContain("script-src 'self' 'unsafe-inline';");
    expect(policy).not.toContain("unsafe-eval");
    expect(policy).toContain("connect-src 'self' https://tiles.openfreemap.org https://s3.amazonaws.com");
    expect(policy).toContain("img-src 'self' data: blob: https://tiles.openfreemap.org https://s3.amazonaws.com");
    expect(policy).toContain("worker-src 'self' blob:");
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("object-src 'none'");
    expect(policy).toContain("upgrade-insecure-requests");
  });

  it("desenvolvimento: eval e websocket da recarga", () => {
    const policy = csp(true);
    expect(policy).toContain("'unsafe-eval'");
    expect(policy).toContain("ws: wss:");
    expect(policy).not.toContain("upgrade-insecure-requests");
  });

  it("demais cabeçalhos e origens", () => {
    const keys = securityHeaders({ dev: false, mapUrls: [] }).map((h) => h.key);
    expect(keys).toEqual([
      "Content-Security-Policy",
      "X-Content-Type-Options",
      "Referrer-Policy",
      "X-Frame-Options",
      "Permissions-Policy",
    ]);
    expect(originOf("https://a.b/c/{z}/{x}/{y}.png")).toBe("https://a.b");
    expect(originOf("javascript:alert(1)")).toBeNull();
    expect(originOf(undefined)).toBeNull();
    expect(csp(false)).toContain("connect-src 'self' https://tiles.openfreemap.org");
  });
});
