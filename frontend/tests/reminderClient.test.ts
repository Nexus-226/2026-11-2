// @vitest-environment jsdom
import { beforeEach, expect, it } from "vitest";
import { reminderClient } from "../src/api/reminders";

const key = "pet-agent.demo.reminders.v1";

const staleItem = {
  id: "a",
  pet_id: null,
  title: "旧提醒",
  due_on: "2000-01-01",
  source_record_id: null,
  status: "pending",
  due_group: "today",
  created_at: "2000-01-01T00:00:00Z",
  updated_at: "2000-01-01T00:00:00Z",
};

beforeEach(() => {
  localStorage.clear();
});

it("recomputes due_group on read in demo mode", async () => {
  localStorage.setItem(key, JSON.stringify([staleItem]));
  const items = await reminderClient.list({});
  expect(items[0].due_group).toBe("overdue");
});
