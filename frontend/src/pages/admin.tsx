import { useState, useRef, DragEvent, ChangeEvent } from "react";
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
  Info
} from "lucide-react";
import { uploadDocument, UploadResponse } from "../lib/api";

interface UploadedItem {
  id: string;
  filename: string;
  markdownFile: string;
  timestamp: Date;
  status: "success" | "duplicate" | "error";
  details?: string;
}

export default function Admin() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [duplicateNotice, setDuplicateNotice] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  
  const [history, setHistory] = useState<UploadedItem[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      const file = e.dataTransfer.files[0];
      setSelectedFile(file);
    }
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setSuccess(null);
    setDuplicateNotice(null);
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const triggerFileSelect = () => {
    fileInputRef.current?.click();
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    setIsUploading(true);
    setProgress(0);
    setError(null);
    setSuccess(null);
    setDuplicateNotice(null);

    // Check if file is already in history
    const isDuplicate = history.some(h => h.filename === selectedFile.name && h.status === "success");

    try {
      const result: UploadResponse = await uploadDocument(selectedFile, (pct) => {
        setProgress(pct);
      });

      if (isDuplicate) {
        setDuplicateNotice(`This manual (${result.filename}) was already in Octo RAG. Re-indexed latest version.`);
      } else {
        setSuccess(
          `✓ "${result.filename}" processed and added to assistant manuals. Ready for search!`
        );
      }

      const newItem: UploadedItem = {
        id: Math.random().toString(36).substring(7),
        filename: result.filename,
        markdownFile: result.markdown_file,
        timestamp: new Date(),
        status: isDuplicate ? "duplicate" : "success",
      };
      setHistory((prev) => [newItem, ...prev.filter(h => h.filename !== result.filename)]);
      setSelectedFile(null);
    } catch (err: any) {
      const errorMessage = err.message || "Failed to process the document.";
      setError(errorMessage);

      const newItem: UploadedItem = {
        id: Math.random().toString(36).substring(7),
        filename: selectedFile.name,
        markdownFile: "",
        timestamp: new Date(),
        status: "error",
        details: errorMessage,
      };
      setHistory((prev) => [newItem, ...prev]);
    } finally {
      setIsUploading(false);
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

  const filteredHistory = history.filter((item) =>
    item.filename.toLowerCase().includes(searchQuery.toLowerCase())
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
              Manual Management
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
          <h1 className="text-2xl font-bold text-octo-charcoal tracking-tight">Manuals & Documents</h1>
          <p className="text-sm text-octo-muted">
            Upload equipment manuals, PDF guides, and troubleshooting specs so Octo RAG can answer technical questions.
          </p>
        </div>

        {/* ── Upload Area Card ────────────────────────────────────────────────── */}
        <div className="octo-card p-6 md:p-8 space-y-6">
          <div className="flex items-center justify-between border-b border-octo-border pb-4">
            <div className="flex items-center gap-2">
              <Plus className="h-5 w-5 text-octo-orange" />
              <h2 className="text-lg font-semibold text-octo-charcoal">Upload Manual</h2>
            </div>
            <span className="text-xs text-octo-muted">Max 25MB · PDF, DOCX, TXT</span>
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
              className="hidden"
            />
            <div className="p-4 bg-white rounded-full border border-octo-border shadow-sm mb-3">
              <UploadCloud className="h-7 w-7 text-octo-orange" />
            </div>
            <p className="text-base font-semibold text-octo-charcoal text-center">
              Drag and drop your manual here, or <span className="text-octo-orange hover:underline">browse files</span>
            </p>
            <p className="text-xs text-octo-muted mt-1.5">Supported: PDF, Word (DOCX), Text files</p>
          </div>

          {/* Selected File Card */}
          {selectedFile && (
            <div className="octo-card-subtle p-4 flex items-center justify-between gap-4 animate-fadeIn">
              <div className="flex items-center gap-3 min-w-0">
                <div className="p-2.5 bg-white rounded-btn border border-octo-border text-octo-orange shrink-0">
                  <File className="h-5 w-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-octo-charcoal truncate">{selectedFile.name}</p>
                  <p className="text-xs text-octo-muted mt-0.5">{formatBytes(selectedFile.size)}</p>
                </div>
              </div>

              <button
                onClick={handleUpload}
                disabled={isUploading}
                className="h-11 px-5 rounded-btn text-xs font-semibold text-white bg-octo-orange hover:bg-octo-orange-hover shadow-sm active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed shrink-0 flex items-center gap-2"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Processing...</span>
                  </>
                ) : (
                  <span>Upload Manual</span>
                )}
              </button>
            </div>
          )}

          {/* Stage-by-Stage Progress Bar */}
          {isUploading && (
            <div className="space-y-3 p-4 bg-white rounded-card border border-octo-border animate-fadeIn">
              <div className="flex justify-between text-xs font-semibold text-octo-charcoal">
                <span>
                  {progress < 30
                    ? "✓ Uploading document..."
                    : progress < 60
                    ? "✓ Extracting text & diagrams..."
                    : progress < 90
                    ? "✓ Updating search index..."
                    : "✓ Almost ready!"}
                </span>
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
                <p className="font-semibold text-sm">Document Ingested</p>
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
                <p className="mt-1 leading-relaxed">{error}</p>
              </div>
            </div>
          )}
        </div>

        {/* ── Document Library History ────────────────────────────────────────── */}
        <div className="octo-card p-6 md:p-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-octo-border pb-4">
            <div className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-octo-orange" />
              <h2 className="text-lg font-semibold text-octo-charcoal">Session Upload Log</h2>
            </div>

            {/* Filter Search Input */}
            {history.length > 0 && (
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

          {history.length === 0 ? (
            <div className="text-center py-10 border border-octo-border rounded-card bg-octo-surface-warm/40">
              <FileText className="h-8 w-8 text-octo-muted mx-auto mb-2" />
              <p className="text-sm font-medium text-octo-charcoal">No documents uploaded in this session yet.</p>
              <p className="text-xs text-octo-muted mt-1">Uploaded manuals will appear here after ingestion.</p>
            </div>
          ) : filteredHistory.length === 0 ? (
            <div className="text-center py-6 text-xs text-octo-muted">
              No manuals found matching "{searchQuery}".
            </div>
          ) : (
            <div className="divide-y divide-octo-border border border-octo-border rounded-card overflow-hidden bg-white">
              {filteredHistory.map((item) => (
                <div
                  key={item.id}
                  className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between text-xs hover:bg-octo-surface-warm/50 transition-colors gap-3"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div
                      className={`p-2 rounded-btn border shrink-0 ${
                        item.status === "success" || item.status === "duplicate"
                          ? "bg-emerald-50 border-emerald-200 text-emerald-700"
                          : "bg-red-50 border-red-200 text-red-700"
                      }`}
                    >
                      <File className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <p className="font-semibold text-octo-charcoal text-sm truncate">{item.filename}</p>
                      <p className="text-xs text-octo-muted mt-0.5">
                        Uploaded at {item.timestamp.toLocaleTimeString()} · Status:{" "}
                        {item.status === "success"
                          ? "✓ Ready for search"
                          : item.status === "duplicate"
                          ? "ℹ️ Re-indexed existing manual"
                          : "Upload error"}
                      </p>
                    </div>
                  </div>

                  <div className="shrink-0 flex items-center gap-2 self-end sm:self-center">
                    <Link
                      href="/"
                      className="px-3 py-1 rounded-btn bg-octo-surface-warm hover:bg-[#E4DCD0] text-octo-charcoal border border-octo-border text-xs font-semibold transition-colors"
                    >
                      Ask about this
                    </Link>
                    {item.status === "success" || item.status === "duplicate" ? (
                      <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                        Ready
                      </span>
                    ) : (
                      <span
                        className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-200 cursor-help"
                        title={item.details}
                      >
                        Failed
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
