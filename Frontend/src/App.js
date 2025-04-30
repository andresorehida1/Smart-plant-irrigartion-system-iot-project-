import { useEffect } from "react";
import { colorModeContext, useMode } from "./theme";
import { CssBaseline, ThemeProvider } from "@mui/material";
import TopBar from "./scenes/global/TopBar";
import LoginForm from "./components/LoginForm/LoginForm";
import RegisterForm from "./components/RegisterForm/RegisterForm";
import RegisterLayout from "./components/RegisterForm/RegisterLayout";
import Profile from "./scenes/Profile";
import Plants from "./scenes/Plants";
import Dashboard from "./scenes/Dashboard";
import LoginLayout from "./components/LoginForm/LoginLayout";
import { Route, Routes, Navigate, useLocation, useNavigate } from "react-router-dom";

function RequireAuth({ children }) {
  const isAuthenticated = localStorage.getItem("user");
  const location = useLocation();
  return isAuthenticated ? children : <Navigate to="/" state={{ from: location }} replace />;
}

function App() {
  const [theme, colorMode] = useMode();
  const isAuthenticated = localStorage.getItem("user");
  const navigate = useNavigate();

  useEffect(() => {
    const validateUser = async () => {
      const user = JSON.parse(localStorage.getItem("user"));
      if (!user?.username) return;

      try {
        const res = await fetch(`http://localhost:8080/user?username=${user.username}`);
        if (!res.ok) {
          localStorage.removeItem("user");
          navigate("/", { replace: true });
        }
      } catch (error) {
        console.error("Error validating user session:", error);
      }
    };

    validateUser();
  }, [navigate]);

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="/" element={<LoginLayout><LoginForm /></LoginLayout>} />
        <Route path="/register" element={<RegisterLayout><RegisterForm /></RegisterLayout>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }

  return (
    <colorModeContext.Provider value={colorMode}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <div className="app">
          <main className="content">
            <TopBar />
            <Routes>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<RequireAuth><Dashboard /></RequireAuth>} />
              <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
              <Route path="/plants" element={<RequireAuth><Plants /></RequireAuth>} />
            </Routes>
          </main>
        </div>
      </ThemeProvider>
    </colorModeContext.Provider>
  );
}

export default App;