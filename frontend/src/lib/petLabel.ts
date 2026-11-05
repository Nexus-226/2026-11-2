import type { Pet } from "../types/pet";
export function petSpeciesLabel(pet: Pet) {
  return pet.species === "cat"
    ? "猫咪"
    : pet.species === "dog"
      ? "狗狗"
      : pet.other_species
        ? `其他（${pet.other_species}）`
        : "其他";
}
