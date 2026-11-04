import { useEffect, useState } from "react";
import { recordClient, usingDemoRecords } from "../../api/records";
import { shanghaiToday, type PetRecord } from "../../types/records";
import "../../styles/weight-trend.css";

const day = (date: string) => Date.parse(`${date}T00:00:00Z`);
const format = (value: number) => value.toFixed(2);

export default function WeightTrend({
  petId,
  petName,
  revision,
  onAdd,
  initialRange = "90",
  onRangeChange,
}: {
  petId: string | null;
  petName: string;
  revision: number;
  onAdd: () => void;
  initialRange?: string;
  onRangeChange?: (range: string) => void;
}) {
  const [range, setRange] = useState(initialRange);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{
    loading: boolean;
    error: string;
    items: PetRecord[];
  }>({ loading: true, error: "", items: [] });
  const [selected, setSelected] = useState<string | null>(null);
  const today = shanghaiToday();
  const from =
    range === "all"
      ? undefined
      : new Date(day(today) - (Number(range) - 1) * 86400000)
          .toISOString()
          .slice(0, 10);
  useEffect(() => {
    if (!petId) return;
    let live = true;
    setSelected(null);
    setState({ loading: true, error: "", items: [] });
    recordClient
      .list({
        pet_id: petId,
        record_type: "weight",
        ...(from ? { from_date: from } : {}),
        to_date: today,
      })
      .then((items) => {
        if (live)
          setState({
            loading: false,
            error: "",
            items: items
              .filter(
                (r) =>
                  r.pet_id === petId &&
                  r.record_type === "weight" &&
                  Number.isFinite(r.weight_kg) &&
                  r.weight_kg! > 0 &&
                  r.weight_kg! <= 500 &&
                  r.occurred_on <= today &&
                  (!from || r.occurred_on >= from),
              )
              // Reverse the API's complete order, including timestamp ties.
              .reverse(),
          });
      })
      .catch((e: unknown) => {
        if (live)
          setState({
            loading: false,
            error: e instanceof Error ? e.message : "查询失败，请重试。",
            items: [],
          });
      });
    return () => {
      live = false;
    };
  }, [petId, from, today, revision, attempt]);
  const items = state.items;
  const first = items[0],
    last = items[items.length - 1];
  // Keep every dot, but connect only the last created reading on each date.
  const daily = items.filter(
    (r, i) => r.occurred_on !== items[i + 1]?.occurred_on,
  );
  const active = items.find((r) => r.id === selected) ?? last;
  const values = items.map((r) => r.weight_kg!);
  const low = Math.min(...values),
    high = Math.max(...values);
  const padding = Math.max((high - low) * 0.2, high * 0.03, 0.05);
  const min = Math.max(0, low - padding),
    max = high + padding;
  const x = (r: PetRecord) =>
    first.occurred_on === last.occurred_on
      ? 350
      : 72 +
        ((day(r.occurred_on) - day(first.occurred_on)) /
          (day(last.occurred_on) - day(first.occurred_on))) *
          556;
  const y = (r: PetRecord) => 200 - ((r.weight_kg! - min) / (max - min)) * 160;
  return (
    <section className="records-panel weight-trend" aria-label="体重趋势">
      <div className="weight-heading">
        <div>
          <span className="section-kicker">WEIGHT TREND</span>
          <h2>体重趋势</h2>
          <p>
            {petId ? petName : "请选择具体宠物查看趋势"} ·{" "}
            {usingDemoRecords ? "本地演示数据" : "后端 API 数据"}
          </p>
        </div>
        {petId && (
          <div role="group" aria-label="体重趋势时间范围">
            {[
              ["30", "近30天"],
              ["90", "近90天"],
              ["all", "全部"],
            ].map(([value, label]) => (
              <button
                key={value}
                aria-pressed={range === value}
                onClick={() => {
                  setRange(value);
                  onRangeChange?.(value);
                }}
              >
                {label}
              </button>
            ))}
          </div>
        )}
      </div>
      {!petId ? (
        <p>未关联记录不合并绘图，选择宠物后即可查看。</p>
      ) : state.loading ? (
        <p role="status">正在加载体重趋势…</p>
      ) : state.error ? (
        <p role="alert">
          体重趋势加载失败：{state.error}{" "}
          <button onClick={() => setAttempt((v) => v + 1)}>重试体重趋势</button>
        </p>
      ) : !last ? (
        <div>
          <p>所选时间范围内暂无体重记录。</p>
          <button onClick={onAdd}>添加体重记录</button>
        </div>
      ) : (
        <>
          <div className="weight-summary">
            <div>
              区间最新体重
              <strong>
                {format(last.weight_kg!)} <small>kg</small>
              </strong>
              <span>{last.occurred_on}</span>
            </div>
            <div>
              较区间最早一条称重
              <strong>
                {items.length > 1
                  ? `${last.weight_kg! - first.weight_kg! > 0 ? "+" : ""}${format(last.weight_kg! - first.weight_kg!)} kg`
                  : "—"}
              </strong>
              <span>{items.length} 条称重记录</span>
            </div>
          </div>
          <svg
            viewBox="0 0 700 252"
            role="img"
            aria-label={`${petName}体重趋势，${items.length}条记录，单位公斤`}
          >
            <title>体重按实际日期间隔绘制；同日记录按创建顺序排列</title>
            {[0, 0.5, 1].map((t) => (
              <g key={t}>
                <line
                  x1="72"
                  x2="628"
                  y1={200 - t * 160}
                  y2={200 - t * 160}
                  stroke="#e0e7df"
                />
                <text x="62" y={205 - t * 160} textAnchor="end">
                  {format(min + t * (max - min))}
                </text>
              </g>
            ))}
            <text x="72" y="22">
              kg
            </text>
            {daily.length > 1 && (
              <polyline
                points={daily.map((r) => `${x(r)},${y(r)}`).join(" ")}
                fill="none"
                stroke="#387768"
                strokeWidth="3"
              />
            )}
            {items.map((r) => (
              <circle
                key={r.id}
                cx={x(r)}
                cy={y(r)}
                r={active?.id === r.id ? 7 : 5}
                fill="#387768"
                stroke="white"
                strokeWidth="2"
                tabIndex={0}
                role="button"
                aria-label={`${r.occurred_on}，${r.weight_kg} kg${r.notes ? `，${r.notes}` : ""}`}
                onMouseEnter={() => setSelected(r.id)}
                onFocus={() => setSelected(r.id)}
                onClick={() => setSelected(r.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelected(r.id);
                  }
                }}
              >
                <title>
                  {r.occurred_on} · {r.weight_kg} kg
                </title>
              </circle>
            ))}
            <text x="72" y="235">
              {first.occurred_on}
            </text>
            {first.occurred_on !== last.occurred_on && (
              <text x="628" y="235" textAnchor="end">
                {last.occurred_on}
              </text>
            )}
          </svg>
          <p className="weight-detail" aria-live="polite">
            选中记录：{active.occurred_on} · {format(active.weight_kg!)} kg
            {active.notes ? ` · ${active.notes}` : ""}
          </p>
          {items.length === 1 && <p>再记录一次即可查看变化。</p>}
          <details>
            <summary>查看称重明细（{items.length} 条）</summary>
            <div className="weight-table">
              <table>
                <caption>当前区间全部称重记录；同日多条记录均保留</caption>
                <thead>
                  <tr>
                    <th>日期</th>
                    <th>体重（kg）</th>
                    <th>备注</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => (
                    <tr key={r.id}>
                      <td>{r.occurred_on}</td>
                      <td>{format(r.weight_kg!)}</td>
                      <td>{r.notes ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
          <p className="weight-footnote">
            同日全部称重点保留，折线每天取接口同日列表首条（创建时间相同时按 ID
            决定）；重叠点可查看明细。连线不代表期间每日体重，趋势不用于诊断。
          </p>
        </>
      )}
    </section>
  );
}
