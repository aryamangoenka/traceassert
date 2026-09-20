import request from "supertest";
import { expect, test } from "vitest";
import { createApp } from "../src/server";

test("notes require login", async () => {
  const agent = request.agent(createApp());
  await agent.get("/notes").expect(401);
});

test("create and list notes", async () => {
  const agent = request.agent(createApp());
  await agent.post("/login").send({ username: "grace", password: "pw2" }).expect(200);
  await agent.post("/notes").send({ text: "buy milk" }).expect(201);
  const list = await agent.get("/notes").expect(200);
  expect(list.body.notes.some((n) => n.text === "buy milk")).toBe(true);
});

test("empty notes are rejected", async () => {
  const agent = request.agent(createApp());
  await agent.post("/login").send({ username: "grace", password: "pw2" }).expect(200);
  await agent.post("/notes").send({ text: "   " }).expect(400);
});
