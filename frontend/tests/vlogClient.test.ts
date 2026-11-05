import { afterEach, expect, it, vi } from "vitest";
import { vlogClient } from "../src/api/vlogs";

afterEach(() => vi.unstubAllGlobals());

it("sends DELETE to remove a Vlog", async () => {
  const fetchMock = vi
    .fn()
    .mockResolvedValue(new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);

  await expect(vlogClient.remove("vlog-id")).resolves.toBeUndefined();
  expect(fetchMock).toHaveBeenCalledWith(
    "/api/v1/vlogs/vlog-id",
    expect.objectContaining({ method: "DELETE" }),
  );
});
