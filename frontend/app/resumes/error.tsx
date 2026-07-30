"use client";

export default function ResumesError({ reset }: { reset: () => void }) {
  return <main className="mx-auto max-w-3xl px-5 py-20 text-center">
    <h1 className="text-xl font-bold">无法加载简历文档</h1>
    <p className="mt-3 text-sm text-[#65716c]">请确认后端服务可用，然后重试。</p>
    <button type="button" onClick={reset} className="mt-5 rounded-xl bg-[#234e43] px-4 py-2.5 text-xs font-bold text-white">重新加载</button>
  </main>;
}
