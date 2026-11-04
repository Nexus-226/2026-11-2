// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { PetInput } from "../src/types/pet";

const key = "pet-agent.demo.pets.v1";
const input: PetInput = {
  name: "团团",
  species: "other",
  other_species: "兔",
  breed: null,
  birthday: null,
  notes: null,
};
const pet = {
  id: "pet-1",
  ...input,
  created_at: "2026-11-04T00:00:00Z",
  updated_at: "2026-11-04T00:00:00Z",
};

async function client(mode = "demo") {
  vi.resetModules();
  vi.stubEnv("VITE_PET_DATA_SOURCE", mode);
  return (await import("../src/api/pets")).petClient;
}

beforeEach(() => localStorage.clear());
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("宠物演示数据", () => {
  it("旧档案补 null，修改和重新读取后保留所有原资料", async () => {
    const { other_species: _, ...legacy } = pet;
    localStorage.setItem(key, JSON.stringify([legacy]));
    const pets = await client();
    expect(await pets.list()).toEqual([{ ...legacy, other_species: null }]);
    await pets.update(pet.id, { ...input, other_species: " 仓鼠 " });
    expect(await (await client()).list()).toEqual([
      { ...pet, other_species: "仓鼠", updated_at: expect.any(String) },
    ]);
    expect(JSON.parse(localStorage.getItem(key)!)[0].other_species).toBe(
      "仓鼠",
    );
  });

  it("新建、清空及切换猫狗会持久化明确的 null", async () => {
    const pets = await client();
    const saved = await pets.create({ ...input, other_species: " 兔 " });
    expect(saved.other_species).toBe("兔");
    await pets.update(saved.id, { ...input, other_species: "   " });
    expect((await pets.list())[0].other_species).toBeNull();
    await pets.update(saved.id, {
      ...input,
      species: "cat",
      other_species: null,
    });
    expect((await (await client()).list())[0]).toMatchObject({
      species: "cat",
      other_species: null,
    });
  });

  it("码点计数允许 50 个非 BMP 字符，拒绝 51 个且不破坏已有数据", async () => {
    const pets = await client();
    const saved = await pets.create({
      ...input,
      other_species: ` ${"𠮷".repeat(50)} `,
    });
    const before = localStorage.getItem(key);
    await expect(
      pets.update(saved.id, { ...input, other_species: "𠮷".repeat(51) }),
    ).rejects.toThrow("50");
    expect(localStorage.getItem(key)).toBe(before);
    await expect(
      pets.update(saved.id, { ...input, species: "dog" }),
    ).rejects.toThrow("猫狗");
    expect(localStorage.getItem(key)).toBe(before);
  });

  it("不做 NFC，不折叠内部空白", async () => {
    const pets = await client();
    expect(
      (await pets.create({ ...input, other_species: " e\u0301  兔 " }))
        .other_species,
    ).toBe("e\u0301  兔");
  });

  it("存储写入失败不伪造保存成功", async () => {
    const pets = await client();
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("full");
    });
    await expect(pets.create(input)).rejects.toThrow("无法保存演示数据");
    expect(await pets.list()).toEqual([]);
  });
});

describe("宠物 API Client（模拟 HTTP）", () => {
  it("正确发送创建/更新字段与显式 null，不丢失具体物种", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(pet), { status: 201 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ ...pet, species: "dog", other_species: null }),
        ),
      );
    vi.stubGlobal("fetch", fetch);
    const pets = await client("api");
    expect(
      (await pets.create({ ...input, other_species: " 兔 " })).other_species,
    ).toBe("兔");
    await pets.update(pet.id, {
      ...input,
      species: "dog",
      other_species: null,
    });
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual(input);
    expect(fetch.mock.calls[1][1].method).toBe("PATCH");
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toMatchObject({
      species: "dog",
      other_species: null,
    });
    expect(localStorage.getItem(key)).toBeNull();
  });

  it("读取完整列表，允许具体值和 null", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify([pet, { ...pet, id: "pet-2", other_species: null }]),
          ),
        ),
    );
    expect(await (await client("api")).list()).toEqual([
      pet,
      { ...pet, id: "pet-2", other_species: null },
    ]);
  });

  it.each([undefined, 12, true, "", " 兔 ", "𠮷".repeat(51)])(
    "拒绝无效字段 %s，不把 API 旧响应当成功",
    async (value) => {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(
            new Response(JSON.stringify({ ...pet, other_species: value })),
          ),
      );
      await expect((await client("api")).create(input)).rejects.toThrow(
        "不符合约定",
      );
      expect(localStorage.getItem(key)).toBeNull();
    },
  );

  it("列表拒绝猫狗携带非空具体物种", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify([{ ...pet, species: "cat" }])),
        ),
    );
    await expect((await client("api")).list()).rejects.toThrow("不符合约定");
  });

  it("后端拒绝写入或断网时保留错误，不回退本地演示", async () => {
    localStorage.setItem(key, JSON.stringify([pet]));
    const before = localStorage.getItem(key);
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            error: { code: "VALIDATION_ERROR", message: "后端尚未开放字段" },
          }),
          { status: 422 },
        ),
      )
      .mockRejectedValueOnce(new Error("offline"));
    vi.stubGlobal("fetch", fetch);
    const pets = await client("api");
    await expect(pets.create(input)).rejects.toThrow("后端尚未开放字段");
    await expect(pets.update(pet.id, input)).rejects.toThrow("无法连接后端");
    expect(localStorage.getItem(key)).toBe(before);
  });
});
