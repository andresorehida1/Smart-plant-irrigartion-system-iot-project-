import React, { useState, useEffect } from "react";
import { ResponsiveLine } from "@nivo/line";
import { Box, useTheme } from "@mui/material";
import { tokens } from "../theme";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8080";

const METRICS = ["temperature", "humidity", "moisture", "ph"];
const COLORS = {
  temperature: "hsl(10, 70%, 50%)",
  humidity:    "hsl(200, 70%, 50%)",
  moisture:    "hsl(90, 70%, 50%)",
  ph:          "hsl(320, 70%, 50%)"
};

const LineChart = ({
  isDashboard = false,
  view = "raw",
  metric = "temperature",
  username,
  plant
}) => {
  const theme = useTheme();
  const t = tokens(theme.palette.mode);

  const [data, setData] = useState([]);
  const [noData, setNoData] = useState(false);

  useEffect(() => {
    if (!username || !plant) return;

    const fetchData = async () => {
      let url;
      if (view === "raw") {
        url = `${BACKEND_URL}/get_plot?username=${username}&plant=${plant}&graph=${metric}`;
      } else if (view === "historical") {
        url = `${BACKEND_URL}/get_historical_trends?username=${username}&plant=${plant}`;
      } else {
        url = `${BACKEND_URL}/get_realtime_analysis?username=${username}&plant=${plant}`;
      }

      try {
        const res = await fetch(url);
        const raw = await res.json();

        let series = [];

        if (view === "raw") {
          const pts = (raw.timestamps || []).map((ts, i) => ({
            x: new Date(ts),
            y: +raw.values[i].toFixed(2),
          }));
          series = [{ id: metric, color: COLORS[metric], data: pts }];

        } else if (view === "historical") {
          series = METRICS.map(m => {
            const arr = raw[m] || [];
            const pts = arr
              .map(pt => {
                const t = new Date(pt.time);
                const y = pt.prediction;
                return (t && y != null && !isNaN(y))
                  ? { x: t, y: +y.toFixed(2) }
                  : null;
              })
              .filter(p => p);
            return { id: m, color: COLORS[m], data: pts };
          }).filter(s => s.data.length > 0);

        } else {
          series = METRICS.map(m => {
            const pts = raw
              .map(pt => {
                const val = pt[`filt_${m}`];
                return (pt.time && val != null && !isNaN(val))
                  ? { x: new Date(pt.time), y: +val.toFixed(2) }
                  : null;
              })
              .filter(p => p);
            return { id: m, color: COLORS[m], data: pts };
          }).filter(s => s.data.length > 0);
        }

        setData(series);
        setNoData(series.length === 0);
      } catch (err) {
        console.error("Error fetching chart data:", err);
        setNoData(true);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [view, metric, username, plant]);

  if (noData) {
    return (
      <Box
        sx={{
          color: t.grey[300],
          textAlign: "center",
          mt: 4,
        }}
      >
        No data available for {view === "raw" ? metric : view}.
      </Box>
    );
  }

  return (
    <ResponsiveLine
      data={data}
      theme={{
        axis: {
          domain: { line: { stroke: t.grey[100] } },
          legend: { text: { fill: t.grey[100] } },
          ticks: {
            line: { stroke: t.grey[100], strokeWidth: 1 },
            text: { fill: t.grey[100] },
          },
        },
        legends: { text: { fill: t.grey[100] } },
        tooltip: { container: { color: t.primary[500] } },
      }}
      colors={{ datum: "color" }}
      margin={{ top: 20, right: 40, bottom: 60, left: 50 }}
      xScale={{ type: "time", format: "native", precision: "second" }}
      xFormat="time:%H:%M:%S"
      axisBottom={{
        format: "%H:%M:%S",
        tickValues: "every 1 minute",
        legend: isDashboard ? undefined : "Time",
        legendOffset: 36,
        legendPosition: "middle",
      }}
      yScale={{ type: "linear", min: "auto", max: "auto", stacked: false }}
      axisLeft={{
        legend: isDashboard ? undefined : (view === "raw" ? metric : view),
        legendOffset: -40,
        legendPosition: "middle",
      }}
      pointSize={6}
      pointBorderWidth={2}
      enableSlices="x"
      useMesh
      legends={[
        {
          anchor: "bottom",
          direction: "row",
          translateY: 50,
          itemWidth: 80,
          itemHeight: 20,
          itemsSpacing: 10,
          symbolSize: 12,
          symbolShape: "circle",
          effects: [
            {
              on: "hover",
              style: {
                itemBackground: "rgba(0,0,0,0.03)",
                itemOpacity: 1,
              },
            },
          ],
        },
      ]}
    />
  );
};

export default LineChart;
