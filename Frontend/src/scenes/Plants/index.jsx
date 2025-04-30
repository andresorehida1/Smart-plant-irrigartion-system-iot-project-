import React, { useState, useEffect } from "react";
import {
  Box,
  TextField,
  Typography,
  useTheme,
  InputLabel,
  Select,
  FormControl,
  MenuItem,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  RadioGroup,
  Radio,
  FormControlLabel
} from "@mui/material";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import WaterDropOutlinedIcon from "@mui/icons-material/WaterDropOutlined";
import MemoryIcon from "@mui/icons-material/Memory";
import ScheduleIcon from "@mui/icons-material/Schedule";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";

const Plants = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const userData = JSON.parse(localStorage.getItem("user"));
  const username = userData?.username;
  const password = userData?.password;

  const [plants, setPlants] = useState([]);
  const [irrigationModes, setIrrigationModes] = useState({});
  const [openAddDialog, setOpenAddDialog] = useState(false);
  const [newSerial, setNewSerial] = useState("");
  const [newName, setNewName] = useState("");
  const [newType, setNewType] = useState("");

  useEffect(() => {
    let mounted = true;
    const fetchData = async () => {
      const refreshed = await refreshPlants();
      if (mounted) {
        setPlants(refreshed);
        const modes = {};
        refreshed.forEach(p => {
          modes[p.deviceConnectorSerialNumber] = p.irrigationMode || "automated";
        });
        setIrrigationModes(modes);
      }
    };
    fetchData();
    return () => { mounted = false; };
  }, []);

  const generateDevices = (serial) => {
    return `Temperature sensor: ${serial}T\nHumidity sensor: ${serial}H\nSoil sensor: ${serial}M\npH sensor: ${serial}P\nActuator: ${serial}W`;
  };

  const refreshPlants = async () => {
    try {
      const res = await fetch(`http://localhost:8080/user?username=${username}`);
      const data = await res.json();
      localStorage.setItem(
        "user",
        JSON.stringify({ username, password, plants: data.plants })
      );
      const modes = {};
      data.plants.forEach(p => {
        modes[p.deviceConnectorSerialNumber] = p.irrigationMode || "only notifications";
      });
      setIrrigationModes(modes);
      return data.plants;
    } catch (error) {
      console.error("❌ Error refreshing plants:", error);
      return [];
    }
  };

  const handleDelete = async (plantSerial) => {
    try {
      await fetch(
        `http://localhost:8080/deletePlant?username=${username}&plantSerial=${plantSerial}`,
        { method: 'DELETE' }
      );
      const updatedPlants = await refreshPlants();
      setPlants(updatedPlants);
    } catch (error) {
      console.error("❌ Error deleting plant:", error);
    }
  };

  const handleIrrigationModeChange = async (plantSerial, newMode) => {
    const updatedModes = { ...irrigationModes, [plantSerial]: newMode };
    setIrrigationModes(updatedModes);

    try {
      await fetch("http://localhost:8080/changeIrrigationMode", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, plantSerial, newMode })
      });
      const updatedPlants = await refreshPlants();
      setPlants(updatedPlants);
    } catch (error) {
      console.error("❌ Error changing irrigation mode:", error);
    }
  };

  const handleIrrigate = async (plantSerial) => {
    try {
      const res = await fetch("http://localhost:8080/irrigate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, plantSerial })
      });
      const result = await res.json();
      if (res.ok) {
        alert(`✅ Irrigation command sent! (${result.percentage_used}% used)`);
      } else {
        alert("❌ Failed to send irrigation command: " + result.error || result.message);
      }
    } catch (error) {
      console.error("❌ Error sending irrigation command:", error);
      alert("❌ Error sending irrigation command.");
    }
  };

  const handleAdd = async () => {
    const topicPrefix = `${username}/${newSerial}`;
    const newPlant = {
      username,
      plantName: newName,
      plantType: newType,
      deviceConnectorSerialNumber: newSerial,
      waterPumpSerial: `${newSerial}W`,
      sensorList: [
        {
          serialNumber: `${newSerial}T`,
          measureType: "Temperature",
          mqttTopic: `${topicPrefix}/${newSerial}T`
        },
        {
          serialNumber: `${newSerial}H`,
          measureType: "Humidity",
          mqttTopic: `${topicPrefix}/${newSerial}H`
        },
        {
          serialNumber: `${newSerial}M`,
          measureType: "Moisture",
          mqttTopic: `${topicPrefix}/${newSerial}M`
        },
        {
          serialNumber: `${newSerial}P`,
          measureType: "PH",
          mqttTopic: `${topicPrefix}/${newSerial}P`
        }
      ],
      irrigationMode: "only notifications"
    };
    try {
      await fetch("http://localhost:8080/addPlant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newPlant)
      });
      const updatedPlants = await refreshPlants();
      setPlants(updatedPlants);
      setOpenAddDialog(false);
      setNewSerial("");
      setNewName("");
      setNewType("");
    } catch (error) {
      console.error("❌ Error adding plant:", error);
    }
  };

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="PLANTS" subtitle="Welcome To Your Plants" />
      </Box>

      {plants.map((plant, index) => (
        <Box
          key={index}
          display="flex"
          flexDirection="column"
          mb="20px"
          p="10px"
          border="1px solid #ccc"
          borderRadius="5px"
        >
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h5" color={colors.greenAccent[400]}>
              {plant.plantName}
            </Typography>
            <Box>
              <Button
                variant="text"
                color="inherit"
                startIcon={<WaterDropOutlinedIcon />}
                disabled={irrigationModes[plant.deviceConnectorSerialNumber] !== "only notifications"}
                onClick={() => handleIrrigate(plant.deviceConnectorSerialNumber)}
              >
                Irrigate
              </Button>
              <Button
                variant="text"
                color="inherit"
                startIcon={<DeleteOutlineOutlinedIcon />}
                onClick={() => handleDelete(plant.deviceConnectorSerialNumber)}
              >
                Delete
              </Button>
            </Box>
          </Box>
          <Box display="flex" flexWrap="wrap" justifyContent="space-between" mt="10px">
            <Box display="flex" flexDirection="column" flex={1}>
              <TextField label="Serial Number" value={plant.deviceConnectorSerialNumber} disabled sx={{ m: 1 }} />
              <TextField label="Plant Name" value={plant.plantName} disabled sx={{ m: 1 }} />
              <FormControl sx={{ m: 1, minWidth: 120 }}>
                <InputLabel>Plant Type</InputLabel>
                <Select value={plant.plantType} label="Plant Type" disabled>
                  <MenuItem value="cactus">Cactus</MenuItem>
                  <MenuItem value="spider plant">Spider Plant</MenuItem>
                  <MenuItem value="peace lily">Peace Lily</MenuItem>
                </Select>
              </FormControl>
              <TextField
                label="Actuator"
                value={plant.waterPump.serialNumber || "Not defined"}
                disabled
                sx={{ m: 1 }}
              />
            </Box>
            <Box display="flex" flexDirection="column" flex={1}>
              <TextField
                label="Sensors"
                multiline
                rows={4}
                value={plant.sensorList?.map(s => `${s.measureType}: ${s.serialNumber}`).join('\n') || ''}
                fullWidth
                disabled
                sx={{ m: 1 }}
              />
              <FormControl component="fieldset" sx={{ m: 1 }}>
                <Typography variant="subtitle1" sx={{ mb: 1 }}>Irrigation Mode</Typography>
                <RadioGroup
                  row
                  value={irrigationModes[plant.deviceConnectorSerialNumber] || "automated"}
                  onChange={(e) => handleIrrigationModeChange(plant.deviceConnectorSerialNumber, e.target.value)}
                >
                  <FormControlLabel
                    value="automated"
                    control={
                      <Radio
                        icon={<MemoryIcon />}
                        checkedIcon={<MemoryIcon />}
                        sx={{
                          color: colors.grey[300],
                          '&.Mui-checked': { color: colors.greenAccent[400] }
                        }}
                      />
                    }
                    label="Automated"
                  />
                  <FormControlLabel
                    value="scheduled"
                    control={
                      <Radio
                        icon={<ScheduleIcon />}
                        checkedIcon={<ScheduleIcon />}
                        sx={{
                          color: colors.grey[300],
                          '&.Mui-checked': { color: colors.greenAccent[400] }
                        }}
                      />
                    }
                    label="Scheduled"
                  />
                  <FormControlLabel
                    value="only notifications"
                    control={
                      <Radio
                        icon={<NotificationsActiveIcon />}
                        checkedIcon={<NotificationsActiveIcon />}
                        sx={{
                          color: colors.grey[300],
                          '&.Mui-checked': { color: colors.greenAccent[400] }
                        }}
                      />
                    }
                    label="Only Notifications"
                  />
                </RadioGroup>
              </FormControl>
            </Box>
          </Box>
        </Box>
      ))}

      {plants.length < 3 && (
        <Box display="flex" justifyContent="flex-end" m="25px">
          <Button variant="contained" onClick={() => setOpenAddDialog(true)}>
            Add Plant
          </Button>
        </Box>
      )}

      <Dialog open={openAddDialog} onClose={() => setOpenAddDialog(false)}>
        <DialogTitle>Add New Plant</DialogTitle>
        <DialogContent>
          <TextField
            margin="dense"
            label="Serial Number"
            type="text"
            fullWidth
            value={newSerial}
            onChange={(e) => setNewSerial(e.target.value)}
          />
          <TextField
            margin="dense"
            label="Plant Name"
            type="text"
            fullWidth
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
          <FormControl fullWidth margin="dense">
            <InputLabel>Plant Type</InputLabel>
            <Select
              value={newType}
              onChange={(e) => setNewType(e.target.value)}
              label="Plant Type"
            >
              <MenuItem value="cactus">Cactus</MenuItem>
              <MenuItem value="spider plant">Spider Plant</MenuItem>
              <MenuItem value="peace lily">Peace Lily</MenuItem>
            </Select>
          </FormControl>
          {newSerial && (
            <TextField
              margin="dense"
              label="Devices Preview"
              type="text"
              fullWidth
              multiline
              rows={5}
              value={generateDevices(newSerial)}
              disabled
            />
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenAddDialog(false)}>Cancel</Button>
          <Button onClick={handleAdd}>Accept</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Plants;
