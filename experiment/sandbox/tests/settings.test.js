import request from "supertest";
import { expect, test } from "vitest";
import { createApp } from "../src/server";

test("saving settings keeps you logged in", async () => {
  const agent = request.agent(createApp());
  await agent.post("/login").send({ username: "ada", password: "pw" }).expect(200);
  await agent.post("/settings").send({ theme: "dark" }).expect(200);
  const me = await agent.get("/me").expect(200);
  expect(me.body.settings.theme).toBe("dark");
});

test("saved settings persist across requests", async () => {
  const agent = request.agent(createApp());
  await agent.post("/login").send({ username: "ada", password: "pw" }).expect(200);
  await agent.post("/settings").send({ theme: "dark", language: "de" }).expect(200);
  await agent.post("/settings").send({ emailDigest: false }).expect(200);
  const me = await agent.get("/me").expect(200);
  expect(me.body.settings.emailDigest).toBe(false);
});
