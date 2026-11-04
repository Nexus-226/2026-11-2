import type { PetInput } from "../types/pet";

export function normalizeOtherSpecies(value: string | null): string | null {
  return value?.trim() || null;
}

export function validOtherSpecies(value: unknown): value is string | null {
  return (
    value === null ||
    (typeof value === "string" &&
      value === value.trim() &&
      value.length > 0 &&
      [...value].length <= 50)
  );
}

export function normalizePetInput(input: PetInput): PetInput {
  const other_species = normalizeOtherSpecies(input.other_species);
  if (!validOtherSpecies(other_species)) {
    throw new Error("具体物种最多填写 50 个字符。");
  }
  if (input.species !== "other" && other_species !== null) {
    throw new Error("猫狗资料不能填写其他具体物种，请先清空。");
  }
  return { ...input, other_species };
}
