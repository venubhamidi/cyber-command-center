// Material UI theme (D-020), on the same tokens App.css already uses, so the two coexist while the
// inventory screen migrates (asset detail ticket 04).
import { createTheme } from "@mui/material/styles";

export const tokens = {
  bg: "#0f1419", panel: "#161c24", line: "#263040", text: "#e6edf3", muted: "#8b98a8",
  accent: "#4f9cf9", warn: "#f5a524",
};

export const theme = createTheme({
  palette: {
    mode: "dark",
    background: { default: tokens.bg, paper: tokens.panel },
    primary: { main: tokens.accent },
    warning: { main: tokens.warn },
    text: { primary: tokens.text, secondary: tokens.muted },
    divider: tokens.line,
  },
  typography: { fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif', fontSize: 13 },
  shape: { borderRadius: 10 },
});
