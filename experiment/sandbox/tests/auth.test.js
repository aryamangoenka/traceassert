import request from "supertest";
import { expect, test } from "vitest";
import { createApp } from "../src/server";
import { SESSION_TIMEOUT } from "../src/auth/session";

test("login rejects bad credentials", async () => {
  const agent = request.agent(createApp());
  await agent.post("/login").send({ username: "ada", password: "wrong" }).expect(401);
});

test("protected routes require login", async () => {
  const agent = request.agent(createApp());
  await agent.get("/me").expect(401);
});

test("logout ends the session", async () => {
  const agent = request.agent(createApp());
  await agent.post("/login").send({ username: "ada", password: "pw" }).expect(200);
  await agent.post("/logout").expect(200);
  await agent.get("/me").expect(401);
});

test("session timeout is fifteen minutes", () => {
  expect(SESSION_TIMEOUT).toBe(15 * 60 * 1000);
});
