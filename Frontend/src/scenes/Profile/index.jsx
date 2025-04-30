import React, { useState, useEffect } from "react";
import { 
  Box, 
  TextField, 
  Button, 
  Checkbox, 
  FormControlLabel, 
  Dialog, 
  DialogTitle, 
  DialogContent, 
  DialogActions 
} from "@mui/material";
import Header from "../../components/Header";
import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import { useNavigate } from "react-router-dom";

const Profile = () => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const navigate = useNavigate();

  useEffect(() => {
    const userData = JSON.parse(localStorage.getItem("user"));
    if (userData) {
      setUsername(userData.username);
      setPassword(userData.password);
    }
  }, []);

  const handleDeleteAccount = async () => {
    try {
      await fetch(`http://localhost:8080/deleteAccount?username=${username}`, {
        method: "DELETE",
      });
      localStorage.removeItem("user");
      navigate("/");
      window.location.reload();
    } catch (error) {
      console.error("❌ Error deleting account:", error);
    }
  };

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="PROFILE" subtitle="Welcome To Your Profile Information" />
      </Box>

      <Box display="flex" justifyContent="space-between" m="25px">
        <TextField
          label="Username"
          value={username}
          disabled
n          fullWidth
        />
      </Box>

      <Box display="flex" alignItems="center" m="25px">
        <TextField
          label="Password"
          type={showPassword ? "text" : "password"}
          value={password}
          fullWidth
          InputProps={{ readOnly: true }}
        />
        <FormControlLabel
          control={
            <Checkbox
              checked={showPassword}
              onChange={(e) => setShowPassword(e.target.checked)}
            />
          }
          label="Show Password"
          sx={{ ml: 2 }}
        />
      </Box>

      <Box display="flex" gap={2} m="25px">
        <Button
          variant="outlined"
          color="error"
          endIcon={<DeleteOutlineOutlinedIcon />}
          onClick={handleDeleteAccount}
        >
          Delete Account
        </Button>
      </Box>
    </Box>
  );
};

export default Profile;
