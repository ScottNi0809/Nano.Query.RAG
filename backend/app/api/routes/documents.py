from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import get_settings
from app.services.document_service import get_document_service
from app.services.vectorstore_service import get_vectorstore_service

router = APIRouter()


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    settings = get_settings()
    docs_dir = Path(settings.docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)

    original_name = Path(file.filename or "uploaded-file").name
    extension = Path(original_name).suffix.lower()
    if extension not in (".pdf", ".md", ".txt", ".text"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {extension}")

    document_id = str(uuid4())
    target_path = docs_dir / f"{document_id}_{original_name}"

    content = await file.read()
    target_path.write_bytes(content)

    document_service = get_document_service()
    vectorstore_service = get_vectorstore_service()

    loaded_documents = document_service.load_file(str(target_path))
    chunks = document_service.split_documents(loaded_documents)
    result = vectorstore_service.add_documents(chunks, document_id=document_id)

    return {
        "document_id": document_id,
        "file_name": original_name,
        "saved_path": str(target_path),
        "chunks_added": result["chunks_added"],
    }


@router.get("/documents")
async def list_documents():
    return {
        "documents": get_vectorstore_service().list_documents(),
    }


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    result = get_vectorstore_service().delete_document(document_id)
    return result