import { Box, Container, Typography } from "@mui/material";

import { ActivityNav } from "./ActivityNav";
import { UploadPanel } from "./UploadPanel";

export const Uploads = () => {
  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <ActivityNav />
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "#f1f5f9" }}>
            Upload Visits, Receipts, or Business Cards
          </Typography>
          <Typography sx={{ color: "#94a3b8", fontSize: "0.9rem" }}>
            Upload MyWay route PDFs (visits + mileage), time tracking PDFs, receipt photos/PDFs (expenses),
            or business card photos. We’ll parse them automatically and update your tracker and reimbursements.
          </Typography>
        </Box>
      </Box>

      <UploadPanel />
    </Container>
  );
};

export default Uploads;
