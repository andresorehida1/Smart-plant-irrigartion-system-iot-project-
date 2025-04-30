import { Box, IconButton, Button, useTheme, Badge, Menu, MenuItem, Typography, Divider } from "@mui/material";
import { colorModeContext, tokens } from "../../theme";
import { useContext, useState, useEffect, useRef } from "react";
import LightModeOutlinedIcon from "@mui/icons-material/LightModeOutlined";
import DarkModeOutlinedIcon from "@mui/icons-material/DarkModeOutlined";
import LogoutOutlinedIcon from '@mui/icons-material/LogoutOutlined';
import AccountCircleOutlinedIcon from '@mui/icons-material/AccountCircleOutlined';
import YardOutlinedIcon from '@mui/icons-material/YardOutlined';
import QueryStatsOutlinedIcon from '@mui/icons-material/QueryStatsOutlined';
import NotificationsNoneOutlinedIcon from '@mui/icons-material/NotificationsNoneOutlined';
import DeleteSweepOutlinedIcon from '@mui/icons-material/DeleteSweepOutlined';
import { useNavigate } from "react-router-dom";

const TopBar = () => {
  const theme = useTheme();
  const colorMode = useContext(colorModeContext);
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const wsRef = useRef(null);

  // Obtener usuario actual desde localStorage
  const storedUser = localStorage.getItem("user");
  const currentUser = storedUser ? JSON.parse(storedUser).username : null;

  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8765');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log("✅ Connected to WebSocket server for alerts & irrigation");
        if (currentUser) {
          ws.send(JSON.stringify({ type: 'identify', username: currentUser }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // Determinar usuario objetivo: data.username o data.owner
          const msgUser = data.username || data.owner;
          // Filtrar si no es para el usuario actual
          if (msgUser && msgUser !== currentUser) {
            return;
          }

          if (data.alert && data.timestamp) {
            const alertMessage = `🔔 ${data.alert} (${new Date(data.timestamp).toLocaleTimeString()})`;
            setNotifications(prev => [alertMessage, ...prev]);
          } else if (data.type === "irrigation" && data.percentage != null && data.timestamp) {
            const irrMessage = `💧 Irrigated ${data.percentage}% on plant ${data.plant} (${new Date(data.timestamp).toLocaleTimeString()})`;
            setNotifications(prev => [irrMessage, ...prev]);
          }
        } catch (error) {
          console.error("Error parsing WebSocket message:", error);
        }
      };

      ws.onclose = () => {
        console.warn("⚠️ WebSocket closed. Reconnecting...");
        setTimeout(connectWebSocket, 3000);
      };

      ws.onerror = (error) => {
        console.error("🚨 WebSocket error:", error);
        ws.close();
      };
    };

    connectWebSocket();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [currentUser]);

  const handleNotificationsClick = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => setAnchorEl(null);
  const handleClearNotifications = () => { setNotifications([]); setAnchorEl(null); };

  return (
    <Box display="flex" justifyContent="space-between" p={2}>
      <Box display="flex" borderRadius="3px">
        <Button onClick={() => navigate("/profile")} variant="text" color="inherit" startIcon={<AccountCircleOutlinedIcon />}>Profile</Button>
        <Button onClick={() => navigate("/plants")} variant="text" color="inherit" startIcon={<YardOutlinedIcon />}>Plants</Button>
        <Button onClick={() => navigate("/")} variant="text" color="inherit" startIcon={<QueryStatsOutlinedIcon />}>Dashboard</Button>
      </Box>

      <Box display="flex" alignItems="center">
        <IconButton onClick={handleNotificationsClick} color="inherit">
          <Badge badgeContent={notifications.length} color="error">
            <NotificationsNoneOutlinedIcon />
          </Badge>
        </IconButton>

        <Menu anchorEl={anchorEl} open={Boolean(anchorEl)} onClose={handleClose}
              PaperProps={{ style: { maxHeight: 400, width: '450px' } }}>
          {notifications.length === 0 ? (
            <MenuItem onClick={handleClose}>No new notifications</MenuItem>
          ) : (
            <> {notifications.map((notif, index) => (
              <MenuItem key={index} onClick={handleClose} style={{ whiteSpace: 'normal', wordWrap: 'break-word' }}>
                <Typography variant="body2">{notif}</Typography>
              </MenuItem>
            ))}
            <Divider />
            <MenuItem onClick={handleClearNotifications}>
              <DeleteSweepOutlinedIcon fontSize="small" style={{ marginRight: 8 }} /> Clear Notifications
            </MenuItem>
            </>
          )}
        </Menu>

        <IconButton onClick={colorMode.toggleColorMode} color="inherit">
          {theme.palette.mode === "dark" ? <DarkModeOutlinedIcon/> : <LightModeOutlinedIcon/>}
        </IconButton>

        <IconButton onClick={() => { localStorage.removeItem("user"); navigate("/", { replace: true }); window.location.reload(); }} color="inherit">
          <LogoutOutlinedIcon />
        </IconButton>
      </Box>
    </Box>
  );
};

export default TopBar;
