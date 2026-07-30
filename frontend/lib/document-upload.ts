import type { ResumeDocumentUpload } from "./documents-api";

export type UploadNotice = {
  message: string;
  tone: "success" | "duplicate";
};

export function documentUploadNotice(result: ResumeDocumentUpload): UploadNotice {
  if (result.is_duplicate || result.upload_status === "duplicate") {
    return {
      message: "该简历版本已存在，无需重新解析",
      tone: "duplicate",
    };
  }
  return {
    message: result.message || "简历上传并解析完成。",
    tone: "success",
  };
}
