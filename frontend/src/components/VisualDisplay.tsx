import React, { useState } from "react";
import { Image as ImageIcon, Maximize2, X, ZoomIn, ZoomOut, AlertCircle } from "lucide-react";
import { RetrievedImage } from "./MessageBubble";

interface VisualDisplayProps {
  images?: RetrievedImage[];
  isDiagramRequested?: boolean;
}

export const VisualDisplay: React.FC<VisualDisplayProps> = ({ images = [], isDiagramRequested = false }) => {
  const [selectedImage, setSelectedImage] = useState<RetrievedImage | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  // Honest Diagram Fallback: If user asked for a diagram but no image exists in manual payload
  if ((!images || images.length === 0) && isDiagramRequested) {
    return (
      <div className="my-3 p-4 octo-card-subtle text-amber-800 text-xs flex items-start gap-2.5 border border-amber-200">
        <AlertCircle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold text-octo-charcoal text-xs">No Diagram Available</p>
          <p className="mt-0.5 text-octo-muted leading-relaxed">
            No diagram or schematic drawing was found in the uploaded manual for this specific component.
          </p>
        </div>
      </div>
    );
  }

  if (!images || images.length === 0) return null;

  return (
    <div className="flex flex-col gap-3 my-3 w-full">
      <div className="flex items-center gap-2 text-xs font-semibold text-octo-muted uppercase tracking-wider">
        <ImageIcon className="h-4 w-4 text-octo-orange" />
        <span>Related Diagram & Schematic</span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {images.map((img) => (
          <div
            key={img.image_id}
            className="octo-card p-3 flex flex-col gap-2 hover:border-octo-orange transition-all duration-200 cursor-pointer group"
            onClick={() => {
              setSelectedImage(img);
              setZoomLevel(1);
            }}
          >
            <div className="relative w-full aspect-video rounded-lg overflow-hidden bg-[#F2EEE9] flex items-center justify-center border border-octo-border">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`http://localhost:8000${img.url}`}
                alt={img.caption || "Technical Diagram"}
                className="object-contain max-h-full max-w-full group-hover:scale-[1.02] transition-transform duration-300"
              />
              <div className="absolute top-2 right-2 bg-white/90 p-1.5 rounded-lg shadow border border-octo-border text-octo-charcoal group-hover:text-octo-orange transition-colors">
                <Maximize2 className="h-4 w-4" />
              </div>
            </div>

            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium text-octo-charcoal line-clamp-2" title={img.caption}>
                {img.caption || "Technical Diagram / Schematic"}
              </p>
              <div className="flex justify-between items-center text-xs text-octo-muted">
                <span className="truncate max-w-[70%] font-medium">📄 {img.document_id}</span>
                <span className="bg-octo-surface-warm px-2 py-0.5 rounded-full text-octo-charcoal font-semibold border border-octo-border">
                  Page {img.page}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Expanded Modal Viewer */}
      {selectedImage && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-card max-w-4xl w-full max-h-[90vh] flex flex-col border border-octo-border shadow-2xl overflow-hidden animate-fadeIn">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-octo-border bg-octo-bg">
              <div className="flex items-center gap-2 text-sm font-semibold text-octo-charcoal">
                <ImageIcon className="h-4 w-4 text-octo-orange" />
                <span>Schematic View · Page {selectedImage.page}</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setZoomLevel((prev) => Math.min(prev + 0.25, 2.5))}
                  className="p-1.5 rounded-lg border border-octo-border bg-white text-octo-charcoal hover:bg-octo-surface-warm"
                  title="Zoom In"
                >
                  <ZoomIn className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setZoomLevel((prev) => Math.max(prev - 0.25, 0.75))}
                  className="p-1.5 rounded-lg border border-octo-border bg-white text-octo-charcoal hover:bg-octo-surface-warm"
                  title="Zoom Out"
                >
                  <ZoomOut className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setSelectedImage(null)}
                  className="p-1.5 rounded-lg border border-octo-border bg-white text-octo-charcoal hover:bg-red-50 hover:text-red-600 ml-2"
                  title="Close viewer"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-auto p-6 bg-[#F2EEE9] flex items-center justify-center min-h-[300px]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`http://localhost:8000${selectedImage.url}`}
                alt={selectedImage.caption}
                style={{ transform: `scale(${zoomLevel})` }}
                className="max-h-[65vh] object-contain transition-transform duration-200"
              />
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-octo-border bg-white flex justify-between items-center text-xs text-octo-muted">
              <span className="font-medium text-octo-charcoal">{selectedImage.caption}</span>
              <span>📄 Document: {selectedImage.document_id}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
