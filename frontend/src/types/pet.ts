export type PetSpecies = "dog" | "cat" | "other";

export interface Pet {
  id: string;
  name: string;
  species: PetSpecies;
  other_species: string | null;
  breed: string | null;
  birthday: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export type PetInput = Pick<
  Pet,
  "name" | "species" | "other_species" | "breed" | "birthday" | "notes"
>;

export interface PetClient {
  list(): Promise<Pet[]>;
  create(input: PetInput): Promise<Pet>;
  update(id: string, input: PetInput): Promise<Pet>;
  remove(id: string): Promise<void>;
}
