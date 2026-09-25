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
  Plus,
  Search,
  Trash2,
  X,
  ShieldAlert,
  Activity,
  Database,
  Tag,
  Hash
} from "lucide-react";
import {
  uploadDocument,
  deleteFile,
  fetchManualRegistry,
  fetchAuditSummary,
  ManualRecord,
  AuditSummary
} from "../lib/api";

const EQUIPMENT_TAGS = [
  { id: "all", label: "All Equipment" },
  { id: "industrial", label: "Industrial (CNC / Lathes)" },
  { id: "automobile", label: "Automotive (OBD-II)" },
  { id: "appliance", label: "Appliances & Cooling" },
];

export default function Admin() {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [currentUploadIndex, setCurrentUploadIndex] = useState(0);
  const [currentFileName, setCurrentFileName] = useState("");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedTag, setSelectedTag] = useState("all");

  // Registry and Audit state from PostgreSQL
  const [registry, setRegistry] = useState<ManualRecord[]>([]);
  const [rawFiles, setRawFiles] = useState<string[]>([]);
  const [auditData, setAuditData] = useState<AuditSummary | null>(null);
  const [isLoadingData, setIsLoadingData] = useState(true);

  // Deletion modal state
  const [deletingFile, setDeletingFile] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load Registry & Audit Summary on mount
  const loadDashboardData = async () => {
    try {
      setIsLoadingData(true);
      const [regRes, auditRes] = await Promise.allSettled([
        fetchManualRegistry(),
        fetchAuditSummary(),
      ]);

      if (regRes.status === "fulfilled") {
        setRawFiles(regRes.value.files || []);
        setRegistry(regRes.value.registry || []);
      }
      if (auditRes.status === "fulfilled") {
        setAuditData(auditRes.value);
      }
    } catch (err: any) {
      console.error("Failed to load admin dashboard data:", err);
    } finally {
      setIsLoadingData(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
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

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFiles = Array.from(e.dataTransfer.files);
      setSelectedFiles((prev) => {
        const combined = [...prev, ...droppedFiles];
        return combined.filter((f, idx, self) => idx === self.findIndex((t) => t.name === f.name));
      });
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setError(null);
    setSuccess(null);
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);
      setSelectedFiles((prev) => {
        const combined = [...prev, ...newFiles];
        return combined.filter((f, idx, self) => idx === self.findIndex((t) => t.name === f.name));
      });
    }
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

    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setIsUploading(false);

    // Refresh live data
    await loadDashboardData();

    if (errors.length > 0) {
      setError(`Encountered issues during upload:\n${errors.join("\n")}`);
    }
    if (uploadedCount > 0) {
      setSuccess(`✓ Successfully processed and registered ${uploadedCount} manual${uploadedCount > 1 ? "s" : ""}. MD5 hash logged in PostgreSQL.`);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingFile) return;
    setIsDeleting(true);
    setError(null);
    setSuccess(null);

    const targetFile = deletingFile;
    try {
      await deleteFile(targetFile);
      setSuccess(`✓ Permanently deleted "${targetFile}" from storage, PostgreSQL registry, and Qdrant vectors.`);
      setDeletingFile(null);
      await loadDashboardData();
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

  // Filter manuals based on search query & equipment tag
  const filteredManuals = (registry.length > 0 ? registry : rawFiles.map((fn, idx) => ({
    id: idx,
    filename: fn,
    equipment_type: "industrial",
    file_hash: "legacy_indexed",
    chunks_count: 0,
    created_at: new Date().toISOString()
  }))).filter((item) => {
    const matchesSearch = item.filename.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTag = selectedTag === "all" || item.equipment_type.toLowerCase() === selectedTag.toLowerCase();
    return matchesSearch && matchesTag;
  });

  return (
    <div className="min-h-screen bg-octo-bg text-octo-charcoal flex flex-col">
      {/* ── Top Navigation ────────────────────────────────────────────────────── */}
      <header className="bg-white border-b border-octo-border sticky top-0 z-30 shadow-sm">
        <div className="max-w-[1180px] mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-xl font-bold tracking-tight text-octo-charcoal">
                OCTO <span className="text-octo-orange">RAG</span>
              </span>
            </Link>
            <span className="text-xs text-octo-muted font-semibold bg-octo-surface-warm px-2.5 py-1 rounded-full border border-octo-border flex items-center gap-1.5">
              <Database className="h-3 w-3 text-octo-orange" />
              Admin Console
            </span>
          </div>

          <Link
            href="/"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-btn bg-white border border-octo-border text-xs font-semibold text-octo-charcoal hover:bg-octo-surface-warm transition-colors shadow-sm"
          >
            <ArrowLeft className="h-4 w-4 text-octo-orange" />
            <span>User UI (/app)</span>
          </Link>
        </div>
      </header>

      {/* ── Main Content Container ────────────────────────────────────────────── */}
      <main className="flex-1 max-w-[1180px] mx-auto w-full p-4 md:p-8 space-y-8">
        {/* Auth Gate Warning Banner */}
        <div className="p-4 rounded-card bg-amber-50 border border-amber-200 text-amber-900 text-xs md:text-sm flex items-start gap-3 shadow-sm">
          <ShieldAlert className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold text-amber-900">
              [TODO: Auth-Gate Pending] — Access Control Middleware
            </p>
            <p className="text-amber-700 leading-relaxed">
              This route (<code className="bg-amber-100 px-1 py-0.5 rounded font-mono">/admin</code>) allows direct manual ingestion, index deletion, and audit trail inspection. In production, integrate NextAuth.js or JWT RBAC middleware here to restrict access to authenticated technicians and maintenance leads.
            </p>
          </div>
        </div>

        {/* Dashboard Telemetry Stats Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="octo-card p-5 flex items-center gap-4">
            <div className="p-3 rounded-btn bg-blue-50 text-blue-600">
              <FileText className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs text-octo-muted font-medium">Registered Manuals</p>
              <p className="text-2xl font-bold text-octo-charcoal">
                {auditData?.total_manuals ?? registry.length ?? rawFiles.length}
              </p>
            </div>
          </div>

          <div className="octo-card p-5 flex items-center gap-4">
            <div className="p-3 rounded-btn bg-emerald-50 text-emerald-600">
              <Database className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs text-octo-muted font-medium">PostgreSQL Sessions</p>
              <p className="text-2xl font-bold text-octo-charcoal">
                {auditData?.total_sessions ?? 0}
              </p>
            </div>
          </div>

          <div className="octo-card p-5 flex items-center gap-4">
            <div className="p-3 rounded-btn bg-purple-50 text-purple-600">
              <Activity className="h-6 w-6" />
            </div>
            <div>
              <p className="text-xs text-octo-muted font-medium">Total Diagnostic Turns</p>
              <p className="text-2xl font-bold text-octo-charcoal">
                {auditData?.total_turns ?? 0}
              </p>
            </div>
          </div>
        </div>

        {/* ── Upload Area Card ────────────────────────────────────────────────── */}
        <div className="octo-card p-6 md:p-8 space-y-6">
          <div className="flex items-center justify-between border-b border-octo-border pb-4">
            <div className="flex items-center gap-2">
              <Plus className="h-5 w-5 text-octo-orange" />
              <h2 className="text-lg font-semibold text-octo-charcoal">Upload Technical Manual</h2>
            </div>
            <span className="text-xs text-octo-muted">Max 25MB · Deduplication via MD5 hash</span>
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
              multiple
              accept=".pdf,.docx,.ppt,.pptx,.xls,.xlsx,.txt"
              className="hidden"
            />
            <div className="p-4 rounded-full bg-white shadow-sm mb-3 text-octo-orange">
              <UploadCloud className="h-8 w-8" />
            </div>
            <p className="text-sm font-semibold text-octo-charcoal">
              Click to select or drag and drop technical documents here
            </p>
            <p className="text-xs text-octo-muted mt-1">
              Supports industrial equipment specs, automotive guides, and appliance service manuals
            </p>
          </div>

          {/* Selected Files Queue */}
          {selectedFiles.length > 0 && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-octo-charcoal">
                  Selected Files ({selectedFiles.length})
                </span>
                {!isUploading && (
                  <button
                    onClick={() => setSelectedFiles([])}
                    className="text-xs text-octo-muted hover:text-red-600 transition-colors"
                  >
                    Clear selection
                  </button>
                )}
              </div>

              <div className="max-h-48 overflow-y-auto space-y-2 pr-1">
                {selectedFiles.map((file) => (
                  <div
                    key={file.name}
                    className="flex items-center justify-between p-3 rounded-lg bg-octo-surface-warm/60 border border-octo-border text-xs"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <File className="h-4 w-4 text-octo-orange shrink-0" />
                      <span className="font-medium text-octo-charcoal truncate">{file.name}</span>
                      <span className="text-octo-muted shrink-0">({formatBytes(file.size)})</span>
                    </div>
                    {!isUploading && (
                      <button
                        onClick={() => removeSelectedFile(file.name)}
                        className="p-1 rounded hover:bg-white text-octo-muted hover:text-red-600 transition-colors"
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ))}
              </div>

              {/* Progress Indicator */}
              {isUploading && (
                <div className="space-y-2 p-4 rounded-lg bg-octo-surface-warm border border-octo-border animate-fadeIn">
                  <div className="flex justify-between items-center text-xs font-medium">
                    <span className="text-octo-charcoal flex items-center gap-2">
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-octo-orange" />
                      Ingesting {currentUploadIndex} of {selectedFiles.length}: {currentFileName}
                    </span>
                    <span className="text-octo-orange font-semibold">{progress}%</span>
                  </div>
                  <div className="w-full bg-octo-border rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-octo-orange h-2 rounded-full transition-all duration-200"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Action Button */}
              <button
                onClick={handleUpload}
                disabled={isUploading}
                className="w-full py-3 rounded-btn bg-octo-orange text-white font-semibold text-sm hover:bg-octo-orange/90 transition-all shadow-sm flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {isUploading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span>Processing & Embedding Manuals...</span>
                  </>
                ) : (
                  <>
                    <UploadCloud className="h-4 w-4" />
                    <span>Process & Ingest {selectedFiles.length} Manual{selectedFiles.length > 1 ? "s" : ""}</span>
                  </>
                )}
              </button>
            </div>
          )}

          {/* Feedback Messages */}
          {error && (
            <div className="p-4 rounded-card bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2.5">
              <AlertTriangle className="h-4 w-4 text-red-600 shrink-0 mt-0.5" />
              <p className="font-medium whitespace-pre-line">{error}</p>
            </div>
          )}
          {success && (
            <div className="p-4 rounded-card bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs flex items-start gap-2.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
              <p className="font-medium">{success}</p>
            </div>
          )}
        </div>

        {/* ── Equipment Tag Filter & Manuals Registry ────────────────────────── */}
        <div className="octo-card p-6 md:p-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-octo-border pb-4">
            <div>
              <h2 className="text-lg font-semibold text-octo-charcoal">PostgreSQL Manual Registry</h2>
              <p className="text-xs text-octo-muted">
                Tracked in relational <code className="bg-octo-surface-warm px-1 py-0.5 rounded font-mono">manual_registry</code> table with MD5 hashes
              </p>
            </div>

            {/* Search Input */}
            <div className="relative min-w-[240px]">
              <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-octo-muted" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter manuals..."
                className="w-full pl-9 pr-3 py-1.5 rounded-btn bg-octo-surface-warm/50 border border-octo-border text-xs focus:outline-none focus:border-octo-orange"
              />
            </div>
          </div>

          {/* Equipment Domain Filter Tags */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-octo-muted font-medium flex items-center gap-1 mr-1">
              <Tag className="h-3 w-3" /> Filter by:
            </span>
            {EQUIPMENT_TAGS.map((tag) => (
              <button
                key={tag.id}
                onClick={() => setSelectedTag(tag.id)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                  selectedTag === tag.id
                    ? "bg-octo-orange text-white shadow-sm"
                    : "bg-white border border-octo-border text-octo-muted hover:border-octo-orange hover:text-octo-charcoal"
                }`}
              >
                {tag.label}
              </button>
            ))}
          </div>

          {/* Manuals List Table */}
          {isLoadingData ? (
            <div className="py-12 flex flex-col items-center justify-center text-octo-muted gap-2">
              <Loader2 className="h-6 w-6 animate-spin text-octo-orange" />
              <p className="text-xs">Loading registry from PostgreSQL...</p>
            </div>
          ) : filteredManuals.length === 0 ? (
            <div className="py-10 text-center text-octo-muted text-xs">
              No technical manuals match the current filter.
            </div>
          ) : (
            <div className="divide-y divide-octo-border border border-octo-border rounded-card overflow-hidden bg-white">
              {filteredManuals.map((manual) => (
                <div
                  key={manual.filename}
                  className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-octo-surface-warm/30 transition-colors"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 text-octo-orange shrink-0" />
                      <span className="text-xs font-semibold text-octo-charcoal truncate">
                        {manual.filename}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-octo-surface-warm text-octo-muted border border-octo-border shrink-0">
                        {manual.equipment_type || "industrial"}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-octo-muted">
                      <span className="flex items-center gap-1 font-mono">
                        <Hash className="h-3 w-3" />
                        {manual.file_hash ? manual.file_hash.substring(0, 12) + "..." : "indexed"}
                      </span>
                      <span>·</span>
                      <span>{manual.chunks_count ?? 0} vectors</span>
                      {manual.created_at && (
                        <>
                          <span>·</span>
                          <span>{new Date(manual.created_at).toLocaleDateString()}</span>
                        </>
                      )}
                    </div>
                  </div>

                  <button
                    onClick={() => setDeletingFile(manual.filename)}
                    className="self-end sm:self-center px-2.5 py-1.5 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 text-xs font-medium flex items-center gap-1 transition-colors"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>Delete</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Basic Audit Log View ────────────────────────────────────────────── */}
        <div className="octo-card p-6 md:p-8 space-y-6">
          <div className="flex items-center justify-between border-b border-octo-border pb-4">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-octo-orange" />
              <h2 className="text-lg font-semibold text-octo-charcoal">Session Turn Audit Log</h2>
            </div>
            <span className="text-xs text-octo-muted">Live trail from session_turns</span>
          </div>

          {auditData?.recent_activity && auditData.recent_activity.length > 0 ? (
            <div className="space-y-2">
              <div className="divide-y divide-octo-border border border-octo-border rounded-card overflow-hidden bg-white text-xs">
                {auditData.recent_activity.map((turn) => (
                  <div key={turn.id} className="p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-2 hover:bg-octo-surface-warm/30">
                    <div className="flex items-start gap-2.5 min-w-0">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold shrink-0 uppercase ${
                          turn.sender === "user"
                            ? "bg-blue-100 text-blue-700"
                            : "bg-emerald-100 text-emerald-700"
                        }`}
                      >
                        {turn.sender}
                      </span>
                      <div className="min-w-0">
                        <p className="text-octo-charcoal font-medium truncate max-w-xl">
                          {turn.message_text}
                        </p>
                        {turn.question && (
                          <p className="text-[11px] text-amber-700 italic">Clarification: {turn.question}</p>
                        )}
                        <p className="text-[10px] text-octo-muted font-mono">
                          Session: {turn.session_id.substring(0, 16)}...
                        </p>
                      </div>
                    </div>
                    {turn.created_at && (
                      <span className="text-[10px] text-octo-muted shrink-0">
                        {new Date(turn.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-xs text-octo-muted text-center py-6">
              No recent audit turns recorded yet. Diagnostic turns will appear here in real time.
            </p>
          )}
        </div>
      </main>

      {/* ── Confirmation Modal for Deleting Manual ──────────────────────────── */}
      {deletingFile && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white rounded-card max-w-md w-full p-6 shadow-xl border border-octo-border space-y-4">
            <div className="flex items-center gap-3 text-red-600">
              <div className="p-2.5 rounded-full bg-red-100">
                <Trash2 className="h-6 w-6" />
              </div>
              <h3 className="text-base font-bold text-octo-charcoal">Delete Manual</h3>
            </div>

            <p className="text-xs text-octo-muted leading-relaxed">
              Are you sure you want to permanently delete{" "}
              <span className="font-semibold text-octo-charcoal font-mono">"{deletingFile}"</span>?
              This will remove the file from disk, wipe its vector embeddings from Qdrant, and delete its record from PostgreSQL.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => setDeletingFile(null)}
                disabled={isDeleting}
                className="px-4 py-2 rounded-btn border border-octo-border text-xs font-semibold text-octo-charcoal hover:bg-octo-surface-warm transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmDelete}
                disabled={isDeleting}
                className="px-4 py-2 rounded-btn bg-red-600 hover:bg-red-700 text-white text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                {isDeleting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                <span>Confirm Delete</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
