import { useState, useCallback } from 'react';
import {
  UploadOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FilePdfOutlined,
  FileMarkdownOutlined,
  InboxOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { listDocuments, uploadDocument, deleteDocument } from '@/api/documents';
import type { DocumentInfo } from '@/api/documents';

export default function DocumentsPage() {
  const { t } = useTranslation();
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [initialized, setInitialized] = useState(false);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  if (!initialized) {
    setInitialized(true);
    fetchDocuments();
  }

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    setUploading(true);
    try {
      for (const file of Array.from(files)) {
        await uploadDocument(file);
      }
      await fetchDocuments();
    } catch {
      // error handling
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (docId: string) => {
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.document_id !== docId));
    } catch {
      // error handling
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  const getFileIcon = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf':
        return <FilePdfOutlined />;
      case 'md':
        return <FileMarkdownOutlined />;
      default:
        return <FileTextOutlined />;
    }
  };

  return (
    <div className="documents-page">
      <div className="documents-header">
        <div>
          <h1 className="documents-title">{t('documents.title')}</h1>
          <p className="documents-subtitle">{t('documents.subtitle')}</p>
        </div>
      </div>

      {/* Upload Zone */}
      <div
        className={`upload-zone ${dragOver ? 'upload-zone-active' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => {
          const input = document.createElement('input');
          input.type = 'file';
          input.multiple = true;
          input.accept = '.pdf,.md,.txt,.text';
          input.onchange = (e) => handleUpload((e.target as HTMLInputElement).files);
          input.click();
        }}
      >
        {uploading ? (
          <div className="upload-zone-content">
            <div className="upload-spinner" />
            <p>{t('common.loading')}</p>
          </div>
        ) : (
          <div className="upload-zone-content">
            <InboxOutlined className="upload-zone-icon" />
            <p className="upload-zone-text">{t('documents.uploadHint')}</p>
            <button className="upload-btn">
              <UploadOutlined /> {t('common.upload')}
            </button>
          </div>
        )}
      </div>

      {/* Document List */}
      <div className="documents-list">
        {loading ? (
          <div className="documents-empty">
            <p>{t('common.loading')}</p>
          </div>
        ) : documents.length === 0 ? (
          <div className="documents-empty">
            <InboxOutlined className="documents-empty-icon" />
            <p>{t('documents.noDocuments')}</p>
          </div>
        ) : (
          <table className="documents-table">
            <thead>
              <tr>
                <th>{t('documents.fileName')}</th>
                <th>{t('documents.chunksCount')}</th>
                <th>{t('documents.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.document_id}>
                  <td>
                    <div className="doc-name-cell">
                      {getFileIcon(doc.file_name)}
                      <span>{doc.file_name}</span>
                    </div>
                  </td>
                  <td>
                    <span className="doc-chunk-badge">{doc.chunk_count}</span>
                  </td>
                  <td>
                    <button
                      className="doc-delete-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(doc.document_id);
                      }}
                      title={t('common.delete')}
                    >
                      <DeleteOutlined />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
