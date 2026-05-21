import apiClient from './client';

export interface DocumentInfo {
  document_id: string;
  file_name: string;
  chunk_count: number;
  source_type?: string;
}

export interface UploadResult {
  document_id: string;
  file_name: string;
  saved_path: string;
  chunks_added: number;
}

export async function listDocuments(): Promise<DocumentInfo[]> {
  const { data } = await apiClient.get('/documents');
  return data.documents || [];
}

export async function uploadDocument(file: File): Promise<UploadResult> {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await apiClient.post('/documents/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  });
  return data;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/documents/${encodeURIComponent(documentId)}`);
}
