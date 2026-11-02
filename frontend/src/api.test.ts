import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("API client", () => {
  it("reserves the fixed demo user when listing pets", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [],
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.listPets();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/pets?user_id=demo-user"),
      expect.any(Object),
    );
  });
});
