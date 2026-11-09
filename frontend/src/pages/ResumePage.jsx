import React, { useState, useEffect } from "react"
import { PageContainer } from "@/components/layout/PageContainer"
import { ResumeUploader } from "@/components/resume/ResumeUploader"
import { ResumeList } from "@/components/resume/ResumeList"
import { ResumeProfileCard } from "@/components/resume/ResumeProfileCard"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { resumeApi } from "@/api/resumeApi"
import { UploadCloud, FileText, CheckCircle2 } from "lucide-react"

export function ResumePage({ activeResume, setActiveResume, isConnected }) {
  const [resumes, setResumes] = useState([])
  const [isUploading, setIsUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [isLoadingList, setIsLoadingList] = useState(false)

  // Fetch list of resumes on load
  const loadResumes = async () => {
    setIsLoadingList(true)
    try {
      const data = await resumeApi.listResumes(0, 30)
      if (data && data.length > 0) {
        setResumes(data)
        if (!activeResume) {
          // fetch full details for the most recent one
          const full = await resumeApi.getResume(data[0].id)
          setActiveResume(full)
        }
      } else {
        // Real database returned 0 resumes
        setResumes([])
      }
    } catch (err) {
      console.warn("Backend resumes list failed:", err.message)
      setResumes([])
    } finally {
      setIsLoadingList(false)
    }
  }

  useEffect(() => {
    loadResumes()
  }, [])

  const handleUpload = async (file) => {
    setIsUploading(true)
    setUploadError(null)
    try {
      const response = await resumeApi.uploadResume(file)
      // fetch full detail or use response
      const fullDetail = await resumeApi.getResume(response.id).catch(() => ({
        id: response.id,
        filename: response.filename,
        candidate_name: response.candidate_name,
        email: response.email,
        parsed_data: response.parsed_data,
        created_at: response.created_at,
      }))

      setActiveResume(fullDetail)
      setResumes((prev) => [fullDetail, ...prev.filter((r) => r.id !== fullDetail.id)])
    } catch (err) {
      if (err.code === "ECONNABORTED" || (err.message && err.message.toLowerCase().includes("timeout"))) {
        setUploadError("Upload timed out during deep entity parsing and embedding vectorization. Please try again.")
      } else {
        setUploadError(err.message || "Failed to upload and parse resume.")
      }
    } finally {
      setIsUploading(false)
    }
  }

  const handleSelectResume = async (resumeSummary) => {
    try {
      const full = await resumeApi.getResume(resumeSummary.id)
      setActiveResume(full)
    } catch {
      setActiveResume(resumeSummary)
    }
  }

  const handleDeleteResume = async (resumeId) => {
    try {
      await resumeApi.deleteResume(resumeId)
    } catch (e) {
      console.warn("Delete API call failed:", e)
    }
    const updated = resumes.filter((r) => r.id !== resumeId)
    setResumes(updated)
    if (activeResume?.id === resumeId) {
      setActiveResume(updated[0] || null)
    }
  }

  return (
    <PageContainer
      title="Resume Ingestion & Parsing"
      badge="Parser Agent"
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Upload & History (5 cols) */}
        <div className="lg:col-span-5 space-y-6">
          <Card className="border-[#DDD6E7] shadow-xs">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <UploadCloud className="h-4 w-4 text-[#7A2D4A]" />
                Upload Resume Document
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResumeUploader onUploadSuccess={handleUpload} isUploading={isUploading} />
              {uploadError && (
                <p className="text-xs text-rose-500 mt-2 font-medium">{uploadError}</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-[#7A2D4A]" />
                  Uploaded Profiles ({resumes.length})
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ResumeList
                resumes={resumes}
                activeResumeId={activeResume?.id}
                onSelect={handleSelectResume}
                onDelete={handleDeleteResume}
              />
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Parsed Profile Details (7 cols) */}
        <div className="lg:col-span-7">
          <ResumeProfileCard resume={activeResume} onUpdateResume={setActiveResume} />
        </div>
      </div>
    </PageContainer>
  )
}
