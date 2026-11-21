import { describe, expect, it } from "vitest";
import { formatMoney, formatPct, trendTone } from "./format";

describe("formatMoney", () => {
  it("formats INR with Indian grouping", () => {
    expect(formatMoney("500000.00", "INR")).toBe("₹5,00,000.00");
  });
  it("compacts INR to lakh and crore", () => {
    expect(formatMoney("500000", "INR", { compact: true })).toBe("₹5 L");
    expect(formatMoney("12500000", "INR", { compact: true })).toBe("₹1.25 Cr");
    expect(formatMoney("-250000", "INR", { compact: true })).toBe("-₹2.5 L");
  });
  it("handles missing values", () => {
    expect(formatMoney(null, "INR")).toBe("—");
    expect(formatMoney("abc", "INR")).toBe("—");
  });
  it("formats USD", () => {
    expect(formatMoney("1234.5", "USD")).toBe("$1,234.50");
  });
});

describe("formatPct and trendTone", () => {
  it("signs percentages", () => {
    expect(formatPct("18.0")).toBe("+18.0%");
    expect(formatPct("-4.25")).toBe("-4.3%");
    expect(formatPct(null)).toBe("—");
  });
  it("treats lower costs as good", () => {
    expect(trendTone("-10", false)).toBe("good");
    expect(trendTone("10", false)).toBe("bad");
    expect(trendTone("10")).toBe("good");
    expect(trendTone(null)).toBe("neutral");
  });
});
