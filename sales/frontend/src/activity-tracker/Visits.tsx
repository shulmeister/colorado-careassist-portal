import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Container,
  InputAdornment,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import LocalCarWashIcon from "@mui/icons-material/LocalCarWash";
import SearchIcon from "@mui/icons-material/Search";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { ActivityNav } from "./ActivityNav";

type Visit = {
  id?: string;
  visit_date?: string;
  business_name?: string;
  address?: string;
  city?: string;
  notes?: string;
};

const Visits = () => {
  const [visits, setVisits] = useState<Visit[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    const fetchVisits = async () => {
      try {
        const response = await fetch("api/visits", { credentials: "include" });
        if (response.ok) {
          const data = await response.json();
          setVisits(data);
        }
      } catch (error) {
        console.error("Error fetching visits:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchVisits();
  }, []);

  const filteredVisits = useMemo(() => {
    if (!searchQuery.trim()) return visits;
    const query = searchQuery.toLowerCase();
    return visits.filter(
      (visit) =>
        visit.business_name?.toLowerCase().includes(query) ||
        visit.address?.toLowerCase().includes(query) ||
        visit.city?.toLowerCase().includes(query) ||
        visit.notes?.toLowerCase().includes(query)
    );
  }, [visits, searchQuery]);

  const handleUpload = () => {
    window.location.href = "/activity#activity/uploads";
  };

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <ActivityNav />
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Box display="flex" alignItems="center" gap={1}>
          <LocalCarWashIcon sx={{ color: "#3b82f6", fontSize: "1.5rem" }} />
          <Typography variant="h6" sx={{ fontWeight: 700, color: "#f1f5f9" }}>
            Visits Tracker
          </Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={2}>
          <TextField
            placeholder="Search visits..."
            size="small"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ color: "#64748b" }} />
                </InputAdornment>
              ),
            }}
            sx={{
              width: 250,
              "& .MuiOutlinedInput-root": {
                backgroundColor: "#0f172a",
                "& fieldset": { borderColor: "#334155" },
                "&:hover fieldset": { borderColor: "#475569" },
                "&.Mui-focused fieldset": { borderColor: "#3b82f6" },
              },
              "& .MuiInputBase-input": { color: "#f1f5f9", fontSize: "0.85rem" },
              "& .MuiInputBase-input::placeholder": { color: "#64748b" },
            }}
          />
          <Button
            variant="contained"
            startIcon={<UploadFileIcon />}
            onClick={handleUpload}
            sx={{
              backgroundColor: "#3b82f6",
              "&:hover": { backgroundColor: "#2563eb" },
              textTransform: "none",
              fontSize: "0.85rem",
            }}
          >
            Upload (PDF / Receipt)
          </Button>
        </Box>
      </Box>
      <Card sx={{ backgroundColor: "#1e293b", border: "1px solid #334155" }}>
        <CardContent sx={{ p: 2 }}>
          {loading ? (
            <Typography sx={{ color: "#94a3b8", fontSize: "0.9rem" }}>
              Loading visits...
            </Typography>
          ) : filteredVisits.length > 0 ? (
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell sx={cellHeaderStyles}>Date</TableCell>
                  <TableCell sx={cellHeaderStyles}>Business Name</TableCell>
                  <TableCell sx={cellHeaderStyles}>Address</TableCell>
                  <TableCell sx={cellHeaderStyles}>City</TableCell>
                  <TableCell sx={cellHeaderStyles}>Notes</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredVisits.map((visit) => (
                  <TableRow
                    key={visit.id || `${visit.business_name}-${visit.visit_date}`}
                    sx={{ "&:hover": { backgroundColor: "rgba(255,255,255,0.03)" } }}
                  >
                    <TableCell sx={cellStyles}>
                      {visit.visit_date
                        ? new Date(visit.visit_date + 'T12:00:00').toLocaleDateString()
                        : "-"}
                    </TableCell>
                    <TableCell sx={cellStyles}>{visit.business_name}</TableCell>
                    <TableCell sx={mutedCellStyles}>{visit.address || "-"}</TableCell>
                    <TableCell sx={mutedCellStyles}>{visit.city || "-"}</TableCell>
                    <TableCell sx={mutedCellStyles}>{visit.notes || "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : searchQuery.trim() ? (
            <Box sx={{ textAlign: "center", py: 4 }}>
              <Typography sx={{ color: "#64748b", fontSize: "0.9rem" }}>
                No visits matching "{searchQuery}"
              </Typography>
            </Box>
          ) : (
            <Box sx={{ textAlign: "center", py: 4 }}>
              <Typography sx={{ color: "#64748b", fontSize: "0.9rem", mb: 2 }}>
                No visits recorded yet.
              </Typography>
              <Button
                variant="outlined"
                startIcon={<UploadFileIcon />}
                onClick={handleUpload}
                sx={{
                  color: "#3b82f6",
                  borderColor: "#3b82f6",
                  "&:hover": { backgroundColor: "rgba(59, 130, 246, 0.05)" },
                  textTransform: "none",
                }}
              >
                Upload Your First Visit PDF
              </Button>
            </Box>
          )}
        </CardContent>
      </Card>
    </Container>
  );
};

const cellHeaderStyles = {
  color: "#f1f5f9",
  fontWeight: 600,
  fontSize: "0.85rem",
} as const;

const cellStyles = { color: "#f1f5f9", fontSize: "0.8rem" } as const;
const mutedCellStyles = { color: "#94a3b8", fontSize: "0.8rem" } as const;

export default Visits;
export { Visits };

