import React, { useCallback, useState } from "react"
import { useDropzone } from "react-dropzone"
import { UploadCloud, File, AlertCircle, CheckCircle2, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"

export function ResumeUploader({ onUploadSuccess, isUploading, uploadProgress }) {
  const [dragError, setDragError] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)

  const onDrop = useCallback(
    (acceptedFiles, rejectedFiles) => {
      setDragError(null)
      if (rejectedFiles && rejectedFiles.length > 0) {
        const error = rejectedFiles[0].errors[0]
        if (error.code === "file-too-large") {
          setDragError("File is too large. Maximum size is 10 MB.")
        } else if (error.code === "file-invalid-type") {
          setDragError("Invalid file type. Please upload a PDF, DOCX, or TXT document.")
        } else {
          setDragError(error.message || "Failed to accept file.")
        }
        return
      }

      if (acceptedFiles && acceptedFiles.length > 0) {
        const file = acceptedFiles[0]
        setSelectedFile(file)
        if (onUploadSuccess) {
          onUploadSuccess(file)
        }
      }
    },
    [onUploadSuccess]
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
      "text/plain": [".txt"],
    },
    maxFiles: 1,
    maxSize: 10 * 1024 * 1024, // 10MB
    disabled: isUploading,
  })

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`relative flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-2xl transition-all duration-200 cursor-pointer text-center ${
          isDragActive
            ? "border-[#7A2D4A] bg-[#EDE7F6] scale-[1.01]"
            : "border-[#DDD6E7] hover:border-[#7A2D4A] bg-[#FAF7F3] hover:bg-[#EDE7F6]/50"
        } ${isUploading ? "pointer-events-none opacity-80" : ""}`}
      >
        <input {...getInputProps()} />

        {isUploading ? (
          <div className="flex flex-col items-center space-y-3">
            <div className="relative">
              <div className="h-14 w-14 rounded-full bg-[#EDE7F6] flex items-center justify-center">
                <Loader2 className="h-7 w-7 text-[#7A2D4A] animate-spin" />
              </div>
            </div>
            <div>
              <p className="text-sm font-semibold text-[#3A3A52]">Extracting & Vectorizing Resume...</p>
              <p className="text-xs text-[#5C5C7A] mt-1">
                Running Parser Agent (Rule-Based + Entity NLP) & embedding generation
              </p>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-3">
            <div className="h-12 w-12 rounded-full bg-[#EDE7F6] border border-[#DDD6E7] flex items-center justify-center text-[#7A2D4A]">
              <UploadCloud className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-semibold text-[#3A3A52]">
                {isDragActive ? "Drop the resume here..." : "Drag & drop your resume, or browse"}
              </p>
              <p className="text-xs text-[#5C5C7A] mt-1">Supports PDF, DOCX, TXT up to 10 MB</p>
            </div>
          </div>
        )}
      </div>

      {dragError && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{dragError}</span>
        </div>
      )}
    </div>
  )
}
