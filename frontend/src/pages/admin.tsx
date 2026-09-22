import { useState, useEffect, useRef, DragEvent, ChangeEvent } from "react";
import Link from "next/link";
import {
  FileText,
  UploadCloud,
  File,
  CheckCircle2,
  AlertTriangle,
  ArrowLeft,
  Loader2,
  BookOpen,
  Plus,
  Search,
  Info,
  Trash2,
  X
} from "lucide-react";
import { uploadDocument, fetchFiles, deleteFile } from "../lib/api";

export default function Admin() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [currentUploadIndex, setCurrentUploadIndex] = useState(0);
  const [currentFileName, setCurrentFileName] = useState("");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [duplicateNotice, setDuplicateNotice] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Live available manuals from backend
  const [availableManuals, setAvailableManuals] = useState<string[]>([]);
  const [isLoadingManuals, setIsLoadingManuals] = useState(true);

  // Deletion modal state
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load available manuals on mount
  const loadManuals = async () => {
    try {
      setIsLoadingManuals(true);
      const files = await fetchFiles();
      setAvailableManuals(files);
    } catch (err: any) {
      console.error("Failed to load manuals:", err);
    } finally {
      setIsLoadingManuals(false);
    }
  };

  useEffect(() => {
    loadManuals();
  }, []);

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    setError(null);
    setSuccess(null);
    setDuplicateNotice(null);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFiles = Array.from(e.dataTransfer.files);
      setSelectedFiles((prev) => {
        const combined = [...prev, ...droppedFiles];
        // Deduplicate by name
        return combined.filter((f, idx, self) => idx === self.findIndex((t) => t.name === f.name));
      });
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setSuccess(null);
    setDuplicateNotice(null);
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);
      setSelectedFiles((prev) => {
        const combined = [...prev, ...newFiles];
        return combined.filter((f, idx, self) => idx === self.findIndex((t) => t.name === f.name));
      });
    }
    // Always reset file input value so selecting the same or new files works consecutively
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  const removeSelectedFile = (fileName: string) => {
    setSelectedFiles((prev) => prev.filter((f) => f.name !== fileName));
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    setIsUploading(true);
    setError(null);
    setSuccess(null);
    setDuplicateNotice(null);

    let uploadedCount = 0;
    const errors: string[] = [];

    for (let i = 0; i < selectedFiles.length; i++) {
      const file = selectedFiles[i];
      setCurrentUploadIndex(i + 1);
      setCurrentFileName(file.name);
      setProgress(0);

      try {
        await uploadDocument(file, (pct) => {
          setProgress(pct);
        });
        uploadedCount++;
      } catch (err: any) {
        const msg = err.message || `Failed to process ${file.name}`;
        errors.push(`${file.name}: ${msg}`);
      }
    }

    // Reset state & input reference
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setIsUploading(false);

    // Refresh live backend manual list immediately
    await loadManuals();

    if (errors.length > 0) {
      setError(`Encountered issues during upload:\n${errors.join("\n")}`);
    }
    if (uploadedCount > 0) {
      setSuccess(`✓ Successfully processed and indexed ${uploadedCount} manual${uploadedCount > 1 ? "s" : ""}. Ready for search!`);
    }
  };

  // Delete manual flow with confirmation
  const handleConfirmDelete = async () => {
    if (!deletingFile) return;
    setIsDeleting(true);
    setError(null);
    setSuccess(null);

    const targetFile = deletingFile;
    try {
      await deleteFile(targetFile);
      // Optimistic update
      setAvailableManuals((prev) => prev.filter((f) => f !== targetFile));
      setSuccess(`✓ Permanently deleted "${targetFile}" and cleared its search index.`);
      setDeletingFile(null);
      // Synchronize with backend
      await loadManuals();
    } catch (err: any) {
      setError(err.message || `Failed to delete ${targetFile}`);
      setDeletingFile(null);
    } finally {
      setIsDeleting(false);
    }
  };

  const formatBytes = (bytes: number, decimals = 2) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
  };

  const filteredManuals = availableManuals.filter((file) =>
    file.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="min-h-screen bg-octo-bg text-octo-charcoal flex flex-col">
      {/* ── Top Navigation ────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-octo-border sticky top-0 z-30 shadow-sm">
        <div className="max-w-[1100px] mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-xl font-bold tracking-tight text-octo-charcoal">
                OCTO <span className="text-octo-orange">RAG</span>
              </span>
            </Link>
            <span className="text-xs text-octo-muted font-semibold bg-octo-surface-warm px-2.5 py-1 rounded-full border border-octo-border">
              My Manuals
            </span>
          </div>

          <Link
            href="/"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-btn bg-white border border-octo-border text-xs font-semibold text-octo-charcoal hover:bg-octo-surface-warm transition-colors shadow-sm"
          >
            <ArrowLeft className="h-4 w-4 text-octo-orange" />
            <span>Back to Assistant</span>
          </Link>
        </div>
      </header>

      {/* ── Main Content Container ────────────────────────────────────────────── */}
      <main className="flex-1 max-w-[900px] mx-auto w-full p-4 md:p-8 space-y-8">
        {/* Header Title */}
        <div className="space-y-1">
          <h1 className="text-2xl font-bold text-octo-charcoal tracking-tight">My Manuals & Documents</h1>
          <p className="text-sm text-octo-muted">
            Upload, manage, and delete technical equipment manuals and PDF guides indexed in Octo RAG.
          </p>
        </div>

        {/* ── Upload Area Card ────────────────────────────────────────────────── */}
        <div className="octo-card p-6 md:p-8 space-y-6">
          <div className="flex items-center justify-between border-b border-octo-border pb-4">
            <div className="flex items-center gap-2">
              <Plus className="h-5 w-5 text-octo-orange" />
              <h2 className="text-lg font-semibold text-octo-charcoal">Upload Manuals</h2>
            </div>
            <span className="text-xs text-octo-muted">Max 25MB each · PDF, DOCX, TXT</span>
          </div>

          {/* Drag & Drop Box */}
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={triggerFileSelect}
            className={`border-2 border-dashed rounded-card p-8 flex flex-col items-center justify-center cursor-pointer transition-all duration-200 ${
              isDragging
                ? "border-octo-orange bg-octo-orange-light shadow-inner"
                : "border-octo-border hover:border-octo-orange bg-octo-surface-warm/40 hover:bg-octo-surface-warm"
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".pdf,.docx,.ppt,.pptx,.xls,.xlsx,.txt"
              multiple
              className="hidden"
            />
            <div className="p-4 bg-white rounded-full border border-octo-border shadow-sm mb-3">
              <UploadCloud className="h-7 w-7 text-octo-orange" />
            </div>
            <p className="text-base font-semibold text-octo-charcoal text-center">
              Drag and drop manuals here, or <span className="text-octo-orange hover:underline">browse files</span>
            </p>
            <p className="text-xs text-octo-muted mt-1.5">You can select multiple files at once. Supported: PDF, Word (DOCX), Text</p>
          </div>

          {/* Selected Files List Preview */}
          {selectedFiles.length > 0 && (
            <div className="space-y-3 animate-fadeIn">
              <div className="flex items-center justify-between text-xs font-semibold text-octo-charcoal">
                <span>Selected Files ({selectedFiles.length})</span>
                <button
                  onClick={() => setSelectedFiles([])}
                  className="text-octo-muted hover:text-red-600 transition-colors"
                >
                  Clear all
                </button>
              </div>

              <div className="divide-y divide-octo-border border border-octo-border rounded-card bg-white overflow-hidden">
                {selectedFiles.map((file) => (
                  <div key={file.name} className="p-3 flex items-center justify-between gap-3 text-xs">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="p-1.5 bg-octo-surface-warm rounded border border-octo-border text-octo-orange shrink-0">
                        <File className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-semibold text-octo-charcoal truncate">{file.name}</p>
                        <p className="text-[11px] text-octo-muted">{formatBytes(file.size)}</p>
                      </div>
                    </div>
                    {!isUploading && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          removeSelectedFile(file.name);
                        }}
                        className="p-1 text-octo-muted hover:text-red-600 rounded hover:bg-red-50 transition-colors"
                        title="Remove file"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <button
                onClick={handleUpload}
                disabled={isUploading}
                className="w-full h-11 px-5 rounded-btn text-xs font-semibold text-white bg-octo-orange hover:bg-octo-orange-hover shadow-sm active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Processing file {currentUploadIndex} of {selectedFiles.length}: {currentFileName}...</span>
                  </>
                ) : (
                  <span>Upload & Index {selectedFiles.length} Manual{selectedFiles.length > 1 ? "s" : ""}</span>
                )}
              </button>
            </div>
          )}

          {/* Upload Progress Bar */}
          {isUploading && (
            <div className="space-y-2 p-4 bg-white rounded-card border border-octo-border animate-fadeIn">
              <div className="flex justify-between text-xs font-semibold text-octo-charcoal">
                <span>Ingesting {currentFileName}...</span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 w-full bg-octo-surface-warm rounded-full overflow-hidden border border-octo-border">
                <div
                  className="h-full bg-octo-orange rounded-full transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Status Alerts */}
          {success && (
            <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-card text-xs flex items-start gap-3 animate-fadeIn">
              <CheckCircle2 className="h-5 w-5 text-emerald-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-sm">Success</p>
                <p className="mt-1 leading-relaxed">{success}</p>
              </div>
            </div>
          )}

          {duplicateNotice && (
            <div className="p-4 bg-blue-50 border border-blue-200 text-blue-800 rounded-card text-xs flex items-start gap-3 animate-fadeIn">
              <Info className="h-5 w-5 text-blue-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-sm">Manual Already Exists</p>
                <p className="mt-1 leading-relaxed">{duplicateNotice}</p>
              </div>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-50 border border-red-200 text-red-800 rounded-card text-xs flex items-start gap-3 animate-fadeIn">
              <AlertTriangle className="h-5 w-5 text-red-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-sm">Upload Issue</p>
                <p className="mt-1 leading-relaxed whitespace-pre-line">{error}</p>
              </div>
            </div>
          )}
        </div>

        {/* ── Available Manuals Section (My Manuals) ─────────────────────────── */}
        <div className="octo-card p-6 md:p-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-octo-border pb-4">
            <div className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-octo-orange" />
              <h2 className="text-lg font-semibold text-octo-charcoal">Available Manuals</h2>
              {availableManuals.length > 0 && (
                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-octo-surface-warm text-octo-charcoal border border-octo-border">
                  {availableManuals.length}
                </span>
              )}
            </div>

            {/* Filter Search Input */}
            {availableManuals.length > 0 && (
              <div className="relative flex items-center">
                <Search className="h-3.5 w-3.5 text-octo-muted absolute left-3" />
                <input
                  type="text"
                  placeholder="Search manuals..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 bg-octo-surface-warm border border-octo-border rounded-lg text-xs text-octo-charcoal focus:outline-none focus:border-octo-orange w-48"
                />
              </div>
            )}
          </div>

          {isLoadingManuals ? (
            <div className="text-center py-10">
              <Loader2 className="h-6 w-6 text-octo-orange animate-spin mx-auto mb-2" />
              <p className="text-xs text-octo-muted">Loading indexed manuals...</p>
            </div>
          ) : availableManuals.length === 0 ? (
            <div className="text-center py-10 border border-octo-border rounded-card bg-octo-surface-warm/40">
              <FileText className="h-8 w-8 text-octo-muted mx-auto mb-2" />
              <p className="text-sm font-medium text-octo-charcoal">No manuals currently available.</p>
              <p className="text-xs text-octo-muted mt-1">Upload equipment manuals above to enable technical RAG search.</p>
            </div>
          ) : filteredManuals.length === 0 ? (
            <div className="text-center py-6 text-xs text-octo-muted">
              No manuals found matching "{searchQuery}".
            </div>
          ) : (
            <div className="divide-y divide-octo-border border border-octo-border rounded-card overflow-hidden bg-white">
              {filteredManuals.map((filename) => (
                <div
                  key={filename}
                  className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between text-xs hover:bg-octo-surface-warm/50 transition-colors gap-3"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="p-2 rounded-btn border border-emerald-200 bg-emerald-50 text-emerald-700 shrink-0">
                      <File className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-octo-charcoal text-sm truncate">{filename}</p>
                      <p className="text-xs text-octo-muted mt-0.5 flex items-center gap-2">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-600" />
                        <span>Indexed & Search Ready</span>
                      </p>
                    </div>
                  </div>

                  <div className="shrink-0 flex items-center gap-2 self-end sm:self-center">
                    <Link
                      href={`/?file=${encodeURIComponent(filename)}`}
                      className="px-3 py-1.5 rounded-btn bg-octo-surface-warm hover:bg-[#E4DCD0] text-octo-charcoal border border-octo-border text-xs font-semibold transition-colors"
                    >
                      Ask about this
                    </Link>

                    {/* Delete Action Button */}
                    <button
                      onClick={() => setDeletingFile(filename)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-btn bg-white hover:bg-red-50 text-red-600 border border-red-200 text-xs font-semibold transition-colors shadow-sm"
                      title="Delete this manual"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      <span>Delete</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* ── Confirmation Modal for Deleting Manual ───────────────────────────── */}
      {deletingFile && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white rounded-card border border-octo-border shadow-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-full bg-red-100 text-red-600 shrink-0">
                <AlertTriangle className="h-6 w-6" />
              </div>
              <div className="space-y-1 min-w-0">
                <h3 className="text-base font-bold text-octo-charcoal">Delete Manual</h3>
                <p className="text-xs text-octo-muted leading-relaxed">
                  Are you sure you want to permanently delete <strong className="text-octo-charcoal break-all">{deletingFile}</strong>?
                </p>
                <p className="text-xs text-red-600 font-medium">
                  This will remove the document, its extracted diagrams, and all search vector embeddings. This action cannot be undone.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-octo-border">
              <button
                onClick={() => setDeletingFile(null)}
                disabled={isDeleting}
                className="px-4 py-2 rounded-btn border border-octo-border bg-white text-xs font-semibold text-octo-charcoal hover:bg-octo-surface-warm transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="px-4 py-2 rounded-btn bg-red-600 hover:bg-red-700 text-xs font-semibold text-white transition-colors shadow-sm flex items-center gap-1.5 disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>Confirm Delete</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
