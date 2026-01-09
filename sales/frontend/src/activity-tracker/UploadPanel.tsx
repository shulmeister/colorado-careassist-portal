import { useMemo, useState, useRef } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  LinearProgress,
  Typography,
  Chip,
} from "@mui/material";
import CloudUploadIcon from "@mui/icons-material/CloudUpload";
import ArticleIcon from "@mui/icons-material/Article";
import ImageIcon from "@mui/icons-material/Image";
import FolderIcon from "@mui/icons-material/Folder";
import ContactsIcon from "@mui/icons-material/Contacts";

const ACCEPTED_TYPES = [
  ".pdf",
  ".jpg",
  ".jpeg",
  ".png",
  ".heic",
  ".heif",
];

type UploadResult = {
  success: boolean;
  type?: string;
  filename?: string;
  date?: string;
  total_hours?: number;
  count?: number;
  visits?: Array<Record<string, unknown>>;
  contact?: Record<string, unknown>;
  extracted_text?: string;
  error?: string;
};

type BulkResult = {
  success: boolean;
  message?: string;
  has_more?: boolean;
  total_files?: number;
  processed_so_far?: number;
  next_index?: number;
  batch_processed?: number;
  batch_results?: {
    contacts_created: number;
    contacts_updated: number;
    companies_created: number;
    companies_linked: number;
    errors: string[];
    details: Array<{
      file: string;
      contact: string;
      company: string;
      status: string;
    }>;
  };
  // Cumulative totals for display
  totals?: {
    contacts_created: number;
    contacts_updated: number;
    companies_created: number;
    companies_linked: number;
    errors: string[];
    details: Array<{
      file: string;
      contact: string;
      company: string;
      status: string;
    }>;
  };
  error?: string;
};

type UploadPanelProps = {
  showLegacyLink?: boolean;
};

export const UploadPanel = ({ showLegacyLink = true }: UploadPanelProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleChooseFile = () => {
    fileInputRef.current?.click();
  };

  const fileIcon = useMemo(() => {
    if (!file) return null;
    if (file.type.includes("pdf")) {
      return <ArticleIcon sx={{ color: "#38bdf8" }} fontSize="large" />;
    }
    return <ImageIcon sx={{ color: "#f472b6" }} fontSize="large" />;
  }, [file]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0] ?? null;
    setFile(nextFile);
    setResult(null);
    setError(null);
  };

  const [driveUrl, setDriveUrl] = useState("");
  const [assignTo, setAssignTo] = useState<string>(
    "jacob@coloradocareassist.com",
  );

  // Bulk business card folder upload
  const [folderUrl, setFolderUrl] = useState("");
  const [bulkLoading, setBulkLoading] = useState(false);
  const [bulkResult, setBulkResult] = useState<BulkResult | null>(null);
  const [bulkError, setBulkError] = useState<string | null>(null);

  const handleUpload = async () => {
    if (!file) {
      setError("Select a PDF or image to upload");
      return;
    }
    setUploading(true);
    setResult(null);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/upload", {
        method: "POST",
        body: formData,
        credentials: "include",
      });

      const payload = (await response.json()) as UploadResult & { detail?: string };
      if (!response.ok || !payload.success) {
        throw new Error(payload.detail || payload.error || "Upload failed");
      }
      setResult(payload);
    } catch (err) {
      console.error("Upload error", err);
      setError(
        err instanceof Error ? err.message : "Something went wrong during upload",
      );
    } finally {
      setUploading(false);
    }
  };

  const handleUrlUpload = async () => {
    if (!driveUrl) return;

    setUploading(true);
    setResult(null);
    setError(null);

    try {
      const response = await fetch("/upload-url", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url: driveUrl, assign_to: assignTo }),
        credentials: "include",
      });

      const payload = (await response.json()) as UploadResult;
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || "Upload failed");
      }
      setResult(payload);
      setDriveUrl(""); // Clear input on success
    } catch (err) {
      console.error("URL upload error", err);
      setError(
        err instanceof Error ? err.message : "Something went wrong during URL upload",
      );
    } finally {
      setUploading(false);
    }
  };

  const openLegacyUploader = () => {
    window.location.assign("/legacy#uploads");
  };

  const handleBulkUpload = async () => {
    if (!folderUrl) return;

    setBulkLoading(true);
    setBulkResult(null);
    setBulkError(null);

    // Cumulative totals across all batches
    const totals = {
      contacts_created: 0,
      contacts_updated: 0,
      companies_created: 0,
      companies_linked: 0,
      errors: [] as string[],
      details: [] as Array<{ file: string; contact: string; company: string; status: string }>,
    };

    try {
      let startIndex = 0;
      let hasMore = true;
      let totalFiles = 0;

      while (hasMore) {
        const response = await fetch("/bulk-business-cards", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            folder_url: folderUrl,
            assign_to: assignTo,
            start_index: startIndex,
            batch_size: 10,
          }),
          credentials: "include",
        });

        const payload = (await response.json()) as BulkResult;
        
        if (!response.ok || !payload.success) {
          throw new Error(payload.error || "Bulk processing failed");
        }

        totalFiles = payload.total_files || 0;
        hasMore = payload.has_more || false;
        startIndex = payload.next_index || 0;

        // Accumulate results
        if (payload.batch_results) {
          totals.contacts_created += payload.batch_results.contacts_created;
          totals.contacts_updated += payload.batch_results.contacts_updated;
          totals.companies_created += payload.batch_results.companies_created;
          totals.companies_linked += payload.batch_results.companies_linked;
          totals.errors.push(...payload.batch_results.errors);
          totals.details.push(...payload.batch_results.details);
        }

        // Update UI with progress
        setBulkResult({
          success: true,
          has_more: hasMore,
          total_files: totalFiles,
          processed_so_far: payload.processed_so_far,
          message: payload.message,
          totals: { ...totals },
        });

        // Small delay between batches
        if (hasMore) {
          await new Promise((resolve) => setTimeout(resolve, 500));
        }
      }

      setFolderUrl("");
    } catch (err) {
      console.error("Bulk upload error", err);
      setBulkError(
        err instanceof Error ? err.message : "Something went wrong during bulk processing"
      );
    } finally {
      setBulkLoading(false);
    }
  };

  // Detect if URL is a folder
  const isFolderUrl = driveUrl.includes("/folders/");

  const handleSmartUpload = async () => {
    if (!driveUrl) return;
    
    if (isFolderUrl) {
      // Use bulk processing for folders
      setFolderUrl(driveUrl);
      setBulkLoading(true);
      setBulkResult(null);
      setBulkError(null);

      const totals = {
        contacts_created: 0,
        contacts_updated: 0,
        companies_created: 0,
        companies_linked: 0,
        errors: [] as string[],
        details: [] as Array<{ file: string; contact: string; company: string; status: string }>,
      };

      try {
        let startIndex = 0;
        let hasMore = true;
        let totalFiles = 0;

        while (hasMore) {
          const response = await fetch("/bulk-business-cards", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              folder_url: driveUrl,
              assign_to: assignTo,
              start_index: startIndex,
              batch_size: 10,
            }),
            credentials: "include",
          });

          const payload = (await response.json()) as BulkResult;
          
          if (!response.ok || !payload.success) {
            throw new Error(payload.error || "Bulk processing failed");
          }

          totalFiles = payload.total_files || 0;
          hasMore = payload.has_more || false;
          startIndex = payload.next_index || 0;

          if (payload.batch_results) {
            totals.contacts_created += payload.batch_results.contacts_created;
            totals.contacts_updated += payload.batch_results.contacts_updated;
            totals.companies_created += payload.batch_results.companies_created;
            totals.companies_linked += payload.batch_results.companies_linked;
            totals.errors.push(...payload.batch_results.errors);
            totals.details.push(...payload.batch_results.details);
          }

          setBulkResult({
            success: true,
            has_more: hasMore,
            total_files: totalFiles,
            processed_so_far: payload.processed_so_far,
            message: payload.message,
            totals: { ...totals },
          });

          if (hasMore) {
            await new Promise((resolve) => setTimeout(resolve, 500));
          }
        }

        setDriveUrl("");
      } catch (err) {
        console.error("Bulk upload error", err);
        setBulkError(
          err instanceof Error ? err.message : "Something went wrong during bulk processing"
        );
      } finally {
        setBulkLoading(false);
      }
    } else {
      // Use single file processing
      await handleUrlUpload();
    }
  };

  return (
    <Card sx={{ backgroundColor: "#1e293b", border: "1px solid #334155" }}>
      {(uploading || bulkLoading) && <LinearProgress color="info" />}
      <CardContent sx={{ p: 3 }}>
        {showLegacyLink && (
          <Box display="flex" justifyContent="flex-end" mb={2}>
            <Button
              variant="outlined"
              color="inherit"
              onClick={openLegacyUploader}
              sx={{ textTransform: "none" }}
            >
              Open Legacy Uploader
            </Button>
          </Box>
        )}
        
        {/* Unified Google Drive Import */}
        <Box
          sx={{
            border: "1px solid #10b981",
            borderRadius: 2,
            p: 3,
            display: "flex",
            flexDirection: "column",
            gap: 2,
            backgroundColor: "rgba(16, 185, 129, 0.08)",
          }}
        >
          <Box display="flex" alignItems="center" gap={1}>
            <FolderIcon sx={{ color: "#34d399" }} />
          <Typography sx={{ fontWeight: 600, color: "#f1f5f9" }}>
              Import from Google Drive
            </Typography>
          </Box>
          <Typography sx={{ color: "#94a3b8", fontSize: "0.85rem" }}>
            Paste a Google Drive link to a <strong>file</strong> (MyWay PDF, receipt, business card) 
            or a <strong>folder</strong> of business cards. Folders will be bulk-processed with AI.
          </Typography>
          <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
          <Typography sx={{ color: "#94a3b8", fontSize: "0.85rem" }}>
              Assign imports to:
            </Typography>
            <select
              value={assignTo}
              onChange={(e) => setAssignTo(e.target.value as any)}
              disabled={uploading || bulkLoading}
              style={{
                padding: "8px 10px",
                borderRadius: "6px",
                border: "1px solid #475569",
                backgroundColor: "#0f172a",
                color: "#f1f5f9",
                outline: "none",
              }}
            >
              <option value="jacob@coloradocareassist.com">Jacob</option>
            </select>
          </Box>
          <Box display="flex" gap={2}>
            <input
              type="text"
              placeholder="Paste Google Drive URL (file or folder)..."
              value={driveUrl}
              onChange={(e) => setDriveUrl(e.target.value)}
              disabled={uploading || bulkLoading}
              style={{
                flex: 1,
                padding: "8px 12px",
                borderRadius: "4px",
                border: `1px solid ${isFolderUrl ? "#7c3aed" : "#10b981"}`,
                backgroundColor: "#0f172a",
                color: "#f1f5f9",
                outline: "none",
              }}
            />
            <Button
              variant="contained"
              startIcon={isFolderUrl ? <ContactsIcon /> : <CloudUploadIcon />}
              onClick={handleSmartUpload}
              disabled={!driveUrl || uploading || bulkLoading}
              sx={{
                backgroundColor: isFolderUrl ? "#7c3aed" : "#10b981",
                "&:hover": { backgroundColor: isFolderUrl ? "#6d28d9" : "#059669" },
                textTransform: "none",
                whiteSpace: "nowrap",
              }}
            >
              {uploading || bulkLoading 
                ? "Processing..." 
                : isFolderUrl 
                  ? "Scan All Cards" 
                  : "Fetch & Parse"}
            </Button>
        </Box>

          {isFolderUrl && driveUrl && (
            <Typography sx={{ color: "#a78bfa", fontSize: "0.8rem" }}>
              📁 Folder detected - will bulk process all business card images
            </Typography>
          )}

          {bulkLoading && (
            <Box sx={{ mt: 1 }}>
              <LinearProgress color="secondary" />
              <Typography sx={{ color: "#a78bfa", fontSize: "0.8rem", mt: 1 }}>
                {bulkResult?.processed_so_far != null
                  ? `Processing: ${bulkResult.processed_so_far} of ${bulkResult.total_files} cards...`
                  : "Starting bulk processing..."}
              </Typography>
            </Box>
          )}

          {bulkError && (
            <Alert severity="error" sx={{ mt: 1 }}>
              {bulkError}
            </Alert>
          )}

          {bulkResult && bulkResult.totals && !bulkLoading && (
            <Box sx={{ mt: 2 }}>
              <Alert severity="success" sx={{ mb: 2 }}>
                {bulkResult.message}
              </Alert>
              <Box display="flex" flexWrap="wrap" gap={1} mb={2}>
                <Chip 
                  label={`${bulkResult.totals.contacts_created} Contacts Created`} 
                  color="success" 
                  size="small" 
                />
                <Chip 
                  label={`${bulkResult.totals.contacts_updated} Contacts Updated`} 
                  color="info" 
                  size="small" 
                />
                <Chip 
                  label={`${bulkResult.totals.companies_created} Companies Created`} 
                  color="secondary" 
                  size="small" 
                />
                <Chip 
                  label={`${bulkResult.totals.companies_linked} Companies Linked`} 
                  color="primary" 
                  size="small" 
                />
              </Box>

              {bulkResult.totals.errors.length > 0 && (
                <Alert severity="warning" sx={{ mb: 2 }}>
                  {bulkResult.totals.errors.length} files had errors
                </Alert>
              )}

              {bulkResult.totals.details.length > 0 && (
                <Box sx={{ maxHeight: 200, overflowY: "auto" }}>
                  <Typography sx={{ color: "#e2e8f0", fontWeight: 600, mb: 1, fontSize: "0.9rem" }}>
                    Processed Cards:
                  </Typography>
                  {bulkResult.totals.details.slice(-10).map((d, i) => (
                    <Box key={i} sx={{ p: 1, borderRadius: 1, backgroundColor: "#0f172a", mb: 0.5 }}>
                      <Typography sx={{ color: "#f1f5f9", fontSize: "0.85rem" }}>
                        {d.contact || "Unknown"} {d.company && `@ ${d.company}`}
                      </Typography>
                      <Typography sx={{ color: "#64748b", fontSize: "0.75rem" }}>
                        {d.status}
                      </Typography>
                    </Box>
                  ))}
                  {bulkResult.totals.details.length > 10 && (
                    <Typography sx={{ color: "#64748b", fontSize: "0.8rem", mt: 1 }}>
                      ... and {bulkResult.totals.details.length - 10} more
                    </Typography>
                  )}
                </Box>
              )}
            </Box>
          )}
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", my: 3 }}>
          <Box sx={{ flex: 1, height: "1px", bgcolor: "#334155" }} />
          <Typography sx={{ px: 2, color: "#94a3b8", fontSize: "0.9rem" }}>
            OR upload from device
          </Typography>
          <Box sx={{ flex: 1, height: "1px", bgcolor: "#334155" }} />
        </Box>

        <Box
          sx={{
            border: "1px dashed #475569",
            borderRadius: 2,
            p: 3,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            gap: 2,
            backgroundColor: "rgba(148, 163, 184, 0.05)",
          }}
        >
          {fileIcon || <CloudUploadIcon sx={{ fontSize: 48, color: "#64748b" }} />}
          <div>
            <Typography sx={{ fontWeight: 600, color: "#f1f5f9" }}>
              {file ? file.name : "Choose a PDF or image"}
            </Typography>
            <Typography sx={{ color: "#94a3b8", fontSize: "0.85rem" }}>
              Accepted types: {ACCEPTED_TYPES.join(", ")}
            </Typography>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_TYPES.join(",")}
            onChange={handleFileChange}
            disabled={uploading}
            style={{ display: "none" }}
          />
          <Button
            variant="outlined"
            onClick={handleChooseFile}
            disabled={uploading}
            sx={{
              color: "#94a3b8",
              borderColor: "#475569",
              "&:hover": { borderColor: "#64748b", backgroundColor: "rgba(148, 163, 184, 0.1)" },
              textTransform: "none",
              mb: 1,
            }}
          >
            {file ? `Selected: ${file.name}` : "Choose File"}
          </Button>
          <Button
            variant="contained"
            startIcon={<CloudUploadIcon />}
            onClick={handleUpload}
            disabled={!file || uploading}
            sx={{
              backgroundColor: "#3b82f6",
              "&:hover": { backgroundColor: "#2563eb" },
              textTransform: "none",
            }}
          >
            {uploading ? "Uploading..." : "Upload & Parse"}
          </Button>
        </Box>

        {error && (
          <Alert severity="error" sx={{ mt: 3 }}>
            {error}
          </Alert>
        )}

        {result && (
          <Box sx={{ mt: 3 }}>
            <Alert severity="success" sx={{ mb: 2 }}>
              Successfully processed {result.filename}
            </Alert>
            <Typography sx={{ color: "#e2e8f0", fontWeight: 600 }}>
              Type: {result.type}
            </Typography>
            {result.total_hours != null && (
              <Typography sx={{ color: "#94a3b8" }}>
                Total Hours: {result.total_hours}
              </Typography>
            )}
            {result.count != null && (
              <Typography sx={{ color: "#94a3b8" }}>
                Visits Parsed: {result.count}
              </Typography>
            )}
            {result.contact && (
              <Typography sx={{ color: "#94a3b8" }}>
                Contact: {JSON.stringify(result.contact, null, 2)}
              </Typography>
            )}
            {result.visits && result.visits.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography sx={{ color: "#e2e8f0", fontWeight: 600 }}>
                  Sample Visits
                </Typography>
                <Typography sx={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                  Showing first 3 entries. Full list available from the Visits tab.
                </Typography>
                <pre
                  style={{
                    background: "#0f172a",
                    padding: "12px",
                    borderRadius: "8px",
                    overflowX: "auto",
                    marginTop: "8px",
                  }}
                >
                  {JSON.stringify(result.visits.slice(0, 3), null, 2)}
                </pre>
              </Box>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default UploadPanel;
