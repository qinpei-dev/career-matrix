"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return <div className="m-8 rounded-2xl border border-[#ebc7c1] bg-[#fff4f2] p-6">
    <h2 className="font-bold text-[#9d4035]">定制简历页面加载失败</h2>
    <p className="mt-2 text-sm text-[#82554f]">{error.message}</p>
    <button onClick={reset} className="mt-4 rounded-xl bg-[#315d4f] px-4 py-2 text-sm font-bold text-white">
      重试
    </button>
  </div>;
}
