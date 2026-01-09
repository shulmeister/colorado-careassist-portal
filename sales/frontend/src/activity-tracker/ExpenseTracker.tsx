import { useEffect, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  Container,
  Grid,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Chip,
  Paper,
  CircularProgress,
  Alert,
  Button,
  IconButton,
  ButtonGroup,
} from "@mui/material";
import { ActivityNav } from "./ActivityNav";
import ReceiptIcon from "@mui/icons-material/Receipt";
import DirectionsCarIcon from "@mui/icons-material/DirectionsCar";
import AttachMoneyIcon from "@mui/icons-material/AttachMoney";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";

type ExpenseItem = {
  type: "expense" | "mileage";
  date: string;
  description: string;
  amount: number;
  status?: string;
  url?: string;
  miles?: number;
  rate?: number;
};

type UserSummary = {
  display_name: string;
  total_miles: number;
  mileage_amount: number;
  expenses_amount: number;
  grand_total: number;
  items: ExpenseItem[];
};

type PayPeriodSummary = {
  period: {
    start: string;
    end: string;
    index: number;
    offset: number;
    is_current: boolean;
    is_completed: boolean;
    total_periods: number;
    label: string;
  };
  users: Record<string, UserSummary>;
};

export const ExpenseTracker = () => {
  const [data, setData] = useState<PayPeriodSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [periodOffset, setPeriodOffset] = useState(-1); // Default to previous period (the one just completed)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const response = await fetch(`/api/expenses/pay-period-summary?period_offset=${periodOffset}`, {
          credentials: "include",
        });
        if (!response.ok) {
          throw new Error("Failed to fetch expense summary");
        }
        const result = await response.json();
        setData(result);
      } catch (err) {
        console.error("Error fetching expenses:", err);
        setError("Failed to load expense data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [periodOffset]);

  const goToPreviousPeriod = () => {
    // Don't go before period 1
    if (data && data.period.index > 1) {
      setPeriodOffset((prev) => prev - 1);
    }
  };

  const goToNextPeriod = () => {
    // Don't go past current period
    if (periodOffset < 0) {
      setPeriodOffset((prev) => prev + 1);
    }
  };

  const goToCurrentPeriod = () => {
    setPeriodOffset(0);
  };

  const goToLastCompletedPeriod = () => {
    setPeriodOffset(-1);
  };

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: 3, textAlign: "center" }}>
        <CircularProgress />
      </Container>
    );
  }

  if (error || !data) {
    return (
      <Container maxWidth="xl" sx={{ py: 3 }}>
        <ActivityNav />
        <Alert severity="error">{error || "No data available"}</Alert>
      </Container>
    );
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
    });
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(amount);
  };

  // Calculate payroll totals for display
  const payrollTotal = Object.values(data.users).reduce(
    (sum, user) => sum + user.grand_total,
    0
  );

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <ActivityNav />
      <Box mb={4}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2}>
          <Box>
            <Typography
              variant="h5"
              component="h1"
              gutterBottom
              sx={{ color: "#f1f5f9", fontWeight: 600 }}
            >
              Expense Tracker
            </Typography>
            <Box display="flex" alignItems="center" gap={2}>
              <Typography sx={{ color: "#94a3b8" }}>
                Pay Period {data.period.index}: {formatDate(data.period.start)} -{" "}
                {formatDate(data.period.end)}
              </Typography>
              {data.period.is_completed && (
                <Chip
                  icon={<CheckCircleIcon />}
                  label="READY FOR PAYROLL"
                  color="success"
                  size="small"
                  sx={{ fontWeight: 600 }}
                />
              )}
              {data.period.is_current && (
                <Chip
                  label="In Progress"
                  color="warning"
                  size="small"
                  variant="outlined"
                />
              )}
            </Box>
          </Box>

          {/* Period Navigation */}
          <Box display="flex" flexDirection="column" alignItems="flex-end" gap={1}>
            <Box display="flex" alignItems="center" gap={1}>
              <IconButton
                onClick={goToPreviousPeriod}
                disabled={data.period.index <= 1}
                sx={{ color: "#94a3b8", "&:disabled": { color: "#475569" } }}
                size="small"
              >
                <ChevronLeftIcon />
              </IconButton>
              <Typography sx={{ color: "#f1f5f9", minWidth: 80, textAlign: "center" }}>
                Period {data.period.index}
              </Typography>
              <IconButton
                onClick={goToNextPeriod}
                disabled={periodOffset >= 0}
                sx={{ color: "#94a3b8", "&:disabled": { color: "#475569" } }}
                size="small"
              >
                <ChevronRightIcon />
              </IconButton>
            </Box>
            <ButtonGroup size="small" variant="outlined">
              <Button
                onClick={goToLastCompletedPeriod}
                sx={{
                  color: periodOffset === -1 ? "#22c55e" : "#94a3b8",
                  borderColor: periodOffset === -1 ? "#22c55e" : "#475569",
                  "&:hover": { borderColor: "#22c55e", color: "#22c55e" },
                }}
              >
                Last Completed
              </Button>
              <Button
                onClick={goToCurrentPeriod}
                sx={{
                  color: periodOffset === 0 ? "#3b82f6" : "#94a3b8",
                  borderColor: periodOffset === 0 ? "#3b82f6" : "#475569",
                  "&:hover": { borderColor: "#3b82f6", color: "#3b82f6" },
                }}
              >
                Current
              </Button>
            </ButtonGroup>
          </Box>
        </Box>

        {/* Payroll Summary Banner */}
        {data.period.is_completed && (
          <Paper
            sx={{
              mt: 3,
              p: 2,
              bgcolor: "rgba(34, 197, 94, 0.1)",
              border: "2px solid #22c55e",
              borderRadius: 2,
            }}
          >
            <Box display="flex" justifyContent="space-between" alignItems="center" flexWrap="wrap" gap={2}>
              <Box>
                <Typography variant="h6" sx={{ color: "#22c55e", fontWeight: 700 }}>
                  Payroll Ready
                </Typography>
                <Typography sx={{ color: "#94a3b8" }}>
                  Period {data.period.index} ({formatDate(data.period.start)} - {formatDate(data.period.end)}) is complete
                </Typography>
              </Box>
              <Box textAlign="right">
                <Typography variant="caption" sx={{ color: "#94a3b8" }}>
                  Total Reimbursement Due
                </Typography>
                <Typography variant="h4" sx={{ color: "#22c55e", fontWeight: 700 }}>
                  {formatCurrency(payrollTotal)}
                </Typography>
              </Box>
            </Box>
          </Paper>
        )}
      </Box>

      <Grid container spacing={3}>
        {Object.entries(data.users).map(([email, summary]) => {
          // Use display_name from API, fallback to parsing email
          const displayName = summary.display_name || email.split("@")[0].charAt(0).toUpperCase() + email.split("@")[0].slice(1);

          return (
            <Grid item xs={12} lg={6} key={email}>
              <Card
                sx={{
                  backgroundColor: "#1e293b",
                  border: "1px solid #334155",
                  height: "100%",
                }}
              >
                <CardContent>
                  <Box
                    display="flex"
                    justifyContent="space-between"
                    alignItems="center"
                    mb={3}
                  >
                    <Typography
                      variant="h6"
                      sx={{ color: "#f1f5f9", fontWeight: 600 }}
                    >
                      {displayName}
                    </Typography>
                    <Chip
                      label={formatCurrency(summary.grand_total)}
                      color="success"
                      sx={{ fontSize: "1.1rem", fontWeight: "bold" }}
                    />
                  </Box>

                  <Grid container spacing={2} mb={3}>
                    <Grid item xs={6}>
                      <Paper
                        sx={{
                          p: 2,
                          bgcolor: "rgba(15, 23, 42, 0.6)",
                          border: "1px solid #334155",
                        }}
                      >
                        <Box display="flex" alignItems="center" gap={1} mb={1}>
                          <DirectionsCarIcon
                            sx={{ color: "#38bdf8", fontSize: 20 }}
                          />
                          <Typography
                            variant="body2"
                            sx={{ color: "#94a3b8" }}
                          >
                            Mileage
                          </Typography>
                        </Box>
                        <Typography
                          variant="h6"
                          sx={{ color: "#f1f5f9", fontWeight: 600 }}
                        >
                          {summary.total_miles} mi
                        </Typography>
                        <Typography variant="caption" sx={{ color: "#64748b" }}>
                          {formatCurrency(summary.mileage_amount)}
                        </Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={6}>
                      <Paper
                        sx={{
                          p: 2,
                          bgcolor: "rgba(15, 23, 42, 0.6)",
                          border: "1px solid #334155",
                        }}
                      >
                        <Box display="flex" alignItems="center" gap={1} mb={1}>
                          <ReceiptIcon
                            sx={{ color: "#f472b6", fontSize: 20 }}
                          />
                          <Typography
                            variant="body2"
                            sx={{ color: "#94a3b8" }}
                          >
                            Expenses
                          </Typography>
                        </Box>
                        <Typography
                          variant="h6"
                          sx={{ color: "#f1f5f9", fontWeight: 600 }}
                        >
                          {formatCurrency(summary.expenses_amount)}
                        </Typography>
                        <Typography variant="caption" sx={{ color: "#64748b" }}>
                          {summary.items.filter((i) => i.type === "expense")
                            .length}{" "}
                          items
                        </Typography>
                      </Paper>
                    </Grid>
                  </Grid>

                  <Typography
                    variant="subtitle2"
                    sx={{ color: "#94a3b8", mb: 2 }}
                  >
                    Details
                  </Typography>
                  <Box
                    sx={{
                      maxHeight: 400,
                      overflow: "auto",
                      "&::-webkit-scrollbar": { width: 8 },
                      "&::-webkit-scrollbar-thumb": {
                        bgcolor: "#334155",
                        borderRadius: 4,
                      },
                    }}
                  >
                    {summary.items.length > 0 ? (
                      <Table size="small">
                        <TableBody>
                          {summary.items.map((item, idx) => (
                            <TableRow
                              key={idx}
                              sx={{
                                "&:last-child td, &:last-child th": {
                                  border: 0,
                                },
                              }}
                            >
                              <TableCell sx={{ color: "#cbd5e1", borderBottom: "1px solid #334155" }}>
                                <Box display="flex" flexDirection="column">
                                  <span style={{ fontWeight: 500 }}>
                                    {formatDate(item.date)}
                                  </span>
                                  <span
                                    style={{
                                      fontSize: "0.75rem",
                                      color: "#64748b",
                                    }}
                                  >
                                    {item.type === "mileage"
                                      ? "Mileage Log"
                                      : "Receipt"}
                                  </span>
                                </Box>
                              </TableCell>
                              <TableCell sx={{ color: "#cbd5e1", borderBottom: "1px solid #334155" }}>
                                {item.url && (item.url.startsWith("http://") || item.url.startsWith("https://")) ? (
                                  <a
                                    href={item.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                      color: "#38bdf8",
                                      textDecoration: "none",
                                    }}
                                  >
                                    {item.description || "View Receipt"}
                                  </a>
                                ) : (
                                  item.description
                                )}
                              </TableCell>
                              <TableCell align="right" sx={{ color: "#f1f5f9", fontWeight: 500, borderBottom: "1px solid #334155" }}>
                                {formatCurrency(item.amount || 0)}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    ) : (
                      <Typography
                        variant="body2"
                        sx={{ color: "#64748b", textAlign: "center", py: 2 }}
                      >
                        No entries for this period
                      </Typography>
                    )}
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          );
        })}
      </Grid>
    </Container>
  );
};

export default ExpenseTracker;
