// The page frame every screen renders inside: theme, top bar with the platform health, content area.
import type { ReactNode } from "react";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import AppBar from "@mui/material/AppBar";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import Container from "@mui/material/Container";
import Chip from "@mui/material/Chip";
import Box from "@mui/material/Box";
import type { Health } from "./api";
import { theme } from "./theme";

export function Shell({ health, children }: { health: Health | null; children: ReactNode }) {
  const label = health
    ? `API ${health.status} · db ${health.database} · login ${health.auth_provider} · model ${health.llm_provider} · harness ${health.harness_version}`
    : "API unreachable";
  const color = health?.status === "ok" ? "success" : "error";
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar position="static" color="transparent" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar sx={{ gap: 2 }}>
          <Box sx={{ flexGrow: 1 }}>
            <Typography variant="h6" component="h1" sx={{ fontSize: 20, fontWeight: 600, lineHeight: 1.2 }}>
              Cyber Command Center
            </Typography>
            <Typography variant="body2" color="text.secondary">Enterprise Asset Intelligence</Typography>
          </Box>
          <Chip size="small" variant="outlined" color={color} label={label} sx={{ fontSize: 12 }} />
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: 3 }}>{children}</Container>
    </ThemeProvider>
  );
}
