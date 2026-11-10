"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return <div className="m-8 rounded-xl border border-[#fca5a5] bg-[#f8fafc] p-6">
    <h2 className="font-semibold text-[#b91c1c]">定制简历页面加载失败</h2>
    <p className="mt-2 text-sm text-[#b91c1c]">{error.message}</p>
    <button onClick={reset} className="mt-4 rounded-xl bg-[#2563eb] px-4 py-2 text-sm font-semibold text-white">
      重试
    </button>
  </div>;
}
