import { expect, test } from "vitest";
import { pickSettings } from "../src/settings/validate";

test("unknown keys are dropped", () => {
  expect(pickSettings({ theme: "dark", isAdmin: true })).toEqual({ theme: "dark" });
});

test("bad theme is rejected", () => {
  expect(() => pickSettings({ theme: "neon" })).toThrow(/theme must be one of/);
});

test("emailDigest must be boolean", () => {
  expect(() => pickSettings({ emailDigest: "yes" })).toThrow(/boolean/);
});
