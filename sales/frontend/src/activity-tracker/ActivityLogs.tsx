import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Chip,
  Container,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemText,
  TextField,
  Typography,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import SearchIcon from "@mui/icons-material/Search";
import EventIcon from "@mui/icons-material/Event";

import { ActivityNav } from "./ActivityNav";

type Activity = {
  type: string;
  description: string;
  date: string;
  details?: Record<string, unknown>;
};

const typeLabels: Record<string, string> = {
  visit: "Visit",
  time_entry: "Time Entry",
  contact: "Contact",
};

const typeColors: Record<string, string> = {
  visit: "#34d399",
  time_entry: "#60a5fa",
  contact: "#f472b6",
};

export const ActivityLogs = () => {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const fetchActivities = async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/dashboard/recent-activity?limit=50", {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to load activity logs");
      }
      const data = (await response.json()) as Activity[];
      setActivities(data);
    } catch (error) {
      console.error("Error loading activity", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchActivities();
  }, []);

  const filteredActivities = useMemo(() => {
    if (!searchQuery.trim()) return activities;
    const query = searchQuery.toLowerCase();
    return activities.filter(
      (activity) =>
        activity.description?.toLowerCase().includes(query) ||
        activity.type?.toLowerCase().includes(query) ||
        (activity.details && JSON.stringify(activity.details).toLowerCase().includes(query))
    );
  }, [activities, searchQuery]);

  const grouped = useMemo(() => {
    return filteredActivities.reduce<Record<string, Activity[]>>((acc, activity) => {
      const dateKey = new Date(activity.date).toLocaleDateString();
      acc[dateKey] = acc[dateKey] || [];
      acc[dateKey].push(activity);
      return acc;
    }, {});
  }, [filteredActivities]);

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <ActivityNav />
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6" sx={{ fontWeight: 700, color: "#f1f5f9" }}>
          Recent Activity
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <TextField
            placeholder="Search activity..."
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
          <IconButton onClick={fetchActivities} disabled={loading} aria-label="Refresh logs">
            <RefreshIcon sx={{ color: "#94a3b8" }} />
          </IconButton>
        </Box>
      </Box>

      <Card sx={{ backgroundColor: "#1e293b", border: "1px solid #334155" }}>
        <CardContent>
          {loading ? (
            <Typography sx={{ color: "#94a3b8" }}>Loading activity…</Typography>
          ) : filteredActivities.length === 0 ? (
            <Typography sx={{ color: "#94a3b8" }}>
              {searchQuery.trim()
                ? `No activity matching "${searchQuery}"`
                : "No recent activity recorded. Upload visits or log hours to populate this feed."}
            </Typography>
          ) : (
            Object.entries(grouped).map(([date, entries]) => (
              <Box key={date} sx={{ mb: 4 }}>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <EventIcon sx={{ color: "#38bdf8" }} />
                  <Typography sx={{ color: "#e2e8f0", fontWeight: 600 }}>{date}</Typography>
                </Box>
                <List>
                  {entries.map((activity, index) => (
                    <ListItem
                      key={`${activity.date}-${activity.description}-${index}`}
                      sx={{
                        backgroundColor: "rgba(15, 23, 42, 0.6)",
                        borderRadius: "8px",
                        mb: 1,
                        border: "1px solid rgba(148, 163, 184, 0.12)",
                      }}
                    >
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={1}>
                            <Chip
                              label={typeLabels[activity.type] || activity.type}
                              size="small"
                              sx={{
                                backgroundColor:
                                  typeColors[activity.type] || "rgba(148,163,184,0.3)",
                                color: "#0f172a",
                              }}
                            />
                            <Typography sx={{ color: "#f8fafc", fontWeight: 600 }}>
                              {activity.description}
                            </Typography>
                          </Box>
                        }
                        secondary={
                          <Typography sx={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                            {new Date(activity.date).toLocaleTimeString()} •
                            {" "}
                            {activity.details && JSON.stringify(activity.details)}
                          </Typography>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </Box>
            ))
          )}
        </CardContent>
      </Card>
    </Container>
  );
};

export default ActivityLogs;
