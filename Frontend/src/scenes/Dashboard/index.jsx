import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  useTheme,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Button
} from "@mui/material";
import Header from "../../components/Header";
import { tokens } from "../../theme";
import LineChart from "../../components/LineChart";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8080";

const chartList = [
  { title: "Temperature Over Time", id: "temperature" },
  { title: "Humidity Over Time", id: "humidity" },
  { title: "PH Over Time", id: "ph" },
  { title: "Soil Moisture Over Time", id: "moisture" },
  { title: "Historical Analysis", id: "historical" },
  { title: "Real Time Analysis", id: "realtime" },
];

const Dashboard = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const userData = JSON.parse(localStorage.getItem("user"));
  const username = userData?.username;
  const plants = userData?.plants || [];

  const [selectedPlant, setSelectedPlant] = useState(
    plants[0]?.deviceConnectorSerialNumber || ""
  );
  const [irrigationMode, setIrrigationMode] = useState("");
  const [mainChart, setMainChart] = useState("temperature");
  const [tankStatus, setTankStatus] = useState({ value: null, time: null });

  useEffect(() => {
    const plantObj = plants.find(
      (p) => p.deviceConnectorSerialNumber === selectedPlant
    );
    setIrrigationMode(plantObj?.irrigationMode || "");
  }, [selectedPlant, plants]);

  const handleChartClick = (chartId) => {
    setMainChart(chartId);
  };

  const handleIrrigate = async () => {
    console.log("Irrigate clicked", { username, selectedPlant });
    if (!selectedPlant || !username) {
      alert("❌ No plant selected for irrigation.");
      return;
    }
    try {
      const res = await fetch(`${BACKEND_URL}/irrigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, plantSerial: selectedPlant }),
      });
      console.log("/irrigate status", res.status);
      const result = await res.json();
      console.log("/irrigate payload", result);
      if (res.ok) {
        const pct = result.percentage_used ?? "";
        alert(`✅ Irrigation command sent${pct ? ` (${pct}% used)` : ""}`);
      } else {
        alert(
          "❌ Failed to send irrigation command: " + (result.error || result.message)
        );
      }
    } catch (error) {
      console.error("Error triggering irrigation:", error);
      alert("❌ Error sending irrigation command.");
    }
  };

  useEffect(() => {
    if (!selectedPlant || !username) return;

    const fetchTankStatus = async () => {
      try {
        const res = await fetch(
          `${BACKEND_URL}/get_latest_tank_status?username=${username}&plant=${selectedPlant}`
        );
        const data = await res.json();
        if (data?.value != null) {
          setTankStatus({ value: data.value, time: data.time });
        }
      } catch (error) {
        console.error("Error fetching tank status:", error);
      }
    };

    fetchTankStatus();
    const interval = setInterval(fetchTankStatus, 60000);
    return () => clearInterval(interval);
  }, [selectedPlant, username]);

  if (plants.length === 0) {
    return (
      <Box m="20px">
        <Header title="DASHBOARD" subtitle="Welcome To Your Metrics Dashboard" />
        <Typography variant="h5" mt={4}>
          🚫 You have no plants, add one!
        </Typography>
      </Box>
    );
  }

  const selectedPlantObj = plants.find(
    (p) => p.deviceConnectorSerialNumber === selectedPlant
  );

  return (
    <Box m="20px">
      <Box display="flex" justifyContent="space-between" alignItems="center">
        <Header title="DASHBOARD" subtitle="Welcome To Your Metrics Dashboard" />
        <FormControl sx={{ minWidth: 200 }}>
          <InputLabel>Select Plant</InputLabel>
          <Select
            value={selectedPlant}
            label="Select Plant"
            onChange={(e) => setSelectedPlant(e.target.value)}
          >
            {plants.map((p) => (
              <MenuItem key={p.deviceConnectorSerialNumber} value={p.deviceConnectorSerialNumber}>
                {p.plantName}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      <Box mt="20px" display="flex" alignItems="center" gap="20px">
        <Box>
          <Typography variant="h6">💧 Water Tank Level:</Typography>
          {tankStatus.value != null ? (
            <Typography variant="body1">
              {tankStatus.value}% (Last updated: {" "}
              {new Date(tankStatus.time).toLocaleString()})
            </Typography>
          ) : (
            <Typography variant="body2" color="error">
              No tank data available for this plant.
            </Typography>
          )}
        </Box>
        <Button
          variant="contained"
          color="primary"
          onClick={handleIrrigate}
          disabled={irrigationMode !== "only notifications"}
          sx={{ height: "fit-content", mt: 2 }}
        >
          Irrigate
        </Button>
      </Box>

      <Box
        display="grid"
        gridTemplateColumns="repeat(12, 1fr)"
        gridAutoRows="130px"
        gap="20px"
        mt="20px"
        overflow="hidden"
      >
        {chartList.map((chart) => {
          const isMain = mainChart === chart.id;
          const viewType = ["historical", "realtime"].includes(chart.id)
            ? chart.id
            : "raw";
          return (
            <Box
              key={chart.id}
              onClick={() => handleChartClick(chart.id)}
              gridColumn={isMain ? "span 9" : "span 3"}
              gridRow={isMain ? "span 3" : "span 2"}
              backgroundColor={colors.primary[700]}
              borderRadius="25px"
              sx={{ cursor: "pointer", transition: "all 0.3s ease", overflow: "hidden" }}
            >
              <Box
                mt="25px"
                p="0 30px"
                display="flex"
                justifyContent="space-between"
                alignItems="center"
              >
                <Typography variant="h5" fontWeight="600" color={colors.grey[100]}>
                  {chart.title}
                </Typography>
              </Box>
              <Box height="75%" ml="0px" overflow="hidden">
                <LineChart
                  isDashboard={true}
                  view={viewType}
                  metric={chart.id}
                  plant={selectedPlant}
                  username={username}
                />
              </Box>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};

export default Dashboard;
