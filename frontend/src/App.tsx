import { FormEvent, useEffect, useState } from "react";
import { api } from "./api";
import type { Pet } from "./types";
import "./styles.css";

type Tab = "pets" | "chat" | "nearby";

export default function App() {
  const [tab, setTab] = useState<Tab>("pets");
  const [pets, setPets] = useState<Pet[]>([]);
  const [selectedPet, setSelectedPet] = useState("pet-demo-001");
  const [status, setStatus] = useState("正在载入演示资料…");
  const [answer, setAnswer] = useState("");
  const [places, setPlaces] = useState<Array<{id: string; name: string; address: string; distance_m: number}>>([]);

  const loadPets = () => api.listPets().then((data) => {
    setPets(data);
    if (data[0] && !data.some((pet) => pet.id === selectedPet)) setSelectedPet(data[0].id);
    setStatus("");
  }).catch((error: Error) => setStatus(`载入失败：${error.message}`));

  useEffect(() => {
    void loadPets();
  }, []);

  async function addPet(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setStatus("正在保存…");
    try {
      const pet = await api.createPet({user_id: "demo-user", name: String(data.get("name")), species: String(data.get("species")), breed: String(data.get("breed")) || null, age_years: data.get("age") ? Number(data.get("age")) : null, health_notes: String(data.get("notes")) || null});
      setSelectedPet(pet.id);
      form.reset();
      await loadPets();
    } catch (error) { setStatus(`保存失败：${(error as Error).message}`); }
  }

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const message = String(new FormData(form).get("message"));
    setStatus("Pet Agent 正在整理资料…");
    try { const response = await api.chat(message, selectedPet); setAnswer(response.reply); setStatus(""); form.reset(); }
    catch (error) { setStatus(`对话失败：${(error as Error).message}`); }
  }

  async function findNearby(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const address = String(new FormData(event.currentTarget).get("address"));
    setStatus("正在使用手动地址查找模拟地点…");
    try { const response = await api.nearbyByAddress(address); setPlaces(response.places); setStatus("P1 当前使用明确标记的模拟地图数据。"); }
    catch (error) { setStatus(`查找失败：${(error as Error).message}`); }
  }

  return <main>
    <header><div><span className="eyebrow">3-day hackathon</span><h1>Pet Agent</h1></div><p>先把宠物资料与个性化对话做好，再去探索附近服务。</p></header>
    <nav aria-label="主功能"><button className={tab === "pets" ? "active" : ""} onClick={() => setTab("pets")}>宠物资料 · P0</button><button className={tab === "chat" ? "active" : ""} onClick={() => setTab("chat")}>个性化聊天 · P0</button><button className={tab === "nearby" ? "active" : ""} onClick={() => setTab("nearby")}>附近服务 · P1</button></nav>
    {status && <p className="status" role="status">{status}</p>}
    {tab === "pets" && <section className="grid"><article><h2>演示宠物</h2>{pets.map((pet) => <button className="pet" key={pet.id} onClick={() => setSelectedPet(pet.id)}><strong>{pet.name}</strong><span>{pet.species} · {pet.age_years ?? "?"} 岁</span><small>{pet.health_notes || "暂无健康备注"}</small></button>)}</article><form onSubmit={addPet}><h2>新建宠物</h2><label>名字<input name="name" required /></label><label>物种<input name="species" required placeholder="cat / dog" /></label><label>品种<input name="breed" /></label><label>年龄<input name="age" type="number" min="0" step="0.5" /></label><label>健康备注<textarea name="notes" /></label><button type="submit">保存资料</button></form></section>}
    {tab === "chat" && <section><h2>向 Agent 提问</h2><p>当前宠物：<select value={selectedPet} onChange={(event) => setSelectedPet(event.target.value)}>{pets.map((pet) => <option key={pet.id} value={pet.id}>{pet.name}</option>)}</select></p><form onSubmit={sendMessage} className="chat"><textarea name="message" required placeholder="例如：它最近不吃东西，需要注意什么？" /><button type="submit">发送</button></form>{answer && <div className="answer"><span className="eyebrow">Agent reply</span><p>{answer}</p></div>}</section>}
    {tab === "nearby" && <section><h2>附近宠物服务</h2><p>若浏览器定位被拒绝，请手动输入城市或地址。当前骨架返回模拟数据，真实高德接入不得阻塞 P0。</p><form onSubmit={findNearby} className="inline"><input name="address" required placeholder="上海市人民广场" /><button type="submit">按地址查找</button></form><div className="places">{places.map((place) => <article key={place.id}><strong>{place.name}</strong><span>{place.distance_m} m</span><p>{place.address}</p></article>)}</div></section>}
  </main>;
}
