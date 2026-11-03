import { useState, type FormEvent } from "react";
import { resolveAddress } from "../../api/locations";
import type { AddressMatch } from "../../types/location";
import "../../styles/location.css";

interface AddressResolverProps {
  onResolved: (match: AddressMatch) => void;
  disabled?: boolean;
}

export default function AddressResolver({
  onResolved,
  disabled = false,
}: AddressResolverProps) {
  const [address, setAddress] = useState("");
  const [matches, setMatches] = useState<AddressMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function resolve(e: FormEvent) {
    e.preventDefault();
    const trimmed = address.trim();
    if (!trimmed || trimmed.length > 200) {
      setError("地址须为去除首尾空格后 1–200 个字符。");
      return;
    }
    setLoading(true);
    setError("");
    setMatches([]);
    try {
      const result = await resolveAddress(trimmed);
      setMatches(result);
      if (result.length === 0) setError("未找到匹配地址，请调整后重试。");
    } catch (err) {
      setError(err instanceof Error ? err.message : "地址解析失败，请重试。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="address-resolver">
      <form onSubmit={resolve}>
        <label>
          手动输入地址
          <input
            type="text"
            maxLength={200}
            value={address}
            disabled={disabled || loading}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="例如：北京市朝阳区示例路 18 号"
          />
        </label>
        <button type="submit" disabled={disabled || loading}>
          {loading ? "解析中…" : "解析地址"}
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {matches.length > 0 && (
        <ul className="address-matches" aria-label="地址候选">
          {matches.map((match, index) => (
            <li key={`${match.formatted_address}-${index}`}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onResolved(match)}
              >
                {match.formatted_address}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
