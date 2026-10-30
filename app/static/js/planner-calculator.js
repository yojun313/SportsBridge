/* Calendar-month arithmetic only; never reads card balances or payment history. */
(function (root) {
  function monthIndex(value, label) {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(value || "")) throw new Error(`${label}을 선택해 주세요.`);
    const [year, month] = value.split("-").map(Number);
    if (year < 1900 || year > 2100) throw new Error(`${label}은 1900~2100년 범위로 입력해 주세요.`);
    return year * 12 + month - 1;
  }
  function integer(value, min, max, label) {
    if (value == null || String(value).trim() === "") throw new Error(`${label}를 입력해 주세요.`);
    const number = Number(value);
    if (!Number.isSafeInteger(number) || number < min || number > max) throw new Error(`${label}는 ${min.toLocaleString("ko-KR")}~${max.toLocaleString("ko-KR")} 범위의 정수로 입력해 주세요.`);
    return number;
  }
  function calculate(input) {
    const start = monthIndex(input.start, "지원 시작 월");
    const reference = monthIndex(input.reference, "계산 기준 월");
    const months = integer(input.months, 1, 12, "지원 개월 수");
    const cap = integer(input.cap, 0, 5000000, "월 지원 한도");
    const price = integer(input.price, 0, 5000000, "월 수강료");
    const end = start + months - 1;
    const remaining = Math.max(0, end - Math.max(start, reference) + 1);
    const elapsed = months - remaining;
    const monthlySupport = Math.min(price, cap), monthlyOwn = Math.max(0, price - cap);
    const endMonth = `${Math.floor(end / 12)}-${String(end % 12 + 1).padStart(2, "0")}`;
    return {
      remaining, elapsed, endMonth, status: reference < start ? "before" : reference > end ? "ended" : "active",
      monthlySupport, monthlyOwn, monthlyUnused: Math.max(0, cap - price),
      totalSupport: remaining * monthlySupport, totalOwn: remaining * monthlyOwn,
      totalPrice: remaining * price, remainingCap: remaining * cap,
    };
  }
  root.PlannerCalculator = { calculate };
  if (typeof module !== "undefined" && module.exports) module.exports = { calculate };
})(typeof window !== "undefined" ? window : globalThis);
