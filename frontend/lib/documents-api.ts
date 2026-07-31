import {
  API_BASE_URL,
  ApiError,
  apiFetch,
  demoAuthorizationHeader,
} from "./api.ts";

export type DocumentProcessingStatus = "processing" | "ready" | "failed";

export interface ResumeDocument {
  id: string;
  filename: string;
  file_type: "pdf" | "docx";
  status: DocumentProcessingStatus;
  chunk_count: number;
  embedding_status: DocumentProcessingStatus;
  rag_available: boolean;
  can_retry: boolean;
  created_at: string;
}

export interface ResumeDocumentDetail extends ResumeDocument {
  updated_at: string;
}

export interface ResumeDocumentUpload {
  id: string;
  filename: string;
  file_type: "pdf" | "docx";
  status: DocumentProcessingStatus;
  chunk_count?: number;
  created_at: string;
  updated_at: string;
  upload_status: "created" | "duplicate";
  is_duplicate: boolean;
  message: string;
}

export interface DocumentChunk {
  chunk_id: string;
  section: string;
  chunk_index: number;
  content: string;
}

function responseError(xhr: XMLHttpRequest): ApiError {
  let body: unknown;
  try {
    body = JSON.parse(xhr.responseText);
  } catch {
    body = undefined;
  }
  const detail = typeof body === "object" && body !== null && "detail" in body
    ? (body as { detail?: unknown }).detail
    : undefined;
  return new ApiError(
    typeof detail === "string" ? detail : `API request failed (${xhr.status})`,
    xhr.status,
    body,
  );
}

export function uploadDocument(
  file: File,
  onProgress: (percent: number) => void,
): Promise<ResumeDocumentUpload> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/api/v1/documents/upload`);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("Authorization", demoAuthorizationHeader());
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
      }
    };
    xhr.onerror = () => reject(new ApiError("无法连接文档 API", 0));
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(responseError(xhr));
        return;
      }
      try {
        resolve(JSON.parse(xhr.responseText) as ResumeDocumentUpload);
      } catch {
        reject(new ApiError("文档 API 返回了无效响应", xhr.status));
      }
    };
    const body = new FormData();
    body.append("file", file);
    xhr.send(body);
  });
}

export const documentsApi = {
  list: () => apiFetch<ResumeDocument[]>("/api/v1/documents"),
  get: (id: string) => apiFetch<ResumeDocumentDetail>(
    `/api/v1/documents/${encodeURIComponent(id)}`,
  ),
  chunks: (id: string) => apiFetch<DocumentChunk[]>(
    `/api/v1/documents/${encodeURIComponent(id)}/chunks`,
  ),
  retry: (id: string) => apiFetch<ResumeDocumentDetail>(
    `/api/v1/documents/${encodeURIComponent(id)}/retry`,
    { method: "POST" },
  ),
  delete: (id: string) => apiFetch<void>(
    `/api/v1/documents/${encodeURIComponent(id)}`,
    { method: "DELETE" },
  ),
};
