"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";
import {
  api,
  ApiError,
  type Profile,
  type ProfileDraft,
  type ProfilePayload,
} from "@/lib/api";

const emptyFields: ProfilePayload = {
  name: "",
  target_role: null,
  summary: null,
  skills: [],
};

export function ProfileOnboarding({ documentId }: { documentId?: string }) {
  const [existingProfile, setExistingProfile] = useState<Profile | null>(null);
  const [draft, setDraft] = useState<ProfileDraft | null>(null);
  const [fields, setFields] = useState<ProfilePayload>(emptyFields);
  const [skillsText, setSkillsText] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");
      try {
        let currentProfile: Profile | null = null;
        try {
          currentProfile = await api.getMyProfile();
        } catch (caught) {
          if (!(caught instanceof ApiError && caught.status === 404)) throw caught;
        }

        if (!active) return;
        setExistingProfile(currentProfile);

        const currentFields: ProfilePayload = currentProfile
          ? {
              name: currentProfile.name,
              target_role: currentProfile.target_role,
              summary: currentProfile.summary,
              skills: currentProfile.skills,
            }
          : emptyFields;
        setFields(currentFields);
        setSkillsText(currentFields.skills.join(", "));

        let nextDraft: ProfileDraft | null = null;
        if (documentId) {
          try {
            nextDraft = await api.draftProfileFromDocument(documentId);
          } catch (caught) {
            if (active) {
              setError(caught instanceof Error ? caught.message : "候选人资料草稿加载失败");
            }
            return;
          }
        }
        if (!active) return;

        setDraft(nextDraft);
        const nextFields: ProfilePayload = {
          name: nextDraft?.name?.value ?? currentFields.name,
          target_role: nextDraft?.target_role?.value ?? currentFields.target_role,
          summary: nextDraft?.summary?.value ?? currentFields.summary,
          skills: nextDraft?.skills.length
            ? nextDraft.skills.map((skill) => skill.value)
            : currentFields.skills,
        };
        setFields(nextFields);
        setSkillsText(nextFields.skills.join(", "));
      } catch (caught) {
        if (active) {
          setError(caught instanceof Error ? caught.message : "候选人资料草稿加载失败");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void load();
    return () => { active = false; };
  }, [documentId]);

  async function confirm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError("");
    setSaved(false);

    const payload: ProfilePayload = {
      name: fields.name.trim(),
      target_role: fields.target_role?.trim() || null,
      summary: fields.summary?.trim() || null,
      skills: [...new Set(skillsText.split(/[,，\n]/).map((skill) => skill.trim()).filter(Boolean))],
    };

    if (
      existingProfile
      && !payload.name
      && !payload.target_role
      && !payload.summary
      && payload.skills.length === 0
    ) {
      setError("已有候选人资料不能全部为空");
      setSaving(false);
      return;
    }

    try {
      const profile = existingProfile
        ? await api.updateMyProfile(payload)
        : await api.createProfile(payload);
      setExistingProfile(profile);
      setFields({
        name: profile.name,
        target_role: profile.target_role,
        summary: profile.summary,
        skills: profile.skills,
      });
      setSkillsText(profile.skills.join(", "));
      setSaved(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "候选人资料保存失败");
    } finally {
      setSaving(false);
    }
  }

  function editFields(nextFields: ProfilePayload) {
    setFields(nextFields);
    setSaved(false);
  }

  if (loading) {
    return <section className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-8 text-sm text-[#707a76]" role="status">
      正在加载候选人资料并生成草稿…
    </section>;
  }

  if (error && !draft && !existingProfile && documentId) {
    return <section className="rounded-2xl border border-[#efd4ca] bg-[#fff5f1] p-6">
      <p role="alert" className="text-sm text-[#9a4b35]">{error}</p>
      <Link href="/resumes" className="mt-4 inline-flex text-xs font-bold text-[#315d4f]">返回简历管理</Link>
    </section>;
  }

  const evidence = [
    ...(draft?.name ? [{ label: "姓名", excerpt: draft.name.evidence.excerpt }] : []),
    ...(draft?.target_role ? [{ label: "目标岗位", excerpt: draft.target_role.evidence.excerpt }] : []),
    ...(draft?.summary?.evidence.map((item) => ({ label: "个人简介", excerpt: item.excerpt })) ?? []),
    ...(draft?.skills.map((item) => ({ label: `技能：${item.value}`, excerpt: item.evidence.excerpt })) ?? []),
  ];

  return <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(280px,.75fr)]">
    <form onSubmit={confirm} className="soft-shadow rounded-2xl border border-[#e4e9e2] bg-white p-5 md:p-7">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-bold">{documentId ? "确认 Profile Draft" : "编辑候选人资料"}</h2>
          <p className="mt-1 text-xs leading-5 text-[#7f8985]">
            {existingProfile ? "确认后将更新现有 CandidateProfile。" : "确认前不会创建 CandidateProfile。"}
          </p>
        </div>
        <span className="rounded-full bg-[#edf2eb] px-3 py-1.5 text-[10px] font-bold text-[#466157]">
          {existingProfile ? "已有 Profile" : "尚未保存"}
        </span>
      </div>

      {saved && <p role="status" className="mt-5 rounded-xl bg-[#e9f5ec] px-4 py-3 text-sm text-[#2e654c]">候选人资料已保存。</p>}
      {error && <p role="alert" className="mt-5 rounded-xl bg-[#fff1ec] px-4 py-3 text-sm text-[#a44d35]">{error}</p>}

      <div className="mt-6 grid gap-5 md:grid-cols-2">
        <label className="text-xs font-bold text-[#58645f]">姓名
          <input required maxLength={200} value={fields.name} onChange={(event) => editFields({ ...fields, name: event.target.value })} className="mt-2 w-full rounded-xl border border-[#dfe5dd] px-4 py-3 text-sm font-normal" />
        </label>
        <label className="text-xs font-bold text-[#58645f]">目标岗位
          <input maxLength={200} value={fields.target_role ?? ""} onChange={(event) => editFields({ ...fields, target_role: event.target.value || null })} className="mt-2 w-full rounded-xl border border-[#dfe5dd] px-4 py-3 text-sm font-normal" />
        </label>
      </div>

      <label className="mt-5 block text-xs font-bold text-[#58645f]">技能
        <textarea rows={3} value={skillsText} onChange={(event) => { setSkillsText(event.target.value); setSaved(false); }} className="mt-2 w-full rounded-xl border border-[#dfe5dd] px-4 py-3 text-sm font-normal leading-6" placeholder="使用逗号或换行分隔技能" />
      </label>

      <label className="mt-5 block text-xs font-bold text-[#58645f]">个人简介
        <textarea rows={6} value={fields.summary ?? ""} onChange={(event) => editFields({ ...fields, summary: event.target.value || null })} className="mt-2 w-full rounded-xl border border-[#dfe5dd] px-4 py-3 text-sm font-normal leading-6" />
      </label>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button disabled={saving} className="rounded-xl bg-[#234e43] px-5 py-3 text-sm font-bold text-white disabled:cursor-wait disabled:opacity-60">
          {saving ? "保存中…" : existingProfile ? "确认并更新 Profile" : "确认并创建 Profile"}
        </button>
        <Link href="/resumes" className="px-3 py-2 text-xs font-bold text-[#65716c]">返回简历管理</Link>
      </div>
    </form>

    <aside className="soft-shadow h-fit rounded-2xl border border-[#e4e9e2] bg-white p-5 md:p-6">
      <h2 className="text-sm font-bold">草稿来源</h2>
      <p className="mt-1 text-xs leading-5 text-[#7f8985]">简历内容只用于生成建议字段；保存前请逐项确认。</p>
      {documentId && <p className="mt-4 break-all rounded-xl bg-[#f6f8f4] px-3 py-2 text-[10px] text-[#68736e]">Document: {documentId}</p>}
      <div className="mt-4 space-y-3">
        {evidence.map((item, index) => <article key={`${item.label}-${index}`} className="rounded-xl border border-[#e8ece6] p-3">
          <p className="text-[10px] font-bold text-[#466157]">{item.label}</p>
          <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-[#69736f]">{item.excerpt}</p>
        </article>)}
        {evidence.length === 0 && <p className="rounded-xl bg-[#f6f8f4] px-4 py-5 text-xs leading-5 text-[#7f8985]">
          {documentId ? "该简历没有返回可展示的证据字段，请手动补充并确认。" : "从简历管理上传或选择 ready 文档后，可在这里查看草稿依据。"}
        </p>}
      </div>
    </aside>
  </div>;
}
