"use client";

export default function ResumesError({ reset }: { reset: () => void }) {
  return <main className="mx-auto max-w-3xl px-5 py-20 text-center">
    <h1 className="text-xl font-semibold">无法加载简历文档</h1>
    <p className="mt-3 text-sm text-[#64748b]">请确认后端服务可用，然后重试。</p>
    <button type="button" onClick={reset} className="mt-5 rounded-xl bg-[#2563eb] px-4 py-2.5 text-xs font-semibold text-white">重新加载</button>
  </main>;
}
