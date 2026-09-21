// held out from the sandbox on purpose: a shipped bug is a bug the app's own
// suite didn't catch, so the sandbox suite passes with the bug present. the
// runner copies this file in at scoring time, after the diff is captured.
// the agent never sees it. it checks the actual user symptom: saving
// settings must not log you out.

import request from "supertest";
import { expect, test } from "vitest";
import { createApp } from "../src/server";

test("HELDOUT: saving settings keeps you logged in and persists them", async () => {
  const agent = request.agent(createApp());
  await agent.post("/login").send({ username: "ada", password: "pw" }).expect(200);
  await agent.post("/settings").send({ theme: "dark" }).expect(200);
  const me = await agent.get("/me").expect(200);
  expect(me.body.settings.theme).toBe("dark");
});
