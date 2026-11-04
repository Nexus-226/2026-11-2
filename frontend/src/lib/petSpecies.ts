import type { PetInput } from "../types/pet";

// Match the backend's Python str.strip(): JS trim() also removes U+FEFF,
// but omits U+0085 and U+001C–U+001F. Preserve all non-whitespace characters.
const speciesWhitespace =
  /[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/;
const speciesEdgeWhitespace = new RegExp(
  `^${speciesWhitespace.source}+|${speciesWhitespace.source}+$`,
  "g",
);

export function normalizeOtherSpecies(value: string | null): string | null {
  return value?.replace(speciesEdgeWhitespace, "") || null;
}

export function validOtherSpecies(value: unknown): value is string | null {
  return (
    value === null ||
    (typeof value === "string" &&
      value === normalizeOtherSpecies(value) &&
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
